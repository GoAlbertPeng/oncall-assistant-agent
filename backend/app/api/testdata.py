"""Test data API routes."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.api.auth import get_current_user
from app.services import test_data_service

router = APIRouter()


# Request/Response schemas
class TestLogCreate(BaseModel):
    """Schema for creating a test log."""
    timestamp: Optional[str] = None
    level: str = "INFO"
    message: str
    source: str = "test-service"
    index: str = "test-logs"


class TestLogResponse(BaseModel):
    """Response schema for test log."""
    id: str
    timestamp: str
    level: str
    message: str
    source: str
    index: str


class TestMetricCreate(BaseModel):
    """Schema for creating a test metric."""
    timestamp: Optional[str] = None
    name: str
    labels: dict = {}
    value: float
    type: str = "gauge"


class TestMetricResponse(BaseModel):
    """Response schema for test metric."""
    id: str
    timestamp: str
    name: str
    labels: dict
    value: float
    type: str


class TestDataStats(BaseModel):
    """Statistics about test data."""
    logs_total: int
    logs_by_level: dict
    metrics_total: int
    metrics_by_name: dict


class RegenerateResponse(BaseModel):
    """Response for regenerate action."""
    logs_count: int
    metrics_count: int


class TestDataSourceConfig(BaseModel):
    """Configuration for test data sources."""
    logs: dict
    prometheus: dict


# Log endpoints
@router.get("/logs", response_model=List[TestLogResponse])
async def list_test_logs(
    query: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = 100,
    current_user=Depends(get_current_user),
):
    """Get test log entries from Elasticsearch."""
    return await test_data_service.get_test_logs(query=query, level=level, limit=limit)


@router.post("/logs", response_model=TestLogResponse, status_code=status.HTTP_201_CREATED)
async def create_test_log(
    data: TestLogCreate,
    current_user=Depends(get_current_user),
):
    """Add a new test log entry to Elasticsearch."""
    return await test_data_service.add_test_log(data.model_dump())


@router.delete("/logs/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_log(
    log_id: str,
    current_user=Depends(get_current_user),
):
    """Delete a test log entry from Elasticsearch."""
    success = await test_data_service.delete_test_log(log_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Log entry not found",
        )


@router.delete("/logs", status_code=status.HTTP_204_NO_CONTENT)
async def clear_test_logs(current_user=Depends(get_current_user)):
    """Clear all test logs from Elasticsearch."""
    await test_data_service.clear_test_logs()


# Metric endpoints
@router.get("/metrics", response_model=List[TestMetricResponse])
async def list_test_metrics(
    name: Optional[str] = None,
    limit: int = 100,
    current_user=Depends(get_current_user),
):
    """Get test metric entries from Prometheus."""
    return await test_data_service.get_test_metrics(name=name, limit=limit)


@router.post("/metrics", response_model=TestMetricResponse, status_code=status.HTTP_201_CREATED)
async def create_test_metric(
    data: TestMetricCreate,
    current_user=Depends(get_current_user),
):
    """Add a new test metric to Prometheus via Pushgateway."""
    return await test_data_service.add_test_metric(data.model_dump())


@router.delete("/metrics/{metric_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_metric(
    metric_id: str,
    current_user=Depends(get_current_user),
):
    """Delete a test metric (limited support in Prometheus)."""
    await test_data_service.delete_test_metric(metric_id)


@router.delete("/metrics", status_code=status.HTTP_204_NO_CONTENT)
async def clear_test_metrics(current_user=Depends(get_current_user)):
    """Clear all test metrics from Pushgateway."""
    await test_data_service.clear_test_metrics()


# General endpoints
@router.get("/stats", response_model=TestDataStats)
async def get_test_data_stats(current_user=Depends(get_current_user)):
    """Get statistics about test data."""
    return await test_data_service.get_test_data_stats()


@router.post("/regenerate", response_model=RegenerateResponse)
async def regenerate_test_data(current_user=Depends(get_current_user)):
    """Regenerate all test data with new random samples."""
    return await test_data_service.regenerate_test_data()


@router.get("/config", response_model=TestDataSourceConfig)
async def get_test_datasource_config(current_user=Depends(get_current_user)):
    """Get configuration for creating test data sources."""
    return await test_data_service.get_test_datasource_config()
