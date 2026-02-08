"""Analysis API routes with streaming support."""
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from app.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.ticket import Ticket
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisResult,
    ContextData,
    AnalysisListItem,
    IntentResult,
    ConversationMessage,
    ContinueAnalysisRequest,
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
    Submit an alert for analysis (non-streaming).
    
    This endpoint performs the full analysis synchronously.
    For streaming analysis, use POST /api/analysis/stream
    """
    session = await analysis_service.perform_analysis(db, current_user.id, request)
    return _format_response(session)


@router.post("/stream")
async def create_analysis_stream(
    request: AnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit an alert for streaming analysis.
    
    Returns Server-Sent Events (SSE) stream with analysis progress:
    - stage_start: A new stage is starting
    - stage_progress: Progress update within a stage
    - stage_complete: A stage has completed
    - message: A message/content to display
    - error: An error occurred
    - cancelled: Analysis was cancelled
    - done: Analysis complete
    
    Stages:
    1. intent_understanding - Parse and understand the alert
    2. data_collection - Collect logs and metrics from data sources
    3. llm_analysis - Analyze with LLM
    """
    from app.database import AsyncSessionLocal
    
    # Create session first (use the request-scoped db)
    session = await analysis_service.create_analysis_session(
        db, current_user.id, request.alert_content
    )
    session.add_message("user", request.alert_content)
    await db.commit()
    
    session_id = session.id
    alert_content = request.alert_content
    time_range = request.time_range_minutes
    
    async def event_generator():
        # Create a new database session for the streaming generator
        # because the request-scoped session will be closed when the handler returns
        async with AsyncSessionLocal() as stream_db:
            try:
                # Re-fetch the session with the new db connection
                stream_session = await analysis_service.get_session_by_id(stream_db, session_id)
                if not stream_session:
                    yield f"data: {json.dumps({'event': 'error', 'content': 'Session not found'})}\n\n"
                    return
                
                stream_request = AnalysisRequest(
                    alert_content=alert_content,
                    time_range_minutes=time_range,
                )
                
                async for event in analysis_service.stream_analysis(stream_db, stream_session, stream_request):
                    yield event
            except Exception as e:
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'event': 'error', 'content': f'Stream error: {str(e)}'})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-Id": str(session_id),
        },
    )


@router.post("/{session_id}/continue")
async def continue_analysis(
    session_id: int,
    request: ContinueAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Continue analysis with a follow-up question.
    
    Returns SSE stream with the response.
    """
    from app.database import AsyncSessionLocal
    
    session = await analysis_service.get_session_by_id(db, session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis session not found",
        )
    
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this session",
        )
    
    user_message = request.message
    
    async def event_generator():
        async with AsyncSessionLocal() as stream_db:
            try:
                stream_session = await analysis_service.get_session_by_id(stream_db, session_id)
                if not stream_session:
                    yield f"data: {json.dumps({'event': 'error', 'content': 'Session not found'})}\n\n"
                    return
                
                async for event in analysis_service.continue_analysis(stream_db, stream_session, user_message):
                    yield event
            except Exception as e:
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'event': 'error', 'content': f'Stream error: {str(e)}'})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/{session_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_analysis(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel an ongoing analysis."""
    session = await analysis_service.get_session_by_id(db, session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis session not found",
        )
    
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this session",
        )
    
    cancelled = analysis_service.cancel_session(session_id)
    
    if cancelled:
        session.status = "cancelled"
        session.add_message("system", "分析已被用户取消")
        await db.commit()
        return {"status": "cancelled", "message": "Analysis cancelled"}
    else:
        return {"status": "not_active", "message": "Session is not actively being analyzed"}


@router.post("/{session_id}/reanalyze")
async def reanalyze(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Re-analyze an existing session.
    
    Returns SSE stream with analysis progress.
    """
    session = await analysis_service.get_session_by_id(db, session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis session not found",
        )
    
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this session",
        )
    
    from app.database import AsyncSessionLocal
    
    # Reset session for re-analysis
    session.status = "pending"
    session.analysis_result = None
    session.add_message("user", f"[重新分析] {session.alert_content}")
    await db.commit()
    
    alert_content = session.alert_content
    
    async def event_generator():
        async with AsyncSessionLocal() as stream_db:
            try:
                stream_session = await analysis_service.get_session_by_id(stream_db, session_id)
                if not stream_session:
                    yield f"data: {json.dumps({'event': 'error', 'content': 'Session not found'})}\n\n"
                    return
                
                request = AnalysisRequest(
                    alert_content=alert_content,
                    time_range_minutes=30,
                )
                
                async for event in analysis_service.stream_analysis(stream_db, stream_session, request):
                    yield event
            except Exception as e:
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'event': 'error', 'content': f'Stream error: {str(e)}'})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.delete("/{session_id}", status_code=status.HTTP_200_OK)
async def delete_analysis(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an analysis session."""
    session = await analysis_service.get_session_by_id(db, session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis session not found",
        )
    
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this session",
        )
    
    # First, unlink any tickets associated with this session
    await db.execute(
        update(Ticket).where(Ticket.session_id == session_id).values(session_id=None)
    )
    
    await db.delete(session)
    await db.commit()
    
    return {"status": "deleted", "message": "Analysis session deleted"}


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
            status=s.status or "pending",
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
    """Get a specific analysis session with full conversation history."""
    session = await analysis_service.get_session_by_id(db, session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis session not found",
        )
    
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this session",
        )
    
    return _format_response(session)


def _format_response(session) -> AnalysisResponse:
    """Format an AnalysisSession as AnalysisResponse."""
    messages = []
    if session.messages:
        for msg in session.messages:
            messages.append(ConversationMessage(
                role=msg.get("role", "assistant"),
                content=msg.get("content", ""),
                timestamp=msg.get("timestamp", ""),
                stage=msg.get("stage"),
                data=msg.get("data"),
            ))
    
    return AnalysisResponse(
        id=session.id,
        user_id=session.user_id,
        alert_content=session.alert_content,
        status=session.status or "pending",
        current_stage=session.current_stage,
        intent=IntentResult(**session.intent) if session.intent else None,
        context_data=ContextData(**session.context_data) if session.context_data else None,
        analysis_result=AnalysisResult(**session.analysis_result) if session.analysis_result else None,
        messages=messages,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )
