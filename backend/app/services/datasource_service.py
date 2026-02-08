"""DataSource service."""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.datasource import DataSource, DataSourceType
from app.schemas.datasource import DataSourceCreate, DataSourceUpdate, DataSourceTestResponse
from app.connectors.elasticsearch import ElasticsearchConnector
from app.connectors.loki import LokiConnector
from app.connectors.prometheus import PrometheusConnector


def get_connector(datasource: DataSource):
    """Get the appropriate connector for a data source."""
    if datasource.type == DataSourceType.ELK:
        return ElasticsearchConnector(
            host=datasource.host,
            port=datasource.port,
            auth_token=datasource.auth_token,
            config=datasource.config,
        )
    elif datasource.type == DataSourceType.LOKI:
        return LokiConnector(
            host=datasource.host,
            port=datasource.port,
            auth_token=datasource.auth_token,
            config=datasource.config,
        )
    elif datasource.type == DataSourceType.PROMETHEUS:
        return PrometheusConnector(
            host=datasource.host,
            port=datasource.port,
            auth_token=datasource.auth_token,
            config=datasource.config,
        )
    else:
        raise ValueError(f"Unknown datasource type: {datasource.type}")


async def get_all_datasources(db: AsyncSession) -> List[DataSource]:
    """Get all data sources."""
    result = await db.execute(select(DataSource).order_by(DataSource.created_at.desc()))
    return result.scalars().all()


async def get_datasource_by_id(db: AsyncSession, datasource_id: int) -> Optional[DataSource]:
    """Get a data source by ID."""
    result = await db.execute(select(DataSource).where(DataSource.id == datasource_id))
    return result.scalar_one_or_none()


async def get_datasources_by_type(db: AsyncSession, ds_type: DataSourceType) -> List[DataSource]:
    """Get data sources by type."""
    result = await db.execute(select(DataSource).where(DataSource.type == ds_type))
    return result.scalars().all()


async def create_datasource(db: AsyncSession, data: DataSourceCreate) -> DataSource:
    """Create a new data source."""
    datasource = DataSource(
        name=data.name,
        type=data.type,
        host=data.host,
        port=data.port,
        auth_token=data.auth_token,
        config=data.config,
    )
    db.add(datasource)
    await db.commit()
    await db.refresh(datasource)
    return datasource


async def update_datasource(
    db: AsyncSession, 
    datasource_id: int, 
    data: DataSourceUpdate
) -> Optional[DataSource]:
    """Update a data source."""
    datasource = await get_datasource_by_id(db, datasource_id)
    if not datasource:
        return None
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(datasource, key, value)
    
    await db.commit()
    await db.refresh(datasource)
    return datasource


async def delete_datasource(db: AsyncSession, datasource_id: int) -> bool:
    """Delete a data source."""
    datasource = await get_datasource_by_id(db, datasource_id)
    if not datasource:
        return False
    
    await db.delete(datasource)
    await db.commit()
    return True


async def test_datasource_connection(datasource: DataSource) -> DataSourceTestResponse:
    """Test connection to a data source."""
    connector = get_connector(datasource)
    success, message, latency = await connector.test_connection()
    return DataSourceTestResponse(
        success=success,
        message=message,
        latency_ms=latency,
    )
