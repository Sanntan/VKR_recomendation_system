from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.dependencies import db_dependency
from src.api.schemas import FeedbackCreateSchema, FeedbackResponseSchema
from src.core.database.crud.feedback import create_feedback


router = APIRouter()


@router.post("", response_model=FeedbackResponseSchema, status_code=status.HTTP_201_CREATED)
def submit_feedback(payload: FeedbackCreateSchema, db: Session = Depends(db_dependency)) -> FeedbackResponseSchema:
    feedback = create_feedback(db, student_id=payload.student_id, rating=payload.rating, comment=payload.comment)
    if not feedback:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Feedback not created")
    return FeedbackResponseSchema(
        id=feedback.id,
        student_id=feedback.student_id,
        rating=feedback.rating,
        comment=feedback.comment,
        created_at=feedback.created_at,
    )

