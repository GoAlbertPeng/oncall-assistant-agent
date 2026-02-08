"""DataSource API routes."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.api.auth import get_current_user
from app.schemas.datasource import (
    DataSourceCreate, 
    DataSourceUpdate, 
    DataSourceResponse,
    DataSourceTestResponse,
)
from app.services import datasource_service

router = APIRouter()


@router.get("", response_model=List[DataSourceResponse])
async def list_datasources(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get all data sources."""
    return await datasource_service.get_all_datasources(db)


@router.post("", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_datasource(
    data: DataSourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Create a new data source."""
    return await datasource_service.create_datasource(db, data)


@router.get("/{datasource_id}", response_model=DataSourceResponse)
async def get_datasource(
    datasource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get a data source by ID."""
    datasource = await datasource_service.get_datasource_by_id(db, datasource_id)
    if not datasource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found",
        )
    return datasource


@router.put("/{datasource_id}", response_model=DataSourceResponse)
async def update_datasource(
    datasource_id: int,
    data: DataSourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Update a data source."""
    datasource = await datasource_service.update_datasource(db, datasource_id, data)
    if not datasource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found",
        )
    return datasource


@router.delete("/{datasource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_datasource(
    datasource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Delete a data source."""
    success = await datasource_service.delete_datasource(db, datasource_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found",
        )


@router.post("/{datasource_id}/test", response_model=DataSourceTestResponse)
async def test_datasource(
    datasource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Test connection to a data source."""
    datasource = await datasource_service.get_datasource_by_id(db, datasource_id)
    if not datasource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found",
        )
    return await datasource_service.test_datasource_connection(datasource)
