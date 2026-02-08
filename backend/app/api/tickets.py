"""Tickets API routes."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.ticket import TicketStatus
from app.schemas.ticket import (
    TicketCreate,
    TicketUpdate,
    TicketResponse,
    TicketListResponse,
)
from app.services import ticket_service

router = APIRouter()


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    data: TicketCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new ticket."""
    ticket = await ticket_service.create_ticket(db, current_user.id, data)
    return ticket


@router.get("", response_model=TicketListResponse)
async def list_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[TicketStatus] = Query(None, alias="status"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List tickets with filters.
    
    - status: Filter by ticket status (new, processing, closed)
    - start_date: Filter by creation date start (ISO format)
    - end_date: Filter by creation date end (ISO format)
    """
    tickets, total = await ticket_service.list_tickets(
        db,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        start_date=start_date,
        end_date=end_date,
    )
    
    return TicketListResponse(
        items=[TicketResponse.model_validate(t) for t in tickets],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{ticket_no}", response_model=TicketResponse)
async def get_ticket(
    ticket_no: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a ticket by its ticket number."""
    ticket = await ticket_service.get_ticket_by_no(db, ticket_no)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )
    return ticket


@router.patch("/{ticket_no}", response_model=TicketResponse)
async def update_ticket(
    ticket_no: str,
    data: TicketUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a ticket.
    
    Can update: title, root_cause, level, status
    """
    ticket = await ticket_service.update_ticket(db, ticket_no, data)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )
    return ticket
