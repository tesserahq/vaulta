## Problem Statement

When a service needs metadata for a page of assets (e.g. linden-api rendering a page of resource files, each backed by a Vaulta asset), it currently has no way to ask Vaulta for more than one asset at a time. The only read path is `GET /assets/{asset_id}`, so a caller with N assets on a page must make N sequential HTTP requests to Vaulta to enrich that page.

This N+1 pattern was the direct cause of a production incident: linden-api's `GetResourceFilesQuery.enrich()` calls `GET /assets/{id}` once per resource file, one at a time. Each call is subject to a fixed client-side read timeout; with N sequential round-trips per page, ordinary latency variance on any single call is enough to trip that timeout and fail the *entire* page request, even though Vaulta itself was healthy and each individual asset lookup would have succeeded on its own. The per-id response cache added for `GET /assets/{id}` (see `0004-cached-asset-serving.md` and its follow-up) helps when the *same* id is requested repeatedly, but does nothing for this case, since a single page load requests N *distinct* ids, each exactly once.

## Solution

Add a batch read endpoint to Vaulta that accepts a list of asset ids and returns metadata for all of them in a single request/response round-trip, so a caller enriching a page of N items can do it in one HTTP call instead of N.

- `POST /assets/batch` accepts a JSON body with a list of asset ids (capped at 100 per request) and returns the full `Asset` metadata for every id that exists, in the same shape already returned by `GET /assets/{id}` and `POST /assets/search`.
- Ids that don't exist (or are malformed) are simply omitted from the response — the caller can diff the ids it requested against the ids it got back if it needs to know what's missing. No per-id error reporting.
- The batch endpoint reads through the same per-id record cache already built for `GET /assets/{id}`: each requested id is checked against the cache first, and only the ids that miss are fetched from Postgres, in a single batched query — not one query per missing id.
- Authorization semantics match `GET /assets/{id}` exactly: no ownership filtering. (`GET /assets/{id}` today has no ownership check at all — that's a pre-existing gap tracked separately in [#126](https://github.com/tesserahq/vaulta/issues/126), not something this PRD changes or depends on. The batch endpoint is deliberately consistent with the single-get endpoint it's meant to replace for this use case, rather than introducing new, stricter behavior on only one of the two.)

Updating linden-api's `GetResourceFilesQuery` to actually call this new endpoint instead of looping over `GET /assets/{id}` is a separate follow-up PR in the linden-api repo, once this endpoint exists and ships.

## User Stories

1. As linden-api enriching a page of resource files, I want to fetch metadata for all the assets on that page in a single request, so that page load time no longer scales with the number of files on the page.
2. As linden-api enriching a page of resource files, I want that single request to not be vulnerable to the same per-call timeout that N sequential single-asset requests were, so that ordinary latency variance on Vaulta's side doesn't fail the whole page.
3. As a caller of the batch endpoint, I want ids that don't exist to be silently omitted from the response rather than causing the whole request to fail, so that one bad/stale id doesn't block metadata for the rest of the batch.
4. As a caller of the batch endpoint, I want a clear, enforced limit on how many ids I can request at once, so that I get a fast, predictable error if I misuse the endpoint (e.g. accidentally pass an unbounded list) instead of an unbounded, slow query.
5. As a platform operator, I want repeated batch requests that overlap in ids with recent single-get or batch requests to benefit from the existing per-id cache, so that database load stays proportional to unique assets actually needed, not to the number of requests.
6. As a platform operator, I want the batch endpoint's cache misses to be satisfied with a single database query per request (not one query per missing id), so that a worst-case all-cache-miss batch request still only costs one round-trip to Postgres instead of up to 100.
7. As a developer maintaining this code, I want the "check cache per id, batch-query Postgres for the misses, populate the cache for what was found" logic isolated in one small, testable unit, so that it can be verified without needing a real Redis instance or database, following the same pattern already established for the single-asset cached lookup.
8. As a developer maintaining this code, I want the batch endpoint's authorization behavior to be explicitly identical to `GET /assets/{id}`'s current behavior, so that this PRD doesn't silently introduce a new, inconsistent access-control model alongside the existing (separately tracked) gap.
9. As a developer calling this endpoint from another service, I want its request/response shape to follow the same conventions as `POST /assets/search` (POST with a JSON body, `List[Asset]` response), so that it's predictable and consistent with the rest of the `/assets` API surface.

## Implementation Decisions

