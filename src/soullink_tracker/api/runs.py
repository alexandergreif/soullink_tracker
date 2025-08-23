"""Run management API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ..repositories.dependencies import get_run_repository
from ..repositories.interfaces import RunRepository
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
async def create_run(
    run_data: RunCreate,
    run_repo: RunRepository = Depends(get_run_repository)
) -> RunResponse:
    """
    Create a new SoulLink run.

    This endpoint is typically used by administrators to set up new runs.
    The rules_json field can contain custom game rules and configurations.
    The password will be hashed and stored securely if provided.
    """
    # Hash the password if provided (kept for backwards compatibility)
    # TODO: Move password hashing to repository layer or service layer
    rules_json = run_data.rules_json.copy() if run_data.rules_json else {}
    
    if run_data.password:
        from ..auth.security import hash_password
        password_salt, password_hash = hash_password(run_data.password)
        rules_json["_password_salt"] = password_salt
        rules_json["_password_hash"] = password_hash

    # Create new run using repository
    run = await run_repo.create(
        name=run_data.name,
        rules_json=rules_json,
    )

    return RunResponse.model_validate(run)


@router.get(
    "",
    response_model=RunListResponse,
    responses={200: {"description": "List of runs retrieved successfully"}},
)
async def list_runs(
    run_repo: RunRepository = Depends(get_run_repository)
) -> RunListResponse:
    """
    List all SoulLink runs.

    Returns a list of all runs in the system, ordered by creation date (newest first).
    """
    runs = await run_repo.list_all()

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
async def get_run(
    run_id: UUID,
    run_repo: RunRepository = Depends(get_run_repository)
) -> RunResponse:
    """
    Get details of a specific SoulLink run.

    Returns complete information about the run including its configuration
    and rules. Does not include players or encounters - use separate endpoints
    for that data.
    """
    run = await run_repo.get_by_id(run_id)

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run not found"
        )

    return RunResponse.model_validate(run)
