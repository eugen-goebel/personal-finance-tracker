"""Savings Goals Agent — manage user savings targets and track progress."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from db.models import SavingsGoal


@dataclass
class GoalProgress:
    """Computed progress metrics for a savings goal."""

    progress_pct: float
    remaining_amount: float
    days_left: int | None
    monthly_contribution_needed: float | None


class SavingsGoalsAgent:
    """CRUD and progress maths for ``SavingsGoal`` records."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_goal(
        self,
        name: str,
        target_amount: float,
        target_date: date | None = None,
        current_amount: float = 0.0,
    ) -> SavingsGoal:
        if target_amount <= 0:
            raise ValueError("target_amount must be positive")
        if current_amount < 0:
            raise ValueError("current_amount cannot be negative")

        existing = self.db.query(SavingsGoal).filter(SavingsGoal.name == name).first()
        if existing:
            raise ValueError(f"A goal named '{name}' already exists")

        goal = SavingsGoal(
            name=name,
            target_amount=target_amount,
            current_amount=current_amount,
            target_date=target_date,
        )
        self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)
        return goal

    def list_goals(self) -> list[SavingsGoal]:
        return self.db.query(SavingsGoal).order_by(SavingsGoal.created_at).all()

    def get_goal(self, goal_id: int) -> SavingsGoal | None:
        return self.db.get(SavingsGoal, goal_id)

    def update_goal(
        self,
        goal_id: int,
        *,
        name: str | None = None,
        target_amount: float | None = None,
        current_amount: float | None = None,
        target_date: date | None = None,
        clear_target_date: bool = False,
    ) -> SavingsGoal | None:
        goal = self.get_goal(goal_id)
        if goal is None:
            return None

        if name is not None:
            goal.name = name
        if target_amount is not None:
            if target_amount <= 0:
                raise ValueError("target_amount must be positive")
            goal.target_amount = target_amount
        if current_amount is not None:
            if current_amount < 0:
                raise ValueError("current_amount cannot be negative")
            goal.current_amount = current_amount
        if clear_target_date:
            goal.target_date = None
        elif target_date is not None:
            goal.target_date = target_date

        self.db.commit()
        self.db.refresh(goal)
        return goal

    def contribute(self, goal_id: int, amount: float) -> SavingsGoal | None:
        """Add ``amount`` to ``current_amount`` of the goal."""
        if amount <= 0:
            raise ValueError("contribution must be positive")
        goal = self.get_goal(goal_id)
        if goal is None:
            return None
        goal.current_amount += amount
        self.db.commit()
        self.db.refresh(goal)
        return goal

    def delete_goal(self, goal_id: int) -> bool:
        goal = self.get_goal(goal_id)
        if goal is None:
            return False
        self.db.delete(goal)
        self.db.commit()
        return True

    # ------------------------------------------------------------------
    # Progress maths
    # ------------------------------------------------------------------

    @staticmethod
    def compute_progress(goal: SavingsGoal, *, today: date | None = None) -> GoalProgress:
        today = today or datetime.now(timezone.utc).date()

        if goal.target_amount <= 0:
            progress_pct = 0.0
        else:
            progress_pct = min(100.0, max(0.0, (goal.current_amount / goal.target_amount) * 100))

        remaining_amount = max(goal.target_amount - goal.current_amount, 0.0)

        days_left: int | None = None
        monthly_needed: float | None = None
        if goal.target_date is not None:
            days_left = (goal.target_date - today).days
            if days_left > 0 and remaining_amount > 0:
                # Use months >= 1 to avoid huge spikes near the deadline
                months_left = max(days_left / 30, 1.0)
                monthly_needed = round(remaining_amount / months_left, 2)
            else:
                monthly_needed = None  # past due, on track, or already met

        return GoalProgress(
            progress_pct=round(progress_pct, 2),
            remaining_amount=round(remaining_amount, 2),
            days_left=days_left,
            monthly_contribution_needed=monthly_needed,
        )
