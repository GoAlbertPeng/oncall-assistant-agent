"""Analysis service for alert analysis workflow with streaming support."""
import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, AsyncGenerator, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models.session import AnalysisSession, AnalysisStatus
from app.models.datasource import DataSource, DataSourceType
from app.schemas.analysis import (
    AnalysisRequest, 
    ContextData, 
    AnalysisResult,
    IntentResult,
    StreamEvent,
)
from app.services import datasource_service
from app.services import llm_service
from app.services import test_data_service

# Track active analysis sessions that can be cancelled
_active_sessions: Set[int] = set()
_cancelled_sessions: Set[int] = set()


def is_session_cancelled(session_id: int) -> bool:
    """Check if a session has been cancelled."""
    return session_id in _cancelled_sessions


def cancel_session(session_id: int) -> bool:
    """Cancel an active session."""
    if session_id in _active_sessions:
        _cancelled_sessions.add(session_id)
        return True
    return False


async def create_analysis_session(
    db: AsyncSession,
    user_id: int,
    alert_content: str,
) -> AnalysisSession:
    """Create a new analysis session."""
    session = AnalysisSession(
        user_id=user_id,
        alert_content=alert_content,
        status="pending",
        messages=[],
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


async def update_session_status(
    db: AsyncSession,
    session: AnalysisSession,
    status: str,
    stage: str = None,
) -> None:
    """Update session status and stage."""
    session.status = status
    if stage:
        session.current_stage = stage
    await db.commit()


def _format_sse_event(event: StreamEvent) -> str:
    """Format a StreamEvent as SSE data."""
    data = event.model_dump(exclude_none=True)
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_analysis(
    db: AsyncSession,
    session: AnalysisSession,
    request: AnalysisRequest,
) -> AsyncGenerator[str, None]:
    """
    Stream analysis with multiple stages.
    
    Stages:
    1. Intent Understanding - Parse and understand the alert
    2. Data Collection - Collect logs and metrics
    3. LLM Analysis - Analyze with LLM
    """
    session_id = session.id
    _active_sessions.add(session_id)
    
    try:
        # ====== Stage 1: Intent Understanding ======
        yield _format_sse_event(StreamEvent(
            event="stage_start",
            stage="intent_understanding",
            content="🔍 正在分析告警意图...",
        ))
        
        await update_session_status(db, session, "intent_understanding", "intent_understanding")
        
        # Check for cancellation
        if is_session_cancelled(session_id):
            yield _format_sse_event(StreamEvent(event="cancelled", content="分析已取消"))
            return
        
        # Parse intent
        intent = await _understand_intent(request.alert_content)
        session.intent = intent.model_dump()
        session.add_message("assistant", f"📋 **告警摘要**: {intent.summary}", "intent_understanding")
        session.add_message("assistant", f"🏷️ **告警类型**: {intent.alert_type}", "intent_understanding")
        if intent.affected_system:
            session.add_message("assistant", f"💻 **影响系统**: {intent.affected_system}", "intent_understanding")
        session.add_message("assistant", f"🔑 **关键词**: {', '.join(intent.keywords)}", "intent_understanding")
        await db.commit()
        
        yield _format_sse_event(StreamEvent(
            event="stage_progress",
            stage="intent_understanding",
            content=f"告警摘要: {intent.summary}",
            data=intent.model_dump(),
            progress=100,
        ))
        
        yield _format_sse_event(StreamEvent(
            event="stage_complete",
            stage="intent_understanding",
            content="✅ 意图分析完成",
        ))
        
        await asyncio.sleep(0.3)  # Small delay for UI
        
        # ====== Stage 2: Data Collection ======
        if is_session_cancelled(session_id):
            yield _format_sse_event(StreamEvent(event="cancelled", content="分析已取消"))
            return
        
        yield _format_sse_event(StreamEvent(
            event="stage_start",
            stage="data_collection",
            content="📊 正在收集相关数据...",
        ))
        
        await update_session_status(db, session, "data_collection", "data_collection")
        
        # Collect context with progress updates
        context = ContextData()
        datasources = await _get_datasources(db, request.datasource_ids)
        
        if not datasources:
            session.add_message("assistant", "⚠️ 未配置数据源，将使用测试数据", "data_collection")
            yield _format_sse_event(StreamEvent(
                event="stage_progress",
                stage="data_collection",
                content="未配置数据源，正在加载测试数据...",
                progress=50,
            ))
            
            # Load test data when no datasources configured
            keywords = " ".join(intent.keywords) if intent.keywords else ""
            test_logs = await test_data_service.get_test_logs(query=keywords, limit=50)
            test_metrics = await test_data_service.get_test_metrics(limit=20)
            
            if test_logs:
                context.logs.extend([
                    {
                        "timestamp": log.get("timestamp", ""),
                        "level": log.get("level", "INFO"),
                        "message": log.get("message", ""),
                        "source": f"测试数据: {log.get('source', '')}",
                    }
                    for log in test_logs
                ])
                context.collection_status["test_logs"] = f"从测试数据收集到 {len(test_logs)} 条日志"
            
            if test_metrics:
                for m in test_metrics:
                    context.metrics.append({
                        "metric_name": m.get("name", "unknown"),
                        "labels": m.get("labels", {}),
                        "values": [{"timestamp": m.get("timestamp", ""), "value": m.get("value", 0)}],
                    })
                context.collection_status["test_metrics"] = f"从测试数据收集到 {len(test_metrics)} 条指标"
            
            session.add_message("assistant", f"📥 从测试数据收集到 {len(test_logs)} 条日志, {len(test_metrics)} 条指标", "data_collection")
        else:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=request.time_range_minutes)
            start_iso = start_time.isoformat() + "Z"
            end_iso = end_time.isoformat() + "Z"
            
            keywords = " ".join(intent.keywords) if intent.keywords else _extract_keywords(request.alert_content)
            
            total_ds = len(datasources)
            for i, ds in enumerate(datasources):
                if is_session_cancelled(session_id):
                    yield _format_sse_event(StreamEvent(event="cancelled", content="分析已取消"))
                    return
                
                yield _format_sse_event(StreamEvent(
                    event="stage_progress",
                    stage="data_collection",
                    content=f"正在查询数据源: {ds.name}",
                    progress=int((i / total_ds) * 100),
                ))
                
                await _collect_from_datasource(ds, keywords, start_iso, end_iso, context)
                session.add_message(
                    "assistant", 
                    f"📥 从 **{ds.name}** 收集到 {context.collection_status.get(f'ds_{ds.id}', '0 条数据')}", 
                    "data_collection"
                )
                await db.commit()
        
        # Save context
        session.context_data = context.model_dump()
        await db.commit()
        
        yield _format_sse_event(StreamEvent(
            event="stage_complete",
            stage="data_collection",
            content=f"✅ 数据收集完成: {len(context.logs)} 条日志, {len(context.metrics)} 条指标",
            data={"logs_count": len(context.logs), "metrics_count": len(context.metrics)},
        ))
        
        await asyncio.sleep(0.3)
        
        # ====== Stage 3: LLM Analysis ======
        if is_session_cancelled(session_id):
            yield _format_sse_event(StreamEvent(event="cancelled", content="分析已取消"))
            return
        
        yield _format_sse_event(StreamEvent(
            event="stage_start",
            stage="llm_analysis",
            content="🤖 正在调用大模型进行分析...",
        ))
        
        await update_session_status(db, session, "llm_analysis", "llm_analysis")
        session.add_message("assistant", "🤖 正在分析告警原因，请稍候...", "llm_analysis")
        await db.commit()
        
        # Stream LLM analysis
        yield _format_sse_event(StreamEvent(
            event="stage_progress",
            stage="llm_analysis",
            content="大模型正在思考中...",
            progress=30,
        ))
        
        result = await llm_service.analyze_alert(
            request.alert_content,
            context.logs,
            context.metrics,
        )
        
        if is_session_cancelled(session_id):
            yield _format_sse_event(StreamEvent(event="cancelled", content="分析已取消"))
            return
        
        # Save and stream result
        if result:
            session.analysis_result = result.model_dump()
            
            # Stream each part of the result
            yield _format_sse_event(StreamEvent(
                event="message",
                stage="llm_analysis",
                content=f"## 🎯 根因分析\n{result.root_cause}",
            ))
            await asyncio.sleep(0.2)
            
            yield _format_sse_event(StreamEvent(
                event="message",
                stage="llm_analysis",
                content=f"## 📋 证据\n{result.evidence}",
            ))
            await asyncio.sleep(0.2)
            
            yield _format_sse_event(StreamEvent(
                event="message",
                stage="llm_analysis",
                content=f"## 🏷️ 问题分类\n{_translate_category(result.category)}",
            ))
            await asyncio.sleep(0.2)
            
            yield _format_sse_event(StreamEvent(
                event="message",
                stage="llm_analysis",
                content=f"## 🚑 临时解决方案\n{result.temporary_solution}",
            ))
            await asyncio.sleep(0.2)
            
            yield _format_sse_event(StreamEvent(
                event="message",
                stage="llm_analysis",
                content=f"## 🔧 根本解决方案\n{result.permanent_solution}",
            ))
            await asyncio.sleep(0.2)
            
            yield _format_sse_event(StreamEvent(
                event="message",
                stage="llm_analysis",
                content=f"## 📊 置信度\n{int(result.confidence * 100)}%",
            ))
            
            # Add to messages
            session.add_message("assistant", f"**根因分析**: {result.root_cause}", "llm_analysis", result.model_dump())
        
        await db.commit()
        
        yield _format_sse_event(StreamEvent(
            event="stage_complete",
            stage="llm_analysis",
            content="✅ 分析完成",
        ))
        
        # ====== Complete ======
        await update_session_status(db, session, "completed")
        session.add_message("assistant", "分析完成！您可以继续提问或请求进一步分析。", "completed")
        await db.commit()
        
        yield _format_sse_event(StreamEvent(
            event="done",
            content="分析完成",
            data={"session_id": session.id},
        ))
        
    except Exception as e:
        await update_session_status(db, session, "error")
        session.add_message("system", f"分析出错: {str(e)}", "error")
        await db.commit()
        
        yield _format_sse_event(StreamEvent(
            event="error",
            content=f"分析出错: {str(e)}",
        ))
    
    finally:
        _active_sessions.discard(session_id)
        _cancelled_sessions.discard(session_id)