- **Endpoint**: `POST /assets/batch`, requiring authentication like every other `/assets` route. Request body is a small Pydantic model with a single `ids: List[UUID]` field, constrained to a maximum of 100 entries (a request exceeding that limit is rejected with a 400/422 before any lookup work happens, via a Pydantic length constraint on the field). Response model is `List[Asset]` — the same schema already returned by `GET /assets/{id}` and `POST /assets/search`.
- **Repository**: a new `AssetRepository.get_assets_by_ids(ids: List[UUID]) -> List[Asset]` method, doing a single `WHERE id IN (...)` query. This is the only new repository method needed; it's a straightforward extension of the existing `get_asset`/`search` methods.
- **Batch lookup module**: a new small function/class (living alongside the existing `get_asset_for_serving` cached-lookup helper in `app/services/asset_lookup.py`) that implements the cache-then-batch-DB-fallback logic: given a list of ids, a repository, and the `AssetCache`, it reads each id from the cache first, collects which ids hit (found or confirmed-not-found) versus missed entirely, issues one `get_assets_by_ids` call for the missed ids, populates the cache for each of those (positive or negative, matching the existing per-id cache semantics from `0004`), and returns the full list of found `Asset` records (cache hits plus DB hits combined). This is the single place where the batch hit/miss/negative-hit/batch-fallback decision logic lives, mirroring how `get_asset_for_serving` is the single place for the single-id version of this decision.
- **Route wiring**: the `POST /assets/batch` handler is a thin adapter — validate the request body, call the batch lookup module, return its result as the response. No business logic lives in the route handler itself.
- **Cache reuse**: no changes to `AssetCache` itself are anticipated — the batch lookup module calls the same `read_record`/`write_record_found`/`write_record_not_found` methods already added for `GET /assets/{id}`, just once per id in the batch rather than once per request.
- **Ordering**: the response list has no guaranteed ordering relative to the request's `ids` list (consistent with `POST /assets/search`, which is also unordered). Callers that need to correlate results back to requested ids should key off each returned `Asset`'s `id` field.
- **Out-of-scope refactor note**: `get_asset_by_id` (the existing single-id dependency used by `GET`/`DELETE /assets/{id}`) is not refactored to call through the new batch module internally. The two code paths will have some logical overlap (both do cache-check-then-DB-fallback for asset records), but unifying them is a nice-to-have cleanup, not required for this PRD to deliver its value, and is called out as a possible follow-up rather than bundled in here.

## Testing Decisions

Good tests here verify observable behavior (what gets returned, what the repository/cache calls look like from the outside) rather than internal implementation details of how the cache client talks to Redis, following the same testing philosophy already used for the `0004` caching work.

- **Batch lookup module**: unit-tested with a mocked repository and mocked cache client. Cases: all requested ids are cache hits (repository's `get_assets_by_ids` is never called); some ids are cache hits and some are misses (repository is called exactly once, with only the missing ids); an id is a cached negative hit (excluded from the result, repository not called for it); a miss that comes back from the repository is written to the cache as a positive entry; a miss that the repository doesn't return (nonexistent id) is written to the cache as a negative entry; an empty `ids` list returns an empty result without calling the repository or cache at all.
- **Repository**: unit- or integration-tested (following whichever convention `AssetRepository`'s other methods already use) to confirm `get_assets_by_ids` returns exactly the matching rows for a set of ids, including the case where some requested ids don't exist.
- **Route-level regression tests**: new tests in `tests/app/routers/test_assets.py` (following the existing pattern of overriding `get_asset_cache` with a mocked `AssetCache` and using the `client` fixture) covering: a request within the batch limit returns the expected assets; a request exceeding the 100-id cap is rejected before any lookup occurs; a batch containing a mix of existing and nonexistent ids returns only the existing ones; an empty `ids` list returns an empty list with a 200 (not an error).
- No new Redis or Postgres test infrastructure is introduced — this follows the existing project convention (mocked `Cache`/`AssetCache` for unit and router tests, real transactional Postgres via the `client`/`db` fixtures only where the existing repository tests already use it).

## Out of Scope

- Updating linden-api's `GetResourceFilesQuery` (or any other caller) to actually use this new endpoint — that's a separate follow-up PR in the linden-api repo.
- Fixing the missing ownership check on `GET /assets/{id}` (tracked in [#126](https://github.com/tesserahq/vaulta/issues/126)) — the batch endpoint intentionally matches existing behavior rather than resolving that gap.
- A batch *write* endpoint (create/update/delete multiple assets in one request) — this PRD is read-only.
- Refactoring `get_asset_by_id`'s single-lookup logic to share an implementation with the new batch lookup module.
- Tuning the 100-id cap based on production traffic data — it's chosen to match the existing pagination max page size already in use, not derived from measurement.
- Any change to `POST /assets/search`'s labels-based search — this is a separate, purely id-based lookup path.

## Further Notes

- This PRD is the direct follow-up to two things that already shipped: (1) `0004-cached-asset-serving.md`'s per-id cache, later extended to also cover `GET /assets/{id}` (not just the signed-URL serve path), and (2) an interim mitigation in linden-api (reusing a single `VaultaClient`/session across the enrichment loop instead of constructing one per resource file) that reduces connection overhead but does not eliminate the N sequential round-trips. This PRD is the proper fix for the N+1 shape of the problem; the linden-api mitigation remains valuable in the meantime and after, since not every batch of ids Vaulta serves will always go through the new endpoint.
- The 100-id cap was chosen to match `fastapi_pagination`'s existing max page size already used elsewhere (e.g. in linden-api's resource-file listing endpoints), so that a single page of results can never produce a batch request that exceeds it.
- The GitHub issue documenting the `GET /assets/{id}` ownership gap ([#126](https://github.com/tesserahq/vaulta/issues/126)) also mentions the broader RBAC/workspace-scoping work tracked in issue #48; whoever picks up that issue should consider whether the batch endpoint's authorization model needs to change at the same time, since it's designed to mirror `GET /assets/{id}`'s behavior exactly.
