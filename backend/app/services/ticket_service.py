"""Ticket service."""
from datetime import datetime, date
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, and_
from app.models.ticket import Ticket, TicketStatus, TicketLevel
from app.schemas.ticket import TicketCreate, TicketUpdate


async def generate_ticket_no(db: AsyncSession) -> str:
    """
    Generate a unique ticket number.
    Format: OC{YYYYMMDD}{4-digit sequence}
    Example: OC2024020800001
    """
    today = date.today()
    date_str = today.strftime("%Y%m%d")
    prefix = f"OC{date_str}"
    
    # Find the latest ticket number for today
    result = await db.execute(
        select(Ticket)
        .where(Ticket.ticket_no.like(f"{prefix}%"))
        .order_by(desc(Ticket.ticket_no))
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    
    if latest:
        # Extract sequence number and increment
        seq = int(latest.ticket_no[-5:]) + 1
    else:
        seq = 1
    
    return f"{prefix}{seq:05d}"


async def create_ticket(
    db: AsyncSession,
    handler_id: int,
    data: TicketCreate,
) -> Ticket:
    """Create a new ticket."""
    ticket_no = await generate_ticket_no(db)
    
    ticket = Ticket(
        ticket_no=ticket_no,
        session_id=data.session_id,
        handler_id=handler_id,
        title=data.title,
        root_cause=data.root_cause,
        level=data.level,
        status=TicketStatus.NEW,
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return ticket


async def get_ticket_by_no(
    db: AsyncSession,
    ticket_no: str,
) -> Optional[Ticket]:
    """Get a ticket by its ticket number."""
    result = await db.execute(
        select(Ticket).where(Ticket.ticket_no == ticket_no)
    )
    return result.scalar_one_or_none()


async def list_tickets(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[TicketStatus] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Tuple[List[Ticket], int]:
    """
    List tickets with filters.
    
    Args:
        db: Database session
        page: Page number (1-indexed)
        page_size: Items per page
        status_filter: Filter by status
        start_date: Filter by creation date start
        end_date: Filter by creation date end
    
    Returns:
        Tuple of (tickets, total_count)
    """
    # Build filters
    filters = []
    if status_filter:
        filters.append(Ticket.status == status_filter)
    if start_date:
        filters.append(Ticket.created_at >= start_date)
    if end_date:
        filters.append(Ticket.created_at <= end_date)
    
    # Count total
    count_query = select(func.count()).select_from(Ticket)
    if filters:
        count_query = count_query.where(and_(*filters))
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    # Get paginated results
    offset = (page - 1) * page_size
    query = select(Ticket).order_by(desc(Ticket.created_at)).offset(offset).limit(page_size)
    if filters:
        query = query.where(and_(*filters))
    
    result = await db.execute(query)
    tickets = result.scalars().all()
    
    return tickets, total


async def update_ticket(
    db: AsyncSession,
    ticket_no: str,
    data: TicketUpdate,
) -> Optional[Ticket]:
    """Update a ticket."""
    ticket = await get_ticket_by_no(db, ticket_no)
    if not ticket:
        return None
    
    update_data = data.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(ticket, key, value)
    
    # If status changed to closed, set closed_at
    if data.status == TicketStatus.CLOSED and ticket.closed_at is None:
        ticket.closed_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(ticket)
    return ticket