async def _understand_intent(alert_content: str) -> IntentResult:
    """Parse and understand the alert intent."""
    # Simple intent parsing - could be enhanced with LLM
    content_lower = alert_content.lower()
    
    # Determine alert type
    if any(k in content_lower for k in ["cpu", "内存", "memory", "disk", "磁盘", "load"]):
        alert_type = "performance"
    elif any(k in content_lower for k in ["error", "错误", "exception", "异常", "fail"]):
        alert_type = "error"
    elif any(k in content_lower for k in ["down", "宕机", "unreachable", "超时", "timeout"]):
        alert_type = "availability"
    elif any(k in content_lower for k in ["network", "网络", "connection", "连接"]):
        alert_type = "network"
    else:
        alert_type = "general"
    
    # Extract keywords
    keywords = _extract_keywords(alert_content).split()
    
    # Extract affected system
    affected_system = None
    for word in alert_content.split():
        if word.endswith("-service") or word.endswith("服务"):
            affected_system = word
            break
    
    # Suggest metrics based on type
    suggested_metrics = []
    if alert_type == "performance":
        suggested_metrics = ["cpu_usage", "memory_usage", "disk_usage"]
    elif alert_type == "availability":
        suggested_metrics = ["up", "response_time", "error_rate"]
    elif alert_type == "network":
        suggested_metrics = ["network_in", "network_out", "connection_count"]
    
    return IntentResult(
        summary=alert_content[:100] if len(alert_content) > 100 else alert_content,
        alert_type=alert_type,
        affected_system=affected_system,
        keywords=keywords[:10],
        suggested_metrics=suggested_metrics,
    )


