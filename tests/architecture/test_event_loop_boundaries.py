"""Event-loop guard, provided by tessera_sdk.testing.transaction_guards.

Synchronous database access inside ``async def`` runs on the event loop and
stalls every request in the process while it waits (linden-api SDD 0012).
``async_database_access`` is fully enforced; the only exceptions are the
reasoned entries in ``async_db_allowlist``.
"""

from pathlib import Path

import pytest
from tessera_sdk.testing.transaction_guards import (
    EVENT_LOOP_RULE_NAMES,
    TransactionGuardConfig,
    assert_matches_baseline,
)

CONFIG = TransactionGuardConfig(
    app_root=Path(__file__).parents[2] / "app",
    baseline_path=Path(__file__).with_name("transaction_baseline.json"),
    # async def functions that must await and run their database work via
    # run_in_threadpool (SDD 0012 option 4): (path relative to app/, function)
    # -> reason.
    async_db_allowlist={
        ("routers/assets.py", "serve_asset_via_signed_url"): (
            "streams the S3 object through httpx.AsyncClient; the asset lookup "
            "and presign run in the threadpool and release the connection first"
        ),
    },
)


@pytest.mark.parametrize("rule", EVENT_LOOP_RULE_NAMES)
def test_event_loop_rule_matches_baseline(rule):
    assert_matches_baseline(CONFIG, rule)
