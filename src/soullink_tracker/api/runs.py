"""Run management API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..db.models import Run
from .schemas import RunCreate, RunResponse, RunListResponse, ProblemDetails

router = APIRouter(prefix="/v1/runs", tags=["runs"])


@router.post(
    "",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Run created successfully"},
        422: {"model": ProblemDetails, "description": "Validation error"},
    },
)
def create_run(run_data: RunCreate, db: Session = Depends(get_db)) -> RunResponse:
    """
    Create a new SoulLink run.

    This endpoint is typically used by administrators to set up new runs.
    The rules_json field can contain custom game rules and configurations.
    """
    # Create new run
    run = Run(name=run_data.name, rules_json=run_data.rules_json)

    db.add(run)
    db.commit()
    db.refresh(run)

    return RunResponse.model_validate(run)


@router.get(
    "",
    response_model=RunListResponse,
    responses={200: {"description": "List of runs retrieved successfully"}},
)
def list_runs(db: Session = Depends(get_db)) -> RunListResponse:
    """
    List all SoulLink runs.

    Returns a list of all runs in the system, ordered by creation date (newest first).
    """
    runs = db.query(Run).order_by(Run.created_at.desc()).all()

    return RunListResponse(runs=[RunResponse.model_validate(run) for run in runs])


@router.get(
    "/{run_id}",
    response_model=RunResponse,
    responses={
        200: {"description": "Run retrieved successfully"},
        404: {"model": ProblemDetails, "description": "Run not found"},
        422: {"model": ProblemDetails, "description": "Invalid run ID format"},
    },
)
def get_run(run_id: UUID, db: Session = Depends(get_db)) -> RunResponse:
    """
    Get details of a specific SoulLink run.

    Returns complete information about the run including its configuration
    and rules. Does not include players or encounters - use separate endpoints
    for that data.
    """
    run = db.query(Run).filter(Run.id == run_id).first()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found"
        )

    return RunResponse.model_validate(run)
