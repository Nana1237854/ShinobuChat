from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user_id, get_reminder_service
from app.schemas.sync import ReminderSnoozeRequest
from app.services.reminder_scheduler_service import ReminderSchedulerService

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.get("/due")
def get_due_reminders(
    user_id: UUID = Depends(get_current_user_id),
    service: ReminderSchedulerService = Depends(get_reminder_service),
) -> list[dict]:
    events = service.scan_due_reminders_for_user(user_id)
    return [event.to_payload() for event in events]


@router.post("/{todo_id}/snooze")
def snooze_reminder(
    todo_id: UUID,
    body: ReminderSnoozeRequest,
    user_id: UUID = Depends(get_current_user_id),
    service: ReminderSchedulerService = Depends(get_reminder_service),
) -> dict:
    event = service.snooze(user_id, todo_id, body.minutes)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found or not owned by you.",
        )
    return event.to_payload()


@router.post("/{todo_id}/dismiss")
def dismiss_reminder(
    todo_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    service: ReminderSchedulerService = Depends(get_reminder_service),
) -> dict:
    event = service.dismiss(user_id, todo_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Todo not found or not owned by you.",
        )
    return event.to_payload()