def _translate_category(category: str) -> str:
    """Translate category to Chinese."""
    translations = {
        "code_issue": "代码问题",
        "config_issue": "配置问题", 
        "resource_bottleneck": "资源瓶颈",
        "dependency_failure": "依赖故障",
    }
    return translations.get(category, category)


async def _get_datasources(db: AsyncSession, datasource_ids: Optional[List[int]]) -> List[DataSource]:
    """Get datasources to query."""
    if datasource_ids:
        datasources = []
        for ds_id in datasource_ids:
            ds = await datasource_service.get_datasource_by_id(db, ds_id)
            if ds:
                datasources.append(ds)
        return datasources
    return await datasource_service.get_all_datasources(db)


def _extract_keywords(alert_content: str) -> str:
    """Extract search keywords from alert content."""
    stop_words = {"的", "是", "在", "了", "和", "与", "或", "a", "the", "is", "at", "for", "to", "and", "or"}
    words = alert_content.replace("，", " ").replace("。", " ").replace(",", " ").replace(".", " ").split()
    keywords = [w for w in words if w.lower() not in stop_words and len(w) > 1]
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
            logs = await connector.query(query_str, start_time, end_time)
            
            # If no logs found from datasource, try test data
            if not logs:
                test_logs = await test_data_service.get_test_logs(query=query_str, limit=50)
                if test_logs:
                    logs = test_logs
                    context.collection_status[f"ds_{datasource.id}"] = f"从测试数据收集到 {len(logs)} 条日志"
                else:
                    context.collection_status[f"ds_{datasource.id}"] = "未找到相关日志"
            else:
                context.collection_status[f"ds_{datasource.id}"] = f"收集到 {len(logs)} 条日志"
            
            context.logs.extend([
                {
                    "timestamp": log.get("timestamp", ""),
                    "level": log.get("level", "INFO"),
                    "message": log.get("message", ""),
                    "source": f"{datasource.name}: {log.get('source', '')}",
                }
                for log in logs
            ])
        
        elif datasource.type == DataSourceType.PROMETHEUS:
            metric_queries = _get_prometheus_queries(query_str)
            all_metrics = []
            for query in metric_queries:
                try:
                    metrics = await connector.query(query, start_time, end_time)
                    all_metrics.extend(metrics)
                except Exception:
                    pass
            
            # If no metrics found, try test data
            if not all_metrics:
                test_metrics = await test_data_service.get_test_metrics(limit=20)
                if test_metrics:
                    # Convert test metrics to expected format
                    for m in test_metrics:
                        all_metrics.append({
                            "metric_name": m.get("name", "unknown"),
                            "labels": m.get("labels", {}),
                            "values": [{"timestamp": m.get("timestamp", ""), "value": m.get("value", 0)}],
                        })
                    context.collection_status[f"ds_{datasource.id}"] = f"从测试数据收集到 {len(all_metrics)} 条指标"
                else:
                    context.collection_status[f"ds_{datasource.id}"] = "未找到相关指标"
            else:
                context.collection_status[f"ds_{datasource.id}"] = f"收集到 {len(all_metrics)} 条指标"
            
            context.metrics.extend(all_metrics)
    
    except Exception as e:
        # On error, try to get test data as fallback
        error_msg = str(e)
        if datasource.type in [DataSourceType.ELK, DataSourceType.LOKI]:
            test_logs = await test_data_service.get_test_logs(query=query_str, limit=50)
            if test_logs:
                context.logs.extend([
                    {
                        "timestamp": log.get("timestamp", ""),
                        "level": log.get("level", "INFO"),
                        "message": log.get("message", ""),
                        "source": f"测试数据: {log.get('source', '')}",
                    }
                    for log in test_logs
                ])
                context.collection_status[f"ds_{datasource.id}"] = f"数据源连接失败，从测试数据收集到 {len(test_logs)} 条日志"
            else:
                context.collection_status[f"ds_{datasource.id}"] = f"连接失败: {error_msg[:50]}"
        elif datasource.type == DataSourceType.PROMETHEUS:
            test_metrics = await test_data_service.get_test_metrics(limit=20)
            if test_metrics:
                for m in test_metrics:
                    context.metrics.append({
                        "metric_name": m.get("name", "unknown"),
                        "labels": m.get("labels", {}),
                        "values": [{"timestamp": m.get("timestamp", ""), "value": m.get("value", 0)}],
                    })
                context.collection_status[f"ds_{datasource.id}"] = f"数据源连接失败，从测试数据收集到 {len(test_metrics)} 条指标"
            else:
                context.collection_status[f"ds_{datasource.id}"] = f"连接失败: {error_msg[:50]}"


