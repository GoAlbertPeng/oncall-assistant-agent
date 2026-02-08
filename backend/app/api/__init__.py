"""API routes."""
from fastapi import APIRouter
from app.api import auth, datasources, analysis, tickets

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(datasources.router, prefix="/datasources", tags=["DataSources"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["Analysis"])
api_router.include_router(tickets.router, prefix="/tickets", tags=["Tickets"])
