"""Savings goal API routes — CRUD plus a contribute endpoint."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from agents.savings_goals import SavingsGoalsAgent
from api.schemas import (
    GoalContribution,
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    MessageResponse,
)
from db.database import get_db
from db.models import SavingsGoal

router = APIRouter(prefix="/api/goals", tags=["Savings Goals"])


def _to_response(goal: SavingsGoal) -> dict:
    progress = SavingsGoalsAgent.compute_progress(goal)
    return {
        "id": goal.id,
        "name": goal.name,
        "target_amount": goal.target_amount,
        "current_amount": goal.current_amount,
        "target_date": goal.target_date,
        "progress": {
            "progress_pct": progress.progress_pct,
            "remaining_amount": progress.remaining_amount,
            "days_left": progress.days_left,
            "monthly_contribution_needed": progress.monthly_contribution_needed,
        },
    }


@router.post("/", response_model=GoalResponse, status_code=201)
def create_goal(data: GoalCreate, db: Session = Depends(get_db)):
    agent = SavingsGoalsAgent(db)
    try:
        goal = agent.create_goal(
            name=data.name,
            target_amount=data.target_amount,
            target_date=data.target_date,
            current_amount=data.current_amount,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_response(goal)


@router.get("/", response_model=list[GoalResponse])
def list_goals(db: Session = Depends(get_db)):
    agent = SavingsGoalsAgent(db)
    return [_to_response(g) for g in agent.list_goals()]


@router.get("/{goal_id}", response_model=GoalResponse)
def get_goal(goal_id: int, db: Session = Depends(get_db)):
    agent = SavingsGoalsAgent(db)
    goal = agent.get_goal(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Savings goal not found")
    return _to_response(goal)


@router.put("/{goal_id}", response_model=GoalResponse)
def update_goal(goal_id: int, data: GoalUpdate, db: Session = Depends(get_db)):
    agent = SavingsGoalsAgent(db)
    try:
        goal = agent.update_goal(
            goal_id,
            name=data.name,
            target_amount=data.target_amount,
            current_amount=data.current_amount,
            target_date=data.target_date,
            clear_target_date=data.clear_target_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if goal is None:
        raise HTTPException(status_code=404, detail="Savings goal not found")
    return _to_response(goal)


@router.post("/{goal_id}/contribute", response_model=GoalResponse)
def contribute(goal_id: int, data: GoalContribution, db: Session = Depends(get_db)):
    agent = SavingsGoalsAgent(db)
    try:
        goal = agent.contribute(goal_id, data.amount)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if goal is None:
        raise HTTPException(status_code=404, detail="Savings goal not found")
    return _to_response(goal)


@router.delete("/{goal_id}", response_model=MessageResponse)
def delete_goal(goal_id: int, db: Session = Depends(get_db)):
    agent = SavingsGoalsAgent(db)
    if not agent.delete_goal(goal_id):
        raise HTTPException(status_code=404, detail="Savings goal not found")
    return {"message": "Savings goal deleted"}