def _get_prometheus_queries(keywords: str) -> List[str]:
    """Generate Prometheus queries based on keywords."""
    queries = []
    keywords_lower = keywords.lower()
    
    if "cpu" in keywords_lower:
        queries.append('rate(node_cpu_seconds_total{mode!="idle"}[5m])')
    if "memory" in keywords_lower or "内存" in keywords_lower:
        queries.append('node_memory_MemAvailable_bytes')
    if "disk" in keywords_lower or "磁盘" in keywords_lower:
        queries.append('node_filesystem_avail_bytes')
    if "network" in keywords_lower or "网络" in keywords_lower:
        queries.append('rate(node_network_receive_bytes_total[5m])')
    
    if not queries:
        queries = ["up"]
    
    return queries


# ====== Legacy non-streaming methods for backward compatibility ======

async def collect_context(
    db: AsyncSession,
    alert_content: str,
    time_range_minutes: int,
    datasource_ids: Optional[List[int]] = None,
) -> ContextData:
    """Collect context data from configured data sources."""
    context = ContextData()
    datasources = await _get_datasources(db, datasource_ids)
    keywords = _extract_keywords(alert_content)
    
    if datasources:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=time_range_minutes)
        start_iso = start_time.isoformat() + "Z"
        end_iso = end_time.isoformat() + "Z"
        
        tasks = []
        for ds in datasources:
            tasks.append(_collect_from_datasource(ds, keywords, start_iso, end_iso, context))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    # If no logs collected, get test logs
    if not context.logs:
        test_logs = await test_data_service.get_test_logs(query=keywords, limit=50)
        if test_logs:
            context.logs.extend([
                {
                    "timestamp": log.get("timestamp", ""),
                    "level": log.get("level", "INFO"),
                    "message": log.get("message", ""),
                    "source": f"测试数据: {log.get('source', '')}",
                }
                for log in test_logs
            ])
            context.collection_status["test_logs"] = f"从测试数据收集到 {len(test_logs)} 条日志"
    
    # If no metrics collected, get test metrics
    if not context.metrics:
        test_metrics = await test_data_service.get_test_metrics(limit=20)
        if test_metrics:
            for m in test_metrics:
                context.metrics.append({
                    "metric_name": m.get("name", "unknown"),
                    "labels": m.get("labels", {}),
                    "values": [{"timestamp": m.get("timestamp", ""), "value": m.get("value", 0)}],
                })
            context.collection_status["test_metrics"] = f"从测试数据收集到 {len(test_metrics)} 条指标"
    
    if not context.logs and not context.metrics:
        context.collection_status["global"] = "未能收集到任何数据"
    
    return context


