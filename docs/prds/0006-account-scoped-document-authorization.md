# Project scoped document authorization

Status: Draft for review  
Date: 19 October 2026  
Related issues: [Vaulta 126](https://github.com/tesserahq/vaulta/issues/126) and [Vaulta 48](https://github.com/tesserahq/vaulta/issues/48)

**Terminology:** In Linden, an account is a project. This PRD uses `project` and `project_id` to match eventa and the other Tessera services. The `CreateAccountCommand` name in Linden API is kept where it refers to code.

## Problem Statement

Linden customers store sensitive family documents. Access must follow the project to which a document belongs, including when several authorized family members share a project. Knowing an asset identifier or possessing a copied private-document URL must not grant access.

Vaulta currently authenticates metadata requests without consistently authorizing access to individual assets. Individual reads, listings, and label searches lack project scoping. Assets record an uploader but do not record a project affiliation. An uploader-only rule would prevent legitimate project sharing and conflict with Linden API's service-token metadata requests.

File delivery has a separate gap. Linden API can sign asset URLs locally, and Vaulta serves valid signed URLs without checking the current viewer's membership. The signed serving endpoint returns a one-year public immutable cache directive. Neither URL signing nor metadata authorization alone satisfies project-based document protection.

Linden also accepts Vaulta identifiers when attaching files to business records. The attachment boundary must prevent an authorized user from linking another project's asset and obtaining access through Linden's service credentials.

## Solution

Make private documents project scoped from upload through attachment, metadata retrieval, and download. Use Custos for permission decisions and authenticated file delivery for private documents. Preserve explicit support for intentionally shareable media such as images embedded in emails.

A member with read permission can view documents belonging to their project regardless of who uploaded them. A person outside that project cannot discover metadata, attach its assets, or retrieve its documents through a copied URL. Membership removal or project deactivation prevents subsequent authorized access checks from succeeding.

Production can start with the new model for user-uploaded documents: the product owner confirms that the existing production users have not uploaded document files. That does not mean Vaulta holds no Linden assets. Linden API creates one automatically per project: `CreateAccountCommand._get_avatar_resource` imports the identity avatar through `POST /assets/from-url` using an M2M token and no project context, and Linden signs serve URLs for it. These existing Linden avatar assets must be explicitly classified (see [Shareable media compatibility](#shareable-media-compatibility)), and the automatic avatar import must carry project context going forward. No user-document ownership backfill or customer-file migration is required. Schema migrations and coordinated application deployment are still required. This does not authorize deleting production users, projects, databases, or other applications' assets.

### Proposed access policy

| Actor | Private document access |
| --- | --- |
| Unauthenticated caller | Denied, including with a copied private-document URL |
| Active project member with read permission | Read metadata and download within that project |
| Active project member with upload permission | Upload and attach within that project |
| Active project member with delete permission | Delete within that project |
| Member of another project | Denied without revealing asset existence |
| Removed member or deactivated identity/project | Denied on subsequent requests |
| Linden service identity | Only explicitly granted application and project scopes; validate the acting user's permission for user-triggered operations |
| Operator or administrator | No implicit bypass; any operational access requires an explicit permission grant and audit record |

These rules are proposed requirements for review. Exact Custos role names and the mapping of Linden roles to read, upload, and delete permissions remain implementation planning decisions.

## User Stories

1. As a project member, I want documents to belong to my project so that my family's access does not depend on the uploader's identity.
2. As an authorized reader, I want to open a document uploaded by another project member so that we can manage shared affairs.
3. As an uploader, I want uploads associated with the project I am working in so that documents cannot accidentally cross project boundaries.
4. As a user belonging to multiple projects, I want each document operation checked against the document's project so that switching projects cannot leak information.
5. As a project owner, I want removed members to lose document access so that old links do not preserve their permissions.
6. As a customer, I want copied document links to require login and permission so that forwarding a link does not expose my files.
7. As a customer, I want asset names, extracted text, summaries, labels, and ownership information protected along with file contents.
8. As an authorized user, I want lists and searches to contain only permitted assets so that unrelated projects remain undiscoverable.
9. As a customer, I want attachment creation and replacement to reject assets outside my project so that identifiers cannot bypass authorization.
10. As a permitted editor, I want deletion governed by project permissions so that an uploader-only rule does not block legitimate administration.
11. As an application operator, I want service access explicitly bounded so that one application's credentials cannot access another application's documents.
12. As an email recipient, I want intentionally shared email images to keep working so that stronger document protection does not break existing communications.
13. As an operator, I want failed permission checks to fail closed so that a Custos outage cannot expose documents.
14. As an operator, I want security events recorded without file contents or access credentials so that access can be investigated safely.

## Implementation Decisions

### Asset scope and classification

- Persist the owning application/service, `project_id`, uploader, and access classification as authoritative asset attributes. `project_id` is required for private project documents. Uploader identity is an audit attribute, not the authorization boundary.
- Decouple asset lifetime from the uploader. Today `User.assets` uses `cascade="all, delete-orphan"` and `assets.user_id` is a non-null foreign key, so deleting an uploader's Vaulta user row (`UserRepository.delete_user`) deletes every project document they uploaded. Remove the ORM cascade and change the foreign key to `ON DELETE SET NULL` with a nullable `user_id`, following the two-release migration rule.
- Distinguish private project documents from explicitly shareable media. Default new document uploads to private. An upload requests shareable media with an explicit `visibility=shareable` form field, honored only when the caller has an explicit permission to publish shareable media. `expires_in` alone does not imply shareable.
- Project affiliation must come from authenticated, validated context. A caller may name a `project_id`, but the name only counts once Custos has authorized the caller for that project. A label or free-form identifier is not proof of authorization. The existing `project_id` upload form field is currently forwarded only to Modela processors and is not stored on the asset; in the new model it is persisted as the authoritative scope. Apply this to every asset-creating route, including `POST /assets/from-url`.
- Custos domains use the bare project ID, as eventa does (`authorize` with a `domain_resolver` that returns `project_id`). A UUID project ID is already globally unique, so the domain does not need an application prefix. The application is not encoded in the domain; it comes from validated token context and is stored on the asset. Vaulta's authentication currently reads only the JWT `sub`, so linden-portal, looply-portal, and sendly-portal user tokens cannot yet be told apart. Validate the application against the token's `azp` claim and the `clients` table. A cross-application check must not rely on the caller naming the application.
- Do not allow ordinary attachment or update operations to change an asset's project. Cross-project transfer is outside scope.
- Do not return raw storage URLs, public object URLs, or anonymous signed serve links for private documents. Review upload responses and processing integrations as well as download responses. Trusted processing services may receive narrowly scoped access that is unavailable to ordinary users.

### Authorization module

- Introduce one asset authorization interface that accepts the authenticated principal, requested action, and authoritative asset scope. It owns Custos integration, service delegation rules, denial behavior, and permission-cache policy.
- Keep raw asset lookup separate from authorized access. Every externally reachable path must call authorization before returning metadata, file contents, or issuing access credentials, whether the asset came from the database or a cache.
- Apply the same policy to single and batch metadata lookup, listings, searches, uploads, attachment validation, deletion, downloads, and any asset processing operations exposed to callers. Cover existing endpoints and planned batch lookup contracts.
- Require a `project_id` parameter on `GET /assets`, `POST /assets/search`, and `POST /assets/batch`, and return 400 when it is missing. Authorize that one project with a single Custos check, then filter in SQL (`WHERE application = :app AND project_id = :project_id`) before pagination. Custos has no "list projects this principal can read" primitive: the SDK exposes only single-domain `authorize`, and `GET /users/{id}/memberships` lists memberships, not effective permissions. "List everything I can see" is therefore not a supported contract. Never fetch all assets and rely on client-side filtering.
- The new routes must not use the `"*"` fallback that Vaulta's current `infer_project` returns when `project_id` is absent, nor the equivalent fallback in eventa. A wildcard check would authorize against every project, so a missing `project_id` must be a 400, not a wildcard.
- Authorize each distinct (principal, action, project) at most once per request, and cache nothing across requests. A 100-asset batch or a Linden page whose assets all belong to one project costs one Custos call. Checking per asset would bring back the N sequential round trips that caused the incident behind PRD 0005.
- Return 401 for missing authentication. For authenticated callers, make inaccessible and nonexistent individual assets indistinguishable with 404. The batch endpoint silently omits both, consistent with PRD 0005.
- Keep missing and denied indistinguishable during a Custos outage. When the request names a project, authorize it before the asset lookup and scope the lookup to that project, so a foreign asset is simply not found. When no project is named, a Custos failure returns a retryable 503 for every lookup, including nonexistent IDs; a 404 must never be returned without a successful Custos check. Otherwise a nonexistent ID (404 without calling Custos) and a foreign ID (503 because Custos is needed) become an existence oracle.
- Initially avoid caching positive membership decisions for private-document access. Metadata caches may remain, but must not cache permission grants. Keep the SDK's `AUTHORIZATION_CACHE_ENABLED` off for Vaulta. Any later permission cache needs a defined revocation guarantee and explicit approval.
- Version the asset cache keys (for example a `v2:` prefix) in the release that adds the scope and classification fields. `AssetCache` currently stores serve metadata as `{mime_type, filename}` and full records as the current `Asset` schema, with a 10-minute TTL. Treat any entry without classification or project as a cache miss, never as a default.

### Linden integration and service access

- Linden resolves each document's project from its business entity and checks the acting user's permission before requesting metadata, attaching assets, replacing references, deleting, or serving downloads.
- Vaulta validates service identity and scope independently. A valid M2M token is insufficient for unrestricted cross-application access. Delegated project context must be bound to the authenticated service's allowed scopes.
- On attachment creation or replacement, verify that the Vaulta asset exists, belongs to the same application/project, and is eligible for attachment before committing the relationship. A caller cannot use Linden as a privileged URL signer for an arbitrary asset ID.
- Update portal upload flows and client SDK contracts to carry validated project context. Coordinate the linden-portal, Linden API, Vaulta, SDK, looply-portal, and sendly-portal releases (see [Shareable media compatibility](#shareable-media-compatibility)).
- Pick one enforcement point for deletion. linden-portal currently calls `DELETE /assets/{id}` on Vaulta directly with the user token, so Linden never checks the user's permission and Linden rows end up referencing deleted assets. Route deletion through a Linden API endpoint that removes the business reference and the Vaulta asset together. The portal stops calling Vaulta's delete endpoint directly.
- Remove private URL generation from response-model serialization. Access URLs must lead to an authenticated, authorized download flow; serializing an asset identifier must not mint anonymous access.
- Cover every Linden field that holds a Vaulta asset ID. Each field below currently mints a signed serve URL through `get_signed_url_if_exists` during serialization, and each is an attachment point that must validate application, project, and eligibility on create and replace:

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

New Linden fields that reference Vaulta assets must be added to this inventory and use the shared attachment validator.

### Private file delivery

- Provide an authenticated private download contract. The recommended browser flow is a same-origin Linden endpoint using the existing authenticated session. Linden validates the document relationship and permission, then streams bytes from Vaulta using scoped service access. Equivalent clients may use a protected Vaulta endpoint with a valid user token.
- Support the chosen browser flow without requiring a bearer token in a URL. Review previews and range requests so that every new content request is authorized.
- Use `Cache-Control: private, no-store` for private content and sensitive metadata responses. Ensure proxies, CDN configuration, redirects, and error responses do not create a public caching bypass. Under `no-store`, every rendered private image is a fresh authorized request streamed through Linden API from Vaulta, so a page with N images makes N such requests on each render. If avatars stay private, measure that cost on household list pages before release. For that image class only, `private, max-age=<short>` is the fallback, and it needs explicit approval because it delays revocation for the cached duration.
- Keep storage private and prevent direct bucket/object access from bypassing application authorization. Private responses must not redirect to publicly reusable object URLs.
- Reject private assets on anonymous legacy serving routes even when their signature is valid. A signature is not an override for private classification.
- Permission changes affect subsequent requests. Already downloaded bytes cannot be revoked, and terminating an already authorized in-flight stream is outside scope.

### Shareable media compatibility

- Preserve the existing signed URL format, secret derivation, and routes needed by already-sent email images belonging to other Vaulta consumers. Do not rotate the master signing secret as part of this feature.
- Restrict anonymous serving to assets explicitly classified as shareable media. Inventory existing non-Linden consumers before enforcement; the absence of Linden documents does not establish that the shared Vaulta installation is empty.
- looply-portal and sendly-portal upload email images directly to `POST /assets` with `expires_in` and no visibility flag. Before Vaulta enforces default-private, both portals must send `visibility=shareable`, and their users must hold the Custos permission to publish shareable media. Otherwise every newly sent email gets a `serve_url` that `/assets/serve` rejects, and nothing fails at send time to warn anyone.
- Existing rows get a NULL classification, meaning legacy (see [Deployment and observability](#deployment-and-observability)). `/assets/serve` treats legacy as shareable, which preserves already-sent email links. Do not invent project ownership for legacy email media or reopen anonymous access for private documents.
- Existing Linden avatar assets are the one known group of Linden-owned legacy rows. Once the avatar classification decision is made, either leave them legacy/shareable or assign their project through Linden's person→project mapping as a narrow, one-off task. They are identified through Linden's `avatar` fields, not guessed from Vaulta data.

### Deployment and observability

- Add schema fields and indexes using migrations compatible with overlapping application versions. Old and new API containers overlap during a deploy, so the classification default decides what happens to rows the previous release inserts. A `private` server default breaks existing and in-flight email images. A `shareable` server default makes any document uploaded to an old container permanently public. Roll out in this order:
  1. **Release 1 (additive):** add nullable `application`, `project_id`, and `classification` columns with no server default, plus an index on `(application, project_id)`. `project_id` uses the UUID type, matching eventa's `events.project_id`. NULL classification means legacy and is treated as shareable by `/assets/serve` only. New code always writes an explicit classification and scope. Also in this release: make `user_id` nullable, remove the cascade, and version the cache keys.
  2. **Client cutover:** linden-portal, Linden API (including the avatar import), looply-portal, and sendly-portal send project context and explicit visibility.
  3. **Enforcement:** default uploads to private, reject private assets on `/assets/serve`, and require the `project_id` parameter on list, search, and batch.
  4. **Release 2 (contract):** once nothing writes NULL, classify the remaining legacy rows and add `NOT NULL` on `classification`, plus a `CHECK` that private implies `project_id IS NOT NULL`. Switch the `user_id` foreign key to `ON DELETE SET NULL`.
- Coordinate cutover so old clients cannot create unscoped private documents. Confirm the no-customer-documents assumption at release time; if it no longer holds, stop and revise the rollout plan rather than deleting or guessing ownership.
- Record actor/service, project, asset, operation, result, timestamp, and correlation identifier for relevant access and permission changes. Exclude tokens, signed URLs, extracted document contents, and file bytes from logs.
- Track denied operations, Custos failures, and private download failures. Do not fall back to anonymous delivery or global service access during outages.

## Testing Decisions

Test externally observable access behavior across Vaulta, Linden, and the portal rather than duplicating authorization implementation details. Use the existing PostgreSQL-backed fixtures and authenticated router test patterns, extending them with distinct users, service identities, applications, and projects.

Required acceptance coverage:

1. An authorized member can read metadata and download a document uploaded by another member of the same project.
2. Another project's member cannot read, search for, list, attach, replace references with, delete, or download that asset.
3. A denied read remains denied after a permitted read populates the metadata cache.
4. A copied private download URL fails without authentication and fails for an authenticated nonmember.
5. A correctly signed legacy serve URL cannot serve an asset classified as private.
6. Removed membership, identity deactivation, and project deactivation deny the next request, including after prior successful access.
7. Spoofed project context and cross-application identifiers do not expand a user's or service's access.
8. Linden service requests succeed only within explicitly granted scope; attachment validation prevents arbitrary asset IDs from producing access.
9. Lists and searches remain correctly scoped across pagination, label queries, empty results, and any batch endpoint.
10. Private upload and download responses expose no anonymous storage URL and use the required cache policy. Direct storage access cannot bypass authorization in the deployed configuration.
11. Custos timeout, unavailability, or malformed responses fail closed. Missing assets and denied assets have the same external lookup behavior.
12. Existing permitted email-image links continue to work, including the existing signature format. Shareable media publishing requires explicit permission.
13. Upload, attachment, preview, download, and deletion work through the actual portal session flow, including users who belong to multiple projects.
14. List, search, and batch requests without a `project_id` parameter return 400, and the `"*"` wildcard is never used for them. A 100-asset batch within one project makes exactly one Custos call.
15. During a Custos outage, lookups of nonexistent and foreign asset IDs return the same response.
16. Every Linden asset field in the inventory rejects attaching another project's or another application's asset on create and replace.
17. Deleting an uploader's Vaulta user leaves the project's assets intact.
18. Cache entries written in the pre-release format are treated as misses, never served with a default classification.
19. Legacy rows (NULL classification) keep serving through existing signed URLs. looply-portal and sendly-portal uploads with `visibility=shareable` produce working serve URLs once enforcement is on.
20. Linden's account-creation avatar import creates an asset with application and project scope.

Use local automated tests for policy and database behavior, API integration tests for service boundaries, and staging browser checks for session-based file delivery. Validate storage and proxy access policies separately; passing application tests alone does not establish infrastructure privacy.

## Out of Scope

- Migrating or backfilling existing Linden customer documents.
- Resetting production users, projects, databases, or unrelated assets.
- Per-document invitations, public document sharing, expiring guest links, or anonymous private-document links.
- Moving assets between projects or attaching one private asset across projects.
- Replacing the entire Custos role model or building a permission-management UI.
- Revoking bytes already downloaded or stopping an already authorized active stream.
- A general redesign of analysis providers, storage backends, or email-media delivery.

## Further Notes

Issue 126 should be closed only when unauthorized metadata access is prevented across individual reads and discovery endpoints, with service integration preserved. Issue 48 requires the full project-scoped lifecycle, including file delivery and copied-link behavior. Fixing only one route does not complete either overall access model.

Review decisions before implementation:

- Confirm the proposed project role mapping and whether any existing Linden roles permit narrower document access than project-wide read.
- Confirm the recommended Linden session-based streaming endpoint for browser previews and downloads.
- Confirm that Custos domains are bare project IDs in every Tessera service (as in eventa), and the deactivation signals and service delegation mechanism.
- Confirm how existing non-Linden shareable media will be identified without changing existing email links. The proposed default treats all legacy rows as shareable on `/assets/serve`.
- Decide whether Linden avatars (person, contact, pet) are private or shareable. If private, accept the `no-store` streaming cost or approve a short private cache for that image class.
- Confirm the application identity source. The proposal validates `azp` against the `clients` table, because Custos domains carry only the project ID. If that is not enough, decide how the application is bound to the token.
- Confirm the project ID format. eventa uses UUIDs, but Vaulta's current `project_id` form field accepts any string and defaults to `"*"`. Existing values must be checked before the column is typed as UUID.
