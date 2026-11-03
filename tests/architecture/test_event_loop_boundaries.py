"""Event-loop guard, provided by tessera_sdk.testing.transaction_guards.

Synchronous database access inside ``async def`` runs on the event loop and
stalls every request in the process while it waits (linden-api SDD 0012).
``async_database_access`` starts from the violations listed in
``transaction_baseline.json``; each fix removes its entry. Regenerate it with
``UPDATE_TRANSACTION_BASELINE=1 pytest tests/architecture``.
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
)


@pytest.mark.parametrize("rule", EVENT_LOOP_RULE_NAMES)
def test_event_loop_rule_matches_baseline(rule):
    assert_matches_baseline(CONFIG, rule)
