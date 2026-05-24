"""Tests for the savings goals agent and REST API."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from agents.savings_goals import GoalProgress, SavingsGoalsAgent
from api.main import app
from db.database import Base, get_db, get_engine
from db.models import SavingsGoal
from sqlalchemy.orm import sessionmaker


# ---------------------------------------------------------------------------
# Agent-level tests
# ---------------------------------------------------------------------------

class TestSavingsGoalsAgent:
    def test_create_goal(self, db):
        agent = SavingsGoalsAgent(db)
        goal = agent.create_goal(
            name="Vacation",
            target_amount=3000.0,
            target_date=date(2026, 8, 1),
            current_amount=500.0,
        )
        assert goal.id is not None
        assert goal.name == "Vacation"
        assert goal.target_amount == 3000.0
        assert goal.current_amount == 500.0

    def test_create_rejects_zero_target(self, db):
        agent = SavingsGoalsAgent(db)
        with pytest.raises(ValueError):
            agent.create_goal(name="Bad", target_amount=0)

    def test_create_rejects_negative_current(self, db):
        agent = SavingsGoalsAgent(db)
        with pytest.raises(ValueError):
            agent.create_goal(name="Bad", target_amount=100, current_amount=-1)

    def test_duplicate_name_rejected(self, db):
        agent = SavingsGoalsAgent(db)
        agent.create_goal(name="Laptop", target_amount=1500)
        with pytest.raises(ValueError):
            agent.create_goal(name="Laptop", target_amount=1500)

    def test_contribute_adds_to_current(self, db):
        agent = SavingsGoalsAgent(db)
        goal = agent.create_goal(name="Laptop", target_amount=1500, current_amount=100)
        updated = agent.contribute(goal.id, 50.0)
        assert updated.current_amount == 150.0

    def test_contribute_can_exceed_target(self, db):
        agent = SavingsGoalsAgent(db)
        goal = agent.create_goal(name="Tight", target_amount=100, current_amount=90)
        updated = agent.contribute(goal.id, 50.0)
        # Allowed — user over-saved. progress_pct should clamp to 100.
        assert updated.current_amount == 140.0
        progress = SavingsGoalsAgent.compute_progress(updated)
        assert progress.progress_pct == 100.0
        assert progress.remaining_amount == 0.0

    def test_update_clears_target_date(self, db):
        agent = SavingsGoalsAgent(db)
        goal = agent.create_goal(name="Open", target_amount=500, target_date=date(2026, 12, 31))
        updated = agent.update_goal(goal.id, clear_target_date=True)
        assert updated.target_date is None

    def test_delete(self, db):
        agent = SavingsGoalsAgent(db)
        goal = agent.create_goal(name="Tmp", target_amount=10)
        assert agent.delete_goal(goal.id) is True
        assert agent.get_goal(goal.id) is None

    def test_delete_missing_returns_false(self, db):
        agent = SavingsGoalsAgent(db)
        assert agent.delete_goal(9999) is False


# ---------------------------------------------------------------------------
# Progress maths
# ---------------------------------------------------------------------------

class TestComputeProgress:
    def test_open_ended_goal_has_no_deadline_fields(self):
        goal = SavingsGoal(name="Open", target_amount=1000, current_amount=200)
        p = SavingsGoalsAgent.compute_progress(goal, today=date(2026, 5, 1))
        assert p.progress_pct == 20.0
        assert p.remaining_amount == 800.0
        assert p.days_left is None
        assert p.monthly_contribution_needed is None

    def test_past_due_goal_returns_negative_days(self):
        goal = SavingsGoal(
            name="Late", target_amount=500, current_amount=100,
            target_date=date(2026, 1, 1),
        )
        p = SavingsGoalsAgent.compute_progress(goal, today=date(2026, 3, 1))
        assert p.days_left == -59
        # Past due → no monthly contribution suggestion
        assert p.monthly_contribution_needed is None

    def test_progress_clamped_at_100(self):
        goal = SavingsGoal(name="Over", target_amount=100, current_amount=200)
        p = SavingsGoalsAgent.compute_progress(goal)
        assert p.progress_pct == 100.0

    def test_monthly_contribution_computed(self):
        # 2000 target, 500 saved, 90 days left → 1500 / ~3 months
        goal = SavingsGoal(
            name="Plan", target_amount=2000, current_amount=500,
            target_date=date(2026, 8, 1),
        )
        p = SavingsGoalsAgent.compute_progress(goal, today=date(2026, 5, 3))
        assert p.days_left == 90
        # 1500 / (90/30) = 500
        assert p.monthly_contribution_needed == 500.0

    def test_returns_dataclass_type(self):
        goal = SavingsGoal(name="X", target_amount=10, current_amount=0)
        p = SavingsGoalsAgent.compute_progress(goal)
        assert isinstance(p, GoalProgress)


# ---------------------------------------------------------------------------
# API smoke tests
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client(tmp_path):
    """A TestClient that talks to an isolated SQLite file for this test."""
    db_path = tmp_path / "api.db"
    engine = get_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    def _override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


class TestSavingsGoalsAPI:
    def test_full_lifecycle(self, api_client):
        # Create
        payload = {
            "name": "Vacation",
            "target_amount": 3000,
            "current_amount": 500,
            "target_date": (date.today() + timedelta(days=90)).isoformat(),
        }
        r = api_client.post("/api/goals/", json=payload)
        assert r.status_code == 201
        body = r.json()
        assert body["id"] is not None
        assert body["progress"]["progress_pct"] == pytest.approx(500 / 3000 * 100, rel=1e-2)

        goal_id = body["id"]

        # List
        r = api_client.get("/api/goals/")
        assert r.status_code == 200
        assert len(r.json()) == 1

        # Contribute
        r = api_client.post(f"/api/goals/{goal_id}/contribute", json={"amount": 250})
        assert r.status_code == 200
        assert r.json()["current_amount"] == 750

        # Get
        r = api_client.get(f"/api/goals/{goal_id}")
        assert r.status_code == 200
        assert r.json()["current_amount"] == 750

        # Update — change target
        r = api_client.put(f"/api/goals/{goal_id}", json={"target_amount": 4000})
        assert r.status_code == 200
        assert r.json()["target_amount"] == 4000

        # Delete
        r = api_client.delete(f"/api/goals/{goal_id}")
        assert r.status_code == 200
        r = api_client.get(f"/api/goals/{goal_id}")
        assert r.status_code == 404

    def test_invalid_target_rejected_by_api(self, api_client):
        r = api_client.post("/api/goals/", json={"name": "Bad", "target_amount": 0})
        assert r.status_code == 422  # Pydantic validator rejects before service

    def test_duplicate_name_returns_400(self, api_client):
        api_client.post("/api/goals/", json={"name": "Dup", "target_amount": 100})
        r = api_client.post("/api/goals/", json={"name": "Dup", "target_amount": 200})
        assert r.status_code == 400
        assert "already exists" in r.json()["detail"]
