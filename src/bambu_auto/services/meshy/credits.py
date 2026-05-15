"""Meshy 크레딧 예산 가드 + 원장.

설계 원칙:
1. API 호출 전에 반드시 reserve() 호출 — 예산 초과면 BudgetExceeded 발생
2. 호출 성공 시 commit(), 실패 시 refund()
3. 모든 흐름이 DB에 기록되어 사후 감사 가능
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from bambu_auto.config import Budgets
from bambu_auto.storage.db import Database

LedgerStatus = Literal["reserved", "committed", "refunded"]


class BudgetExceeded(Exception):
    """예산 한도 초과로 신규 작업 거부."""


@dataclass
class CreditUsage:
    monthly_used: int
    daily_used: int
    monthly_cap: int
    daily_cap: int
    reserved_now: int

    @property
    def monthly_remaining(self) -> int:
        return max(0, self.monthly_cap - self.monthly_used - self.reserved_now)

    @property
    def daily_remaining(self) -> int:
        return max(0, self.daily_cap - self.daily_used - self.reserved_now)

    @property
    def monthly_ratio(self) -> float:
        if self.monthly_cap == 0:
            return 0.0
        return (self.monthly_used + self.reserved_now) / self.monthly_cap


class CreditGuard:
    def __init__(self, db: Database, budgets: Budgets) -> None:
        self.db = db
        self.budgets = budgets

    # ---- public API ----

    def estimate(self, operation: str) -> int:
        """작업명 → 예상 크레딧. budgets.yaml의 operation_costs 사용."""
        cost = self.budgets.operation_costs.get(operation)
        if cost is None:
            raise ValueError(f"Unknown operation '{operation}'. Add it to budgets.yaml.")
        return cost

    def usage(self) -> CreditUsage:
        """현재 월간/일간 사용량 + 예약량 조회."""
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        with self.db.connect() as conn:
            monthly = conn.execute(
                "SELECT COALESCE(SUM(credits), 0) FROM credit_ledger "
                "WHERE status = 'committed' AND ts >= ?",
                (month_start.isoformat(),),
            ).fetchone()[0]
            daily = conn.execute(
                "SELECT COALESCE(SUM(credits), 0) FROM credit_ledger "
                "WHERE status = 'committed' AND ts >= ?",
                (day_start.isoformat(),),
            ).fetchone()[0]
            reserved = conn.execute(
                "SELECT COALESCE(SUM(credits), 0) FROM credit_ledger "
                "WHERE status = 'reserved'"
            ).fetchone()[0]

        return CreditUsage(
            monthly_used=monthly,
            daily_used=daily,
            monthly_cap=self.budgets.meshy.monthly_credit_cap,
            daily_cap=self.budgets.meshy.daily_credit_cap,
            reserved_now=reserved,
        )

    def reserve(self, job_id: str, operation: str, note: str | None = None) -> int:
        """크레딧 예약. 예산 초과면 BudgetExceeded.

        Returns: ledger row id (이후 commit/refund 시 사용)
        """
        cost = self.estimate(operation)
        u = self.usage()

        # 1) hard stop
        projected_ratio = (u.monthly_used + u.reserved_now + cost) / max(u.monthly_cap, 1)
        if projected_ratio > self.budgets.meshy.hard_stop_ratio:
            raise BudgetExceeded(
                f"Monthly cap hard stop: would reach {projected_ratio:.1%} "
                f"(limit {self.budgets.meshy.hard_stop_ratio:.1%})"
            )

        # 2) reserve buffer
        if u.monthly_remaining - cost < self.budgets.meshy.reserve_buffer:
            raise BudgetExceeded(
                f"Reserve buffer breach: only {u.monthly_remaining - cost} crd left "
                f"after this op (buffer={self.budgets.meshy.reserve_buffer})"
            )

        # 3) daily cap
        if u.daily_used + u.reserved_now + cost > u.daily_cap:
            raise BudgetExceeded(
                f"Daily cap exceeded: {u.daily_used + cost}/{u.daily_cap}"
            )

        return self._write_ledger(job_id, operation, cost, "reserved", note=note)

    def commit(self, ledger_id: int, actual_credits: int | None = None,
               meshy_task_id: str | None = None) -> None:
        """예약을 확정으로 전환. 실측 크레딧 알면 반영."""
        with self.db.connect() as conn:
            if actual_credits is not None:
                conn.execute(
                    "UPDATE credit_ledger SET status='committed', credits=?, "
                    "meshy_task_id=COALESCE(?, meshy_task_id) WHERE id=?",
                    (actual_credits, meshy_task_id, ledger_id),
                )
            else:
                conn.execute(
                    "UPDATE credit_ledger SET status='committed', "
                    "meshy_task_id=COALESCE(?, meshy_task_id) WHERE id=?",
                    (meshy_task_id, ledger_id),
                )

    def refund(self, ledger_id: int, reason: str) -> None:
        """예약 환불 (실패 시)."""
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE credit_ledger SET status='refunded', note=? WHERE id=?",
                (reason, ledger_id),
            )

    def check_alerts(self) -> list[str]:
        """알림 임계치 도달 여부. 호출자가 webhook 등으로 전송."""
        u = self.usage()
        alerts: list[str] = []
        for threshold in self.budgets.meshy.alert_thresholds:
            if u.monthly_ratio >= threshold:
                alerts.append(
                    f"Meshy monthly credits at {u.monthly_ratio:.0%} "
                    f"({u.monthly_used + u.reserved_now}/{u.monthly_cap})"
                )
        return alerts

    # ---- internal ----

    def _write_ledger(self, job_id: str, operation: str, credits: int,
                      status: LedgerStatus, note: str | None = None) -> int:
        ts = datetime.now(timezone.utc).isoformat()
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO credit_ledger (ts, job_id, operation, credits, status, note) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ts, job_id, operation, credits, status, note),
            )
            return int(cur.lastrowid)
