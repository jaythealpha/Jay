from pathlib import Path

import pytest

from bambu_auto.config import Budgets, MeshyBudget
from bambu_auto.services.meshy.credits import BudgetExceeded, CreditGuard
from bambu_auto.storage.db import Database


@pytest.fixture
def guard(tmp_path: Path) -> CreditGuard:
    db = Database(tmp_path / "test.db")
    budgets = Budgets(
        meshy=MeshyBudget(
            monthly_credit_cap=100,
            daily_credit_cap=50,
            reserve_buffer=10,
            hard_stop_ratio=0.95,
            alert_thresholds=[0.7, 0.9],
        ),
        operation_costs={"image_to_3d_untextured": 5, "image_to_3d_textured": 15},
    )
    return CreditGuard(db, budgets)


def test_reserve_and_commit_tracks_usage(guard: CreditGuard) -> None:
    lid = guard.reserve("job1", "image_to_3d_untextured")
    assert guard.usage().reserved_now == 5
    assert guard.usage().monthly_used == 0
    guard.commit(lid, meshy_task_id="task_abc")
    assert guard.usage().reserved_now == 0
    assert guard.usage().monthly_used == 5


def test_refund_releases_reservation(guard: CreditGuard) -> None:
    lid = guard.reserve("job1", "image_to_3d_textured")
    guard.refund(lid, reason="submit failed")
    u = guard.usage()
    assert u.reserved_now == 0
    assert u.monthly_used == 0


def test_daily_cap_enforced(guard: CreditGuard) -> None:
    for i in range(10):
        guard.commit(guard.reserve(f"j{i}", "image_to_3d_untextured"))
    # 10 * 5 = 50 -> at daily cap
    with pytest.raises(BudgetExceeded, match="Daily cap"):
        guard.reserve("j11", "image_to_3d_untextured")


def test_hard_stop_blocks_at_threshold(tmp_path: Path) -> None:
    # 일간 캡을 크게 잡아서 월간 hard_stop만 격리 테스트
    db = Database(tmp_path / "hard_stop.db")
    budgets = Budgets(
        meshy=MeshyBudget(
            monthly_credit_cap=100,
            daily_credit_cap=999,
            reserve_buffer=10,
            hard_stop_ratio=0.95,
        ),
        operation_costs={"image_to_3d_textured": 15},
    )
    g = CreditGuard(db, budgets)
    # 6 * 15 = 90 committed. Next 15 -> 105 > 95 (hard stop)
    for i in range(6):
        g.commit(g.reserve(f"j{i}", "image_to_3d_textured"))
    with pytest.raises(BudgetExceeded, match="hard stop|Reserve buffer"):
        g.reserve("jnext", "image_to_3d_textured")


def test_unknown_operation_raises(guard: CreditGuard) -> None:
    with pytest.raises(ValueError, match="Unknown operation"):
        guard.reserve("job1", "made_up_op")
