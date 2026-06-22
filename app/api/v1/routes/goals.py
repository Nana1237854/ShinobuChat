from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import get_current_user_id, get_goal_service
from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.schemas.goal import GoalCreate, GoalCheckinOut, GoalOut, GoalUpdate
from app.services.goal_service import GoalService

router = APIRouter(prefix="/goals", tags=["goals"])


@router.post("", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalCreate,
    user_id: UUID = Depends(get_current_user_id),
    service: GoalService = Depends(get_goal_service),
) -> GoalOut:
    return GoalOut.model_validate(service.create_goal(user_id, payload))


@router.get("", response_model=list[GoalOut])
def list_goals(
    user_id: UUID = Depends(get_current_user_id),
    status_filter: str | None = Query(default=None, alias="status"),
    include_completed: bool = False,
    service: GoalService = Depends(get_goal_service),
) -> list[GoalOut]:
    return [
        GoalOut.model_validate(g)
        for g in service.list_goals(user_id, status=status_filter, include_completed=include_completed)
    ]


@router.patch("/{goal_id}", response_model=GoalOut)
def update_goal(
    goal_id: UUID,
    payload: GoalUpdate,
    user_id: UUID = Depends(get_current_user_id),
    service: GoalService = Depends(get_goal_service),
) -> GoalOut:
    return GoalOut.model_validate(service.update_goal(user_id, goal_id, payload))


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    service: GoalService = Depends(get_goal_service),
) -> Response:
    service.delete_goal(user_id, goal_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{goal_id}/checkin", response_model=GoalCheckinOut)
def checkin_goal(
    goal_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    service: GoalService = Depends(get_goal_service),
) -> GoalCheckinOut:
    try:
        result = service.checkin_goal(user_id, goal_id)
        return GoalCheckinOut(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except AppError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/due", response_model=list[GoalCheckinOut])
def get_due_goals(
    user_id: UUID = Depends(get_current_user_id),
    service: GoalService = Depends(get_goal_service),
) -> list[GoalCheckinOut]:
    events = service.scan_due_checkins_for_user(user_id)
    return [GoalCheckinOut(**e) for e in events]
