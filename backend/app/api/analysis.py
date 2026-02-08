"""Analysis API routes."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisResult,
    ContextData,
    AnalysisListItem,
)
from app.services import analysis_service

router = APIRouter()


@router.post("", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
async def create_analysis(
    request: AnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit an alert for analysis.
    
    This endpoint:
    1. Creates a new analysis session
    2. Collects context from configured data sources
    3. Sends data to LLM for analysis
    4. Returns the complete analysis result
    """
    session = await analysis_service.perform_analysis(db, current_user.id, request)
    
    return AnalysisResponse(
        id=session.id,
        user_id=session.user_id,
        alert_content=session.alert_content,
        context_data=ContextData(**session.context_data) if session.context_data else None,
        analysis_result=AnalysisResult(**session.analysis_result) if session.analysis_result else None,
        created_at=session.created_at,
    )


@router.get("", response_model=List[AnalysisListItem])
async def list_analysis_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List analysis sessions for the current user."""
    sessions, total = await analysis_service.list_sessions(
        db, current_user.id, page, page_size
    )
    
    return [
        AnalysisListItem(
            id=s.id,
            alert_content=s.alert_content[:100] + "..." if len(s.alert_content) > 100 else s.alert_content,
            created_at=s.created_at,
            has_result=s.analysis_result is not None,
        )
        for s in sessions
    ]


@router.get("/{session_id}", response_model=AnalysisResponse)
async def get_analysis(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific analysis session."""
    session = await analysis_service.get_session_by_id(db, session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis session not found",
        )
    
    # Check ownership
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this session",
        )
    
    return AnalysisResponse(
        id=session.id,
        user_id=session.user_id,
        alert_content=session.alert_content,
        context_data=ContextData(**session.context_data) if session.context_data else None,
        analysis_result=AnalysisResult(**session.analysis_result) if session.analysis_result else None,
        created_at=session.created_at,
    )
