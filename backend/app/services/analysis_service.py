"""Analysis service for alert analysis workflow."""
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models.session import AnalysisSession
from app.models.datasource import DataSource, DataSourceType
from app.schemas.analysis import (
    AnalysisRequest, 
    AnalysisResponse, 
    ContextData, 
    AnalysisResult,
    AnalysisListItem,
)
from app.services import datasource_service
from app.services import llm_service


async def create_analysis_session(
    db: AsyncSession,
    user_id: int,
    alert_content: str,
) -> AnalysisSession:
    """Create a new analysis session."""
    session = AnalysisSession(
        user_id=user_id,
        alert_content=alert_content,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session_by_id(
    db: AsyncSession,
    session_id: int,
) -> Optional[AnalysisSession]:
    """Get an analysis session by ID."""
    result = await db.execute(
        select(AnalysisSession).where(AnalysisSession.id == session_id)
    )
    return result.scalar_one_or_none()


async def list_sessions(
    db: AsyncSession,
    user_id: int,
    page: int = 1,
    page_size: int = 20,
) -> tuple[List[AnalysisSession], int]:
    """List analysis sessions for a user."""
    # Count total
    count_result = await db.execute(
        select(AnalysisSession).where(AnalysisSession.user_id == user_id)
    )
    total = len(count_result.scalars().all())
    
    # Get paginated results
    offset = (page - 1) * page_size
    result = await db.execute(
        select(AnalysisSession)
        .where(AnalysisSession.user_id == user_id)
        .order_by(desc(AnalysisSession.created_at))
        .offset(offset)
        .limit(page_size)
    )
    sessions = result.scalars().all()
    
    return sessions, total


async def collect_context(
    db: AsyncSession,
    alert_content: str,
    time_range_minutes: int,
    datasource_ids: Optional[List[int]] = None,
) -> ContextData:
    """
    Collect context data from configured data sources.
    
    Args:
        db: Database session
        alert_content: Alert content to search for
        time_range_minutes: Time range to look back
        datasource_ids: Specific datasource IDs, or None for all
    """
    context = ContextData()
    
    # Get datasources
    if datasource_ids:
        datasources = []
        for ds_id in datasource_ids:
            ds = await datasource_service.get_datasource_by_id(db, ds_id)
            if ds:
                datasources.append(ds)
    else:
        datasources = await datasource_service.get_all_datasources(db)
    
    if not datasources:
        context.collection_status["global"] = "No data sources configured"
        return context
    
    # Calculate time range
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=time_range_minutes)
    start_iso = start_time.isoformat() + "Z"
    end_iso = end_time.isoformat() + "Z"
    
    # Extract keywords from alert for querying
    keywords = _extract_keywords(alert_content)
    
    # Collect data from each datasource in parallel
    tasks = []
    for ds in datasources:
        tasks.append(_collect_from_datasource(ds, keywords, start_iso, end_iso, context))
    
    await asyncio.gather(*tasks, return_exceptions=True)
    
    return context


def _extract_keywords(alert_content: str) -> str:
    """Extract search keywords from alert content."""
    # Simple keyword extraction - in production, could use NLP
    # Remove common words and extract meaningful terms
    stop_words = {"的", "是", "在", "了", "和", "与", "或", "a", "the", "is", "at", "for", "to", "and", "or"}
    
    words = alert_content.replace("，", " ").replace("。", " ").replace(",", " ").replace(".", " ").split()
    keywords = [w for w in words if w.lower() not in stop_words and len(w) > 1]
    
    # Return top keywords
    return " ".join(keywords[:10])


async def _collect_from_datasource(
    datasource: DataSource,
    query_str: str,
    start_time: str,
    end_time: str,
    context: ContextData,
) -> None:
    """Collect data from a single datasource."""
    try:
        connector = datasource_service.get_connector(datasource)
        
        if datasource.type in [DataSourceType.ELK, DataSourceType.LOKI]:
            # Log data sources
            logs = await connector.query(query_str, start_time, end_time)
            context.logs.extend([
                {
                    "timestamp": log.get("timestamp", ""),
                    "level": log.get("level", "INFO"),
                    "message": log.get("message", ""),
                    "source": f"{datasource.name}: {log.get('source', '')}",
                }
                for log in logs
            ])
            context.collection_status[f"ds_{datasource.id}"] = f"Collected {len(logs)} logs"
        
        elif datasource.type == DataSourceType.PROMETHEUS:
            # Metrics data source - query common metrics
            # Try to extract metric names from alert or use common ones
            metric_queries = _get_prometheus_queries(query_str)
            
            all_metrics = []
            for query in metric_queries:
                metrics = await connector.query(query, start_time, end_time)
                all_metrics.extend(metrics)
            
            context.metrics.extend(all_metrics)
            context.collection_status[f"ds_{datasource.id}"] = f"Collected {len(all_metrics)} metric series"
    
    except Exception as e:
        context.collection_status[f"ds_{datasource.id}"] = f"Error: {str(e)}"


def _get_prometheus_queries(keywords: str) -> List[str]:
    """Generate Prometheus queries based on keywords."""
    queries = []
    
    # Common metrics to query
    common_metrics = [
        "up",
        "node_cpu_seconds_total",
        "node_memory_MemAvailable_bytes",
        "container_cpu_usage_seconds_total",
        "container_memory_usage_bytes",
    ]
    
    # Check for specific patterns in keywords
    keywords_lower = keywords.lower()
    
    if "cpu" in keywords_lower:
        queries.append('rate(node_cpu_seconds_total{mode!="idle"}[5m])')
        queries.append('rate(container_cpu_usage_seconds_total[5m])')
    
    if "memory" in keywords_lower or "内存" in keywords_lower:
        queries.append('node_memory_MemAvailable_bytes')
        queries.append('container_memory_usage_bytes')
    
    if "disk" in keywords_lower or "磁盘" in keywords_lower:
        queries.append('node_filesystem_avail_bytes')
    
    if "network" in keywords_lower or "网络" in keywords_lower:
        queries.append('rate(node_network_receive_bytes_total[5m])')
        queries.append('rate(node_network_transmit_bytes_total[5m])')
    
    # If no specific metrics matched, query common ones
    if not queries:
        queries = ["up", 'sum(rate(container_cpu_usage_seconds_total[5m])) by (container)']
    
    return queries


async def perform_analysis(
    db: AsyncSession,
    user_id: int,
    request: AnalysisRequest,
) -> AnalysisSession:
    """
    Perform full analysis workflow:
    1. Create session
    2. Collect context
    3. Analyze with LLM
    4. Save results
    """
    # 1. Create session
    session = await create_analysis_session(db, user_id, request.alert_content)
    
    # 2. Collect context
    context = await collect_context(
        db,
        request.alert_content,
        request.time_range_minutes,
        request.datasource_ids,
    )
    
    # Save context data
    session.context_data = context.model_dump()
    await db.commit()
    
    # 3. Analyze with LLM
    result = await llm_service.analyze_alert(
        request.alert_content,
        context.logs,
        context.metrics,
    )
    
    # 4. Save analysis result
    if result:
        session.analysis_result = result.model_dump()
        await db.commit()
    
    await db.refresh(session)
    return session
