## Problem Statement

When a signed asset URL is requested via `GET /assets/serve/{payload}`, Vaulta re-queries Postgres for the asset's metadata (mime type, filename, existence) on every single request, even when the same `asset_id` was just served moments earlier and nothing about it has changed.

This becomes wasteful in real usage patterns: pages like the activity feed render the same user avatar several times per page load, and users revisit the same pages repeatedly. Each render re-fetches the same asset metadata from the database, adding unnecessary load and latency for data that rarely changes.

Separately, we recently fixed a bug where malformed/missing asset IDs in signed URLs caused a 500 instead of a 404 — but even after that fix, a client stuck retrying the same bad `asset_id` still hits Postgres on every retry, since a "not found" result isn't remembered either.

## Solution

Introduce a Redis-backed cache (using the existing `tessera_sdk.infra.cache.Cache` utility, matching Vaulta's Redis config that already exists for other purposes) in front of the asset metadata lookup used by `/assets/serve/{payload}`.

- Successful lookups ("asset exists, here's its metadata") are cached with a short TTL, so repeat requests for the same `asset_id` skip Postgres entirely until the entry expires or is invalidated.
- Failed lookups ("asset does not exist") are also cached, with a shorter TTL, so a client retrying a bad `asset_id` doesn't repeatedly hit Postgres either.
- Caching is scoped only to the serve-by-signed-URL path — it does not change behavior for authenticated asset reads (e.g. `GET /assets/{id}`), which continue to always read fresh from Postgres.
- To guarantee the cache never serves stale data after an asset is renamed or deleted, all code paths that mutate an asset now go through a new command layer that performs the database write and the corresponding cache invalidation together, so no write path can accidentally bypass invalidation.
- If Redis is unavailable, the system fails open: lookups fall straight through to Postgres as they do today, with no user-facing error.

## User Stories

1. As an end user viewing an activity feed with the same avatar repeated multiple times, I want each repeat image request to be served quickly, so that the page feels fast.
2. As an end user browsing between pages that reuse the same assets, I want those repeat asset requests to avoid unnecessary backend delay, so that navigation feels responsive.
3. As a platform operator, I want repeated requests for the same asset to avoid hitting Postgres every time, so that database load stays proportional to unique assets served, not total requests.
4. As a platform operator, I want repeated requests for a missing/invalid asset ID to avoid hitting Postgres every time, so that a misbehaving client (e.g. retrying a stale or malformed signed URL) doesn't generate unbounded database load.
5. As a developer renaming or updating an asset's metadata, I want any cached copy of that asset to be invalidated immediately, so that the serve endpoint never returns stale metadata for an asset I just changed.
6. As a developer deleting an asset, I want any cached copy of that asset to be invalidated immediately, so that the serve endpoint doesn't keep serving metadata for an asset that no longer exists.
7. As a developer working on any current or future route that mutates assets, I want to go through a single shared command layer, so that I can't accidentally forget to invalidate the cache when writing new code.
8. As a developer, I want authenticated asset reads (e.g. `GET /assets/{id}`) to remain uncached and always consistent with the database, so that internal/admin tooling never has to reason about cache staleness.
9. As an on-call engineer, I want the serve endpoint to keep working correctly (just without the caching benefit) if Redis is down or unreachable, so that a Redis outage never turns into an asset-serving outage.
10. As a developer maintaining this code, I want the caching decision logic (check cache, fall back to DB, populate cache, distinguish hit/miss/negative-hit) isolated in one small, testable unit, so that it can be verified without needing a real Redis instance or database.
11. As a developer maintaining this code, I want cache invalidation logic to be exercised by tests, so that a regression in invalidation (e.g. wrong cache key, missed call) is caught before it causes stale-data bugs in production.

## Implementation Decisions

- **Cache client wrapper**: A thin module exposing asset-cache operations (read metadata by `asset_id`, write positive entry, write negative entry, invalidate by `asset_id`) built on top of `tessera_sdk.infra.cache.Cache`. It owns the namespace, key format, and TTL choices, and is wired via a singleton factory exposed through a FastAPI `Depends()` helper, following the same pattern already used by `StorageFactory` and `AnalysisFactory` (including a `.reset()` for test isolation).
- **Cache key**: keyed by `asset_id` only. A single entry per asset represents either "found, here's the metadata" or "confirmed not found" — the lookup module is responsible for interpreting which case applies, so there is only one Redis key to manage (and invalidate) per asset.
- **TTLs**: positive entries (asset found) use a short-lived default TTL (on the order of minutes) as a safety net behind proactive invalidation. Negative entries (asset not found) use a shorter TTL (on the order of tens of seconds), since these are primarily meant to absorb retry storms rather than represent long-lived truth.
- **Cached data shape**: only the fields needed to serve the asset are cached (asset ID, mime type, filename) — not the full ORM row.
- **Cached asset lookup module**: a small, isolated function/class used only by the serve route. Given an `asset_id`, it checks the cache first; on a positive hit it returns metadata without touching the database; on a negative hit it returns "not found" without touching the database; on a miss, it queries `AssetRepository`, then populates the cache with a positive or negative entry accordingly, and returns the result. This is the single place where the hit/miss/negative-hit decision logic lives.
- **Asset commands (new layer)**: a new module that wraps `AssetRepository`'s create/update/delete operations. `update_asset` and `delete_asset` commands perform the repository write and then invalidate the corresponding cache entry as one unit. `create_asset` is included for interface consistency even though a brand-new asset has no existing cache entry to invalidate.
- **Route migration**: every existing route handler that currently calls `AssetRepository.update_asset` or `AssetRepository.delete_asset` directly is migrated to call the corresponding asset command instead, so there is no remaining write path that can bypass cache invalidation.
- **Scope boundary**: `AssetRepository.get_asset` itself is not changed and does not become cache-aware. Only the serve-by-signed-URL route consults the cache for reads; all other asset reads (e.g. authenticated `GET /assets/{id}`) continue to always hit Postgres directly.
- **Failure mode**: cache reads/writes fail open — if Redis is unreachable, the lookup module falls through to the database and the request succeeds as if caching were disabled, matching the existing fail-open behavior already built into `tessera_sdk.infra.cache.Cache`.

## Testing Decisions

Good tests here verify observable behavior (what gets returned, what the database/cache calls look like from the outside) rather than internal implementation details of how the cache client talks to Redis.

- **Cached asset lookup module**: unit-tested with a mocked repository and mocked cache client. Cases: cache hit (positive) returns metadata without calling the repository; cache hit (negative) returns "not found" without calling the repository; cache miss + asset exists calls the repository once and writes a positive cache entry; cache miss + asset does not exist calls the repository once and writes a negative cache entry.
- **Asset commands**: unit-tested with a mocked repository and mocked cache client. Cases: `update_asset` command calls the repository's update and then invalidates the cache entry for that `asset_id`; `delete_asset` command calls the repository's delete and then invalidates the cache entry; failure of the underlying repository call does not invalidate the cache (no partial side effects).
- **Cache client wrapper**: unit-tested with the underlying `tessera_sdk.infra.cache.Cache` mocked. Verifies the correct namespace/key is built for a given `asset_id`, and that the correct TTL is used for positive vs. negative writes.
- **Route-level regression tests**: extend the existing `/assets/serve/{payload}` router tests (following the pattern already established in `tests/app/routers/test_assets.py`, using the `client` fixture and a mocked storage backend) to confirm end-to-end behavior is unchanged from the caller's perspective — a valid signed URL still serves the asset, and a missing/malformed asset ID still returns the correct status code — regardless of whether the cache is involved.
- No new Redis infrastructure is introduced for testing. Following the existing project convention of using the mocked `Cache` dependency rather than a real Redis instance for these tests keeps them fast and deterministic; a real Redis integration/smoke test is out of scope for this PRD.

## Out of Scope

- Caching or optimizing S3 presigned URL generation.
- Caching or optimizing the actual byte-serving/streaming of asset content.
- Adding HTTP caching headers (`Cache-Control`, `ETag`, etc.) to the S3 proxy-streaming branch of the serve route.
- Making authenticated asset reads (e.g. `GET /assets/{id}`) cache-aware.
- Adding a real Redis service to the test/CI environment.
- Tuning exact TTL values based on production traffic data (initial defaults are a starting point, not a final measurement-driven decision).
- Cache warming or pre-population strategies.

## Further Notes

- This PRD originated from a `/grill-me` discussion where the core caching design (scope, invalidation strategy, negative caching, and the decision to introduce a dedicated command layer rather than making the repository or individual routes cache-aware) was already worked through; this document formalizes those decisions.
- The introduction of the command layer is a larger structural change than the caching feature itself, since it requires migrating every existing asset-mutating route. This is intentional: the whole point of the command layer is to make it structurally impossible for a write path to bypass cache invalidation, including future routes not yet written.
- Exact TTL values, and whether a real Redis-backed integration test is later worth adding, are left as implementation-time/follow-up decisions rather than blocking this PRD.