async def perform_analysis(
    db: AsyncSession,
    user_id: int,
    request: AnalysisRequest,
) -> AnalysisSession:
    """Perform full analysis workflow (non-streaming)."""
    session = await create_analysis_session(db, user_id, request.alert_content)
    session.add_message("user", request.alert_content)
    
    context = await collect_context(
        db,
        request.alert_content,
        request.time_range_minutes,
        request.datasource_ids,
    )
    session.context_data = context.model_dump()
    await db.commit()
    
    result = await llm_service.analyze_alert(
        request.alert_content,
        context.logs,
        context.metrics,
    )
    
    if result:
        session.analysis_result = result.model_dump()
        session.add_message("assistant", f"根因分析: {result.root_cause}", "llm_analysis", result.model_dump())
    
    session.status = "completed"
    await db.commit()
    await db.refresh(session)
    return session


async def continue_analysis(
    db: AsyncSession,
    session: AnalysisSession,
    user_message: str,
) -> AsyncGenerator[str, None]:
    """Continue analysis with a follow-up question."""
    session_id = session.id
    _active_sessions.add(session_id)
    
    try:
        session.add_message("user", user_message)
        await db.commit()
        
        yield _format_sse_event(StreamEvent(
            event="stage_start",
            stage="follow_up",
            content="🤖 正在处理您的问题...",
        ))
        
        # Build context from previous analysis
        previous_result = session.analysis_result or {}
        context_summary = f"""
之前的分析结果:
- 根因: {previous_result.get('root_cause', '未知')}
- 证据: {previous_result.get('evidence', '无')}
- 分类: {previous_result.get('category', '未知')}

用户的追问: {user_message}
"""
        
        # Call LLM for follow-up
        result = await llm_service.analyze_alert(
            context_summary,
            session.context_data.get("logs", []) if session.context_data else [],
            session.context_data.get("metrics", []) if session.context_data else [],
        )
        
        if is_session_cancelled(session_id):
            yield _format_sse_event(StreamEvent(event="cancelled", content="分析已取消"))
            return
        
        if result:
            yield _format_sse_event(StreamEvent(
                event="message",
                stage="follow_up",
                content=result.root_cause,
            ))
            
            session.add_message("assistant", result.root_cause, "follow_up", result.model_dump())
        
        await db.commit()
        
        yield _format_sse_event(StreamEvent(
            event="done",
            content="回答完成",
        ))
        
    except Exception as e:
        yield _format_sse_event(StreamEvent(
            event="error",
            content=f"处理出错: {str(e)}",
        ))
    
    finally:
        _active_sessions.discard(session_id)
        _cancelled_sessions.discard(session_id)
