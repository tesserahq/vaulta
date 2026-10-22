# Project scoped document authorization

Status: Draft for review  
Date: 19 October 2026  
Related issues: [Vaulta 126](https://github.com/tesserahq/vaulta/issues/126) and [Vaulta 48](https://github.com/tesserahq/vaulta/issues/48)

**Terminology:** A *project* is the unit that owns data and permissions across the Tessera platform, identified by `project_id`. Each consuming product may use its own name for it (Linden calls it an account). This PRD uses `project` and `project_id`, matching eventa and the other Tessera services. Vaulta is a framework service and must not assume any one product's model. [Linden as the first consumer](#appendix-a-first-consumer-linden) is described in an appendix.

## Problem Statement

Tessera products store sensitive files for their customers: identity documents, legal papers, medical or financial scans, and images they must send by email. Access must follow the project to which a document belongs, including when several authorized members share a project. Knowing an asset identifier or possessing a copied private-document URL must not grant access.

Vaulta currently authenticates metadata requests without consistently authorizing access to individual assets. Individual reads, listings, and label searches lack project scoping. Assets record an uploader but do not record a project affiliation. An uploader-only rule would prevent legitimate project sharing and would conflict with service-token metadata requests from consuming products.

File delivery has a separate gap. Consuming services can sign asset URLs locally, and Vaulta serves valid signed URLs without checking the current viewer's membership. The signed serving endpoint returns a one-year public immutable cache directive. Neither URL signing nor metadata authorization alone satisfies project-based document protection.

Consuming products also accept Vaulta identifiers when attaching files to their own business records. The attachment boundary must prevent an authorized user from linking another project's asset and obtaining access through a product's service credentials.

## Solution

Make private documents project scoped from upload through attachment, metadata retrieval, and download. Use Custos for permission decisions and authenticated file delivery for private documents. Preserve explicit support for intentionally shareable media such as images embedded in emails.

A member with read permission can view documents belonging to their project regardless of who uploaded them. A person outside that project cannot discover metadata, attach its assets, or retrieve its documents through a copied URL. Membership removal or project deactivation prevents subsequent authorized access checks from succeeding.

The design applies to any consuming product. Each product maps its own ownership model onto `project_id`, sends that context from authenticated sessions, and declares which of its fields reference Vaulta assets. Vaulta enforces the policy; it does not learn product-specific business rules.

Existing production data is handled by classification, not by ownership guesses. Legacy rows (see [Shareable media compatibility](#shareable-media-compatibility)) keep their current behavior. Each consuming product confirms before release whether it holds user-uploaded documents created under the old model. If it does, that product must classify or migrate them explicitly before enforcement. No backfill of ownership is assumed, and this PRD does not authorize deleting users, projects, databases, or other applications' assets. Schema migrations and coordinated deployment are still required.

### Proposed access policy

| Actor | Private document access |
| --- | --- |
| Unauthenticated caller | Denied, including with a copied private-document URL |
| Active project member with read permission | Read metadata and download within that project |
| Active project member with upload permission | Upload and attach within that project |
| Active project member with delete permission | Delete within that project |
| Member of another project | Denied without revealing asset existence |
| Removed member or deactivated identity/project | Denied on subsequent requests |
| Consuming service identity (M2M) | Only explicitly granted project scopes; validate the acting user's permission for user-triggered operations |
| Operator or administrator | No implicit bypass; any operational access requires an explicit permission grant and audit record |

These rules are proposed requirements for review. Exact Custos role names and the mapping of each product's roles to read, upload, and delete permissions remain decisions for each consuming product.

## User Stories

1. As a project member, I want documents to belong to my project so that access does not depend on the uploader's identity.
2. As an authorized reader, I want to open a document uploaded by another project member so that we can manage shared affairs.
3. As an uploader, I want uploads associated with the project I am working in so that documents cannot accidentally cross project boundaries.
4. As a user belonging to multiple projects, I want each document operation checked against the document's project so that switching projects cannot leak information.
5. As a project owner, I want removed members to lose document access so that old links do not preserve their permissions.
6. As a customer, I want copied document links to require login and permission so that forwarding a link does not expose my files.
7. As a customer, I want asset names, extracted text, summaries, labels, and ownership information protected along with file contents.
8. As an authorized user, I want lists and searches to contain only permitted assets so that unrelated projects remain undiscoverable.
9. As a customer, I want attachment creation and replacement to reject assets outside my project so that identifiers cannot bypass authorization.
10. As a permitted editor, I want deletion governed by project permissions so that an uploader-only rule does not block legitimate administration.
11. As an operator, I want service access explicitly bounded so that one service identity cannot access projects it has not been granted.
12. As a recipient of an email, I want intentionally shared images to keep working so that stronger document protection does not break existing communications.
13. As an operator, I want failed permission checks to fail closed so that a Custos outage cannot expose documents.
14. As an operator, I want security events recorded without file contents or access credentials so that access can be investigated safely.

## Implementation Decisions

### Asset scope and classification

- Persist `project_id`, uploader, and access classification as authoritative asset attributes. `project_id` is required for private project documents. Uploader identity is an audit attribute, not the authorization boundary.
- Decouple asset lifetime from the uploader. Today `User.assets` uses `cascade="all, delete-orphan"` and `assets.user_id` is a non-null foreign key, so deleting an uploader's Vaulta user row (`UserRepository.delete_user`) deletes every project document they uploaded. Remove the ORM cascade and change the foreign key to `ON DELETE SET NULL` with a nullable `user_id`, following the two-release migration rule.
- Distinguish private project documents from explicitly shareable media. Default new document uploads to private. An upload requests shareable media with an explicit `visibility=shareable` form field, honored only when the caller has an explicit permission to publish shareable media. A caller without that permission who sends `visibility=shareable` gets 403; the request is never silently downgraded to private, because that would break an email image with nothing failing at send time. `expires_in` alone does not imply shareable.

| | Private project document | Shareable media |
| --- | --- | --- |
| Who can fetch the bytes | Only an authenticated, authorized member of the project (or an admin) | Anyone holding the signed serve URL, until it expires |
| Serving route | Authenticated download flow only; anonymous serve rejects it | `/assets/serve` with a valid signature |
| Cache policy | `private, no-store` | Immutable public caching |
| Revocation | Removing membership denies the next request | Does not revoke the URL; it works until expiry |
| Typical use | Passports, wills, scanned documents | Email images already sent to recipients |
- Project affiliation must come from authenticated, validated context. A caller may name a `project_id`, but the name only counts once Custos has authorized the caller for that project. A label or free-form identifier is not proof of authorization. The existing `project_id` upload form field is currently forwarded only to Modela processors and is not stored on the asset; in the new model it is persisted as the authoritative scope. Apply this to every asset-creating route, including `POST /assets/from-url`.
- Custos domains use the bare project ID, as eventa does (`authorize` with a `domain_resolver` that returns `project_id`). Vaulta is shared by several Tessera products (for example Linden, looply, and sendly), each with its own projects. `project_id` is the only tenancy boundary: a user or service can reach only the projects its Custos membership or grant allows, whichever client it authenticates through. Assets do not store an application.
- Service identities (M2M) are authorized by explicit Custos grants for the projects they may access. Record the calling client (the token's `azp`, or `sub` for client-credentials tokens) in the audit log for every access, not on the asset.
- `project_id` is required on every upload except for Tessera administrators. An upload without `project_id` is rejected with 400 for everyone else. Administrators pass `project_id=*` to act at the global scope. The `*` is a request marker, not a stored value: it is authorized by a Custos check on the wildcard domain, which only administrators hold, and the asset is stored with `project_id` NULL. The wildcard is never a silent default.
- Today the upload form defaults `project_id` to `"*"` (`app/routers/assets.py`), and the RBAC resolver defaults to `"*"` when the query parameter is missing (`app/auth/rbac.py`). Both defaults must go, so that a missing project fails with 400 and only an explicit, authorized `*` reaches the global scope.
- Global-scope uploads are the only path for project-less shareable media. Products such as looply and sendly send email images with no `project_id`, so they can publish only if they hold an administrator grant on the wildcard domain. Otherwise they must send a project.
- Do not allow ordinary attachment or update operations to change an asset's project. Cross-project transfer is outside scope.
- Do not return raw storage URLs, public object URLs, or anonymous signed serve links for private documents. Review upload responses and processing integrations as well as download responses. Trusted processing services may receive narrowly scoped access that is unavailable to ordinary users.

### Authorization module

- Introduce one asset authorization interface that accepts the authenticated principal, requested action, and authoritative asset scope. It owns Custos integration, service delegation rules, denial behavior, and permission-cache policy.
- Keep raw asset lookup separate from authorized access. Every externally reachable path must call authorization before returning metadata, file contents, or issuing access credentials, whether the asset came from the database or a cache.
- Apply the same policy to single and batch metadata lookup, listings, searches, uploads, attachment validation, deletion, downloads, and any asset processing operations exposed to callers. Cover existing endpoints and planned batch lookup contracts.
- Require a `project_id` parameter on `GET /assets`, `POST /assets/search`, and `POST /assets/batch`, and return 400 when it is missing. Authorize that one project with a single Custos check, then filter in SQL (`WHERE project_id = :project_id`) before pagination. Custos has no "list projects this principal can read" primitive: the SDK exposes only single-domain `authorize`, and `GET /users/{id}/memberships` lists memberships, not effective permissions. "List everything I can see" is therefore not a supported contract. Never fetch all assets and rely on client-side filtering.
- The new routes must not use the `"*"` fallback that Vaulta's current `infer_project` returns when `project_id` is absent, nor the equivalent fallback in eventa. A wildcard check would authorize against every project, so a missing `project_id` must be a 400, not a wildcard.
- Authorize each distinct (principal, action, project) at most once per request, and cache nothing across requests. A 100-asset batch or a page whose assets all belong to one project costs one Custos call. Checking per asset would bring back the N sequential round trips that caused the incident behind PRD 0005.
- Return 401 for missing authentication. For authenticated callers, make inaccessible and nonexistent individual assets indistinguishable with 404. The batch endpoint silently omits both, consistent with PRD 0005.
- Keep missing and denied indistinguishable during a Custos outage. When the request names a project, authorize it before the asset lookup and scope the lookup to that project, so a foreign asset is simply not found. When no project is named, a Custos failure returns a retryable 503 for every lookup, including nonexistent IDs; a 404 must never be returned without a successful Custos check. Otherwise a nonexistent ID (404 without calling Custos) and a foreign ID (503 because Custos is needed) become an existence oracle.
- Initially avoid caching positive membership decisions for private-document access. Metadata caches may remain, but must not cache permission grants. Keep the SDK's `AUTHORIZATION_CACHE_ENABLED` off for Vaulta. Any later permission cache needs a defined revocation guarantee and explicit approval.
- Version the asset cache keys (for example a `v2:` prefix) in the release that adds the scope and classification fields. `AssetCache` currently stores serve metadata as `{mime_type, filename}` and full records as the current `Asset` schema, with a 10-minute TTL. Treat any entry without classification or project as a cache miss, never as a default.

### Consuming product integration

- Each consuming product resolves a document's project from its own business model and checks the acting user's permission before requesting metadata, attaching assets, replacing references, deleting, or serving downloads. Vaulta does not perform these product-level checks.
- Vaulta validates service identity and scope independently. A valid M2M token is insufficient for unrestricted project access. Delegated project context must be bound to the authenticated service's allowed scopes.
- On attachment creation or replacement, verify that the Vaulta asset exists, belongs to the same project, and is eligible for attachment before committing the relationship. A caller cannot use a product's service as a privileged URL signer for an arbitrary asset ID.
- Each consuming product must inventory every field that holds a Vaulta asset ID. Each such field is an attachment point that must validate project and eligibility on create and replace, and it must not mint anonymous access during serialization. New fields must be added to the inventory and use the shared attachment validator.
- Consumer frontends and client SDKs carry validated project context. Coordinate releases across Vaulta, each consuming product's API, its frontend, and any SDK (see [Shareable media compatibility](#shareable-media-compatibility)).
- Deletion has one enforcement point. Route it through the consuming product's API, which removes the business reference and the Vaulta asset together. Frontends should not call Vaulta's delete endpoint directly with the user token, because then the product never checks the user's permission and its rows can reference deleted assets.
- Access URLs must lead to an authenticated, authorized download flow. Serializing an asset identifier must not mint anonymous access.

### Private file delivery

- Provide an authenticated private download contract. The recommended browser flow is a same-origin endpoint in the consuming product, using its existing authenticated session. The product validates the document relationship and permission, then streams bytes from Vaulta using scoped service access. Equivalent clients may use a protected Vaulta endpoint with a valid user token.
- Support the chosen browser flow without requiring a bearer token in a URL. Review previews and range requests so that every new content request is authorized.
- Use `Cache-Control: private, no-store` for private content and sensitive metadata responses. Ensure proxies, CDN configuration, redirects, and error responses do not create a public caching bypass. Under `no-store`, every rendered private image is a fresh authorized request streamed through the consuming product from Vaulta, so a page with N images makes N such requests on each render. Measure that cost on list pages before release. For that image class only, `private, max-age=<short>` is the fallback, and it needs explicit approval because it delays revocation for the cached duration.
- Keep storage private and prevent direct bucket/object access from bypassing Vaulta authorization. Private responses must not redirect to publicly reusable object URLs.
- Reject private assets on anonymous legacy serving routes even when their signature is valid. A signature is not an override for private classification.
- Permission changes affect subsequent requests. Already downloaded bytes cannot be revoked, and terminating an already authorized in-flight stream is outside scope.

### Shareable media compatibility

- Preserve the existing signed URL format, secret derivation, and routes needed by already-sent email images. Do not rotate the master signing secret as part of this feature.
- Restrict anonymous serving to assets explicitly classified as shareable media. Inventory every consuming application that uploads shareable media before enforcement. The absence of known private documents does not establish that the shared Vaulta installation holds no other data.
- Consuming applications that upload email images directly to `POST /assets` with `expires_in` and no visibility flag must send `visibility=shareable` before Vaulta enforces default-private, and their users must hold the Custos permission to publish shareable media. Otherwise every newly sent email gets a `serve_url` that `/assets/serve` rejects, and nothing fails at send time to warn anyone.
- Existing rows get a NULL classification, meaning legacy (see [Deployment and observability](#deployment-and-observability)). `/assets/serve` treats legacy as shareable, which preserves already-sent email links. Do not invent project ownership for legacy media or reopen anonymous access for private documents.
- Products may have legacy assets that a product itself owns, such as profile images. Each product decides whether to leave those legacy/shareable or assign their project through its own mapping, as a narrow, one-off task. Assignment must come from the product's records, not guessed from Vaulta data.

### Deployment and observability

- Add schema fields and indexes using migrations compatible with overlapping application versions. Old and new API containers overlap during a deploy, so the classification default decides what happens to rows the previous release inserts. A `private` server default breaks existing and in-flight email images. A `shareable` server default makes any document uploaded to an old container permanently public. Roll out in this order:
  1. **Release 1 (additive):** add nullable `project_id` and `classification` columns with no server default, plus an index on `(project_id)`. `project_id` uses the UUID type, matching eventa's `events.project_id`. NULL classification means legacy and is treated as shareable by `/assets/serve` only. New code always writes an explicit classification and scope. Also in this release: make `user_id` nullable, remove the cascade, and version the cache keys.
  2. **Client cutover:** every consuming application sends explicit visibility, and sends project context for private documents. Project-less shareable uploads are the exception described above. This includes the product APIs, their frontends, and any service that creates assets on their behalf.
  3. **Enforcement:** default uploads to private, reject private assets on `/assets/serve`, and require the `project_id` parameter on list, search, and batch.
  4. **Release 2 (contract):** once nothing writes NULL, classify the remaining legacy rows and add `NOT NULL` on `classification`, plus a `CHECK` that private implies `project_id IS NOT NULL`. Switch the `user_id` foreign key to `ON DELETE SET NULL`.
- Coordinate cutover so old clients cannot create unscoped private documents. Each consuming product confirms, at release time, whether it holds user-uploaded documents created under the old model. If it does, stop and revise its rollout plan rather than deleting or guessing ownership.
- Record actor/service, project, asset, operation, result, timestamp, and correlation identifier for relevant access and permission changes. Exclude tokens, signed URLs, extracted document contents, and file bytes from logs.
- Track denied operations, Custos failures, and private download failures. Do not fall back to anonymous delivery or global service access during outages.

## Testing Decisions

Test externally observable access behavior across Vaulta and a consuming application rather than duplicating authorization implementation details. Use the existing PostgreSQL-backed fixtures and authenticated router test patterns, extending them with distinct users, service identities, and projects.

Required acceptance coverage:

1. An authorized member can read metadata and download a document uploaded by another member of the same project.
2. A member of another project cannot read, search for, list, attach, replace references with, delete, or download that asset.
3. A denied read remains denied after a permitted read populates the metadata cache.
4. A copied private download URL fails without authentication and fails for an authenticated nonmember.
5. A correctly signed legacy serve URL cannot serve an asset classified as private.
6. Removed membership, identity deactivation, and project deactivation deny the next request, including after prior successful access.
7. Spoofed project context and forged or unrelated service identities do not expand a user's or service's access.
8. Consuming-application service requests succeed only within explicitly granted scope; attachment validation prevents arbitrary asset IDs from producing access.
9. Lists and searches remain correctly scoped across pagination, label queries, empty results, and any batch endpoint.
10. Private upload and download responses expose no anonymous storage URL and use the required cache policy. Direct storage access cannot bypass authorization in the deployed configuration.
11. Custos timeout, unavailability, or malformed responses fail closed. Missing assets and denied assets have the same external lookup behavior.
12. Existing permitted email-image links continue to work, including the existing signature format. Shareable media publishing requires explicit permission.
13. Upload, attachment, preview, download, and deletion work through the actual session flow of a consuming frontend, including users who belong to multiple projects.
14. List, search, and batch requests without a `project_id` parameter return 400, and the `"*"` wildcard is never used for them. A 100-asset batch within one project makes exactly one Custos call.
15. During a Custos outage, lookups of nonexistent and foreign asset IDs return the same response.
16. Every asset field in a consuming product's inventory rejects attaching another project's asset on create and replace.
17. Deleting an uploader's Vaulta user leaves the project's assets intact.
18. Cache entries written in the pre-release format are treated as misses, never served with a default classification.
19. Legacy rows (NULL classification) keep serving through existing signed URLs. Uploads with `visibility=shareable` from each shareable-media producer produce working serve URLs once enforcement is on.
20. A product's automatic asset creation (for example an avatar import) creates an asset with project scope.

Use local automated tests for policy and database behavior, API integration tests for service boundaries, and staging browser checks for session-based file delivery. Validate storage and proxy access policies separately; passing application tests alone does not establish infrastructure privacy.

## Out of Scope

- Migrating or backfilling any product's existing customer documents.
- Resetting production users, projects, databases, or unrelated assets.
- Per-document invitations, public document sharing, expiring guest links, or anonymous private-document links.
- Moving assets between projects or attaching one private asset across projects.
- Replacing the entire Custos role model or building a permission-management UI.
- Revoking bytes already downloaded or stopping an already authorized active stream.
- A general redesign of analysis providers, storage backends, or email-media delivery.
- Product-specific business rules (for example, which roles a product grants). Products own those; Vaulta enforces the project boundary.

## Further Notes

Issue 126 should be closed only when unauthorized metadata access is prevented across individual reads and discovery endpoints, with service integration preserved. Issue 48 requires the full project-scoped lifecycle, including file delivery and copied-link behavior. Fixing only one route does not complete either overall access model.

Review decisions before implementation:

- Confirm the Custos domain and role conventions across all Tessera services, including the deactivation signals and the service delegation mechanism.
- Confirm how service identities are granted project access in Custos, and that M2M tokens from Auth0 carry the client identity the audit log will record (`azp` or `sub`).
- Confirm the project ID format. eventa uses UUIDs, but Vaulta's current `project_id` form field accepts any string and defaults to `"*"`. Existing values must be checked before the column is typed as UUID.
- Confirm how existing shareable media will be identified without changing existing links. The proposed default treats all legacy rows as shareable on `/assets/serve`.
- Decide, per consuming product, whether its avatar-style images are private or shareable. If private, accept the `no-store` streaming cost or approve a short private cache for that image class.

## Appendix A: First consumer (Linden)

Linden is the first product to adopt this design. Its requirements are the reference inventory, not the design's boundary.

- **Project mapping:** a Linden account is a project. Linden resolves each document's project from its business entity.
- **Automatic avatar import:** `CreateAccountCommand._get_avatar_resource` imports the identity avatar through `POST /assets/from-url` using an M2M token with no project context, and Linden signs serve URLs for it. This call must carry project context going forward. Existing avatar assets are legacy rows; Linden decides whether to keep them shareable or assign their project through its person→project mapping. They are identified through Linden's `avatar` fields, not guessed from Vaulta data.
- **Deletion:** linden-portal currently calls `DELETE /assets/{id}` on Vaulta directly with the user token, so Linden never checks the user's permission and Linden rows end up referencing deleted assets. This is the case the deletion rule above addresses.
- **Attachment inventory:** each field below currently mints a signed serve URL through `get_signed_url_if_exists` during serialization, and each must validate project and eligibility on create and replace.

| Linden schema | Asset field(s) | Proposed classification |
| --- | --- | --- |
| `resource_file` | `resource_id` | Private |
| `will` | `document_file_id` | Private |
| `passport` | `front_image`, `back_image` | Private |
| `drivers_license` | `front_image`, `back_image` | Private |
| `birth_certificate` | `front_image`, `back_image` | Private |
| `social_security_number` | `front_image`, `back_image` | Private |
| `vehicle` | `photo_asset_id` | Private |
| `real_estate` | `photo_asset_id` | Private |
| `person`, `contact`, `pet` | `avatar` | Review decision (see Further Notes) |

- **Other shareable-media producers:** looply-portal and sendly-portal, which are other Tessera products, upload email images to `POST /assets` with `expires_in`, no visibility flag, and no `project_id` today. They must send `visibility=shareable` before enforcement, and they still send no `project_id`. Without a project, their uploads need the administrator wildcard grant described in the asset scope rules; otherwise they must send a `project_id`.
