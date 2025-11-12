from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.dependencies import db_dependency
from src.api.schemas import RecommendationSchema
from src.core.database.crud.recommendations import get_recommendations_for_student, delete_recommendation
from src.recommendation.events.score_calculation import (
    recalculate_scores_for_all_students,
    recalculate_scores_for_student,
)


router = APIRouter()


@router.get("/by-student/{student_id}", response_model=list[RecommendationSchema])
def list_recommendations_for_student(
    student_id: UUID,
    limit: int = 10,
    db: Session = Depends(db_dependency),
) -> list[RecommendationSchema]:
    recommendations = get_recommendations_for_student(db, student_id=student_id, limit=limit)
    return [RecommendationSchema.model_validate(rec) for rec in recommendations]


@router.post("/recalculate", response_model=dict)
def recalculate_all_recommendations(
    min_score: float = 0.0,
    batch_size: int = 1000,
    db: Session = Depends(db_dependency),
) -> dict:
    stats = recalculate_scores_for_all_students(db, min_score=min_score, batch_size=batch_size)
    return stats


@router.post("/by-student/{student_id}/recalculate", response_model=dict)
def recalculate_recommendations_for_student(
    student_id: UUID,
    min_score: float = 0.0,
    db: Session = Depends(db_dependency),
) -> dict:
    stats = recalculate_scores_for_student(db, student_id=student_id, min_score=min_score)
    return stats


@router.delete("/{recommendation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recommendation_item(recommendation_id: int, db: Session = Depends(db_dependency)) -> None:
    deleted = delete_recommendation(db, recommendation_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")

