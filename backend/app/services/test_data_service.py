"""Test data service - logs in memory, metrics in real Prometheus."""
import os
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import httpx

# Configuration from environment
PROMETHEUS_URL = os.getenv("TEST_PROMETHEUS_URL", "http://prometheus:9090")
PUSHGATEWAY_URL = os.getenv("TEST_PUSHGATEWAY_URL", "http://pushgateway:9091")

# In-memory storage for test logs (Elasticsearch would need 512MB+ RAM)
_test_logs: List[Dict[str, Any]] = []


def _generate_sample_logs() -> List[Dict[str, Any]]:
    """Generate realistic sample log entries based on common incident scenarios."""
    logs = []
    now = datetime.utcnow()
    
    # ===== 场景1: 订单服务CPU高负载 =====
    scenario1_logs = [
        {"service": "order-service", "level": "WARN", "offset": 45, "msg": "CPU使用率上升至75%，触发告警阈值"},
        {"service": "order-service", "level": "WARN", "offset": 40, "msg": "GC频率增加，平均每分钟3次Full GC"},
        {"service": "order-service", "level": "ERROR", "offset": 35, "msg": "CPU使用率达到92%，服务响应延迟增加"},
        {"service": "order-service", "level": "ERROR", "offset": 30, "msg": "处理订单请求超时，耗时15000ms，正常值200ms"},
        {"service": "order-service", "level": "WARN", "offset": 28, "msg": "线程池队列积压严重，当前等待任务数: 2500"},
        {"service": "order-service", "level": "ERROR", "offset": 25, "msg": "CPU使用率持续高于95%超过5分钟，触发P1告警"},
        {"service": "api-gateway", "level": "ERROR", "offset": 24, "msg": "上游服务order-service响应超时，熔断器已开启"},
        {"service": "order-service", "level": "INFO", "offset": 20, "msg": "自动扩容触发，新增2个实例"},
        {"service": "order-service", "level": "INFO", "offset": 15, "msg": "CPU使用率下降至65%，服务恢复正常"},
    ]
    
    # ===== 场景2: 支付服务内存溢出 =====
    scenario2_logs = [
        {"service": "payment-service", "level": "INFO", "offset": 60, "msg": "JVM堆内存使用率: 65%，老年代占用: 2.1GB/3GB"},
        {"service": "payment-service", "level": "WARN", "offset": 55, "msg": "内存使用率达到80%，建议关注"},
        {"service": "payment-service", "level": "WARN", "offset": 50, "msg": "检测到内存泄漏风险，PaymentCache对象数量异常增长"},
        {"service": "payment-service", "level": "ERROR", "offset": 45, "msg": "JVM堆内存使用率达到95%，触发紧急GC"},
        {"service": "payment-service", "level": "ERROR", "offset": 42, "msg": "Full GC耗时8500ms，服务暂停响应"},
        {"service": "payment-service", "level": "ERROR", "offset": 40, "msg": "java.lang.OutOfMemoryError: Java heap space"},
        {"service": "payment-service", "level": "ERROR", "offset": 38, "msg": "支付请求处理失败，事务已回滚: PAY-20260208-12345"},
        {"service": "api-gateway", "level": "ERROR", "offset": 37, "msg": "payment-service健康检查失败，从负载均衡器摘除"},
        {"service": "payment-service", "level": "INFO", "offset": 30, "msg": "服务实例重启中..."},
        {"service": "payment-service", "level": "INFO", "offset": 25, "msg": "服务重启完成，内存使用率恢复至35%"},
    ]
    
    # ===== 场景3: 数据库连接池耗尽 =====
    scenario3_logs = [
        {"service": "user-service", "level": "INFO", "offset": 70, "msg": "数据库连接池状态: 活跃连接50/100，空闲连接50"},
        {"service": "user-service", "level": "WARN", "offset": 65, "msg": "数据库连接池使用率达到75%，当前活跃: 75/100"},
        {"service": "user-service", "level": "WARN", "offset": 60, "msg": "检测到慢SQL查询: SELECT * FROM user_orders耗时3500ms"},
        {"service": "user-service", "level": "WARN", "offset": 55, "msg": "数据库连接池使用率90%，等待获取连接的请求: 25"},
        {"service": "user-service", "level": "ERROR", "offset": 50, "msg": "数据库连接池已满，无法获取新连接，等待超时5000ms"},
        {"service": "user-service", "level": "ERROR", "offset": 48, "msg": "com.mysql.jdbc.exceptions.jdbc4.ConnectionException: 连接池耗尽"},
        {"service": "user-service", "level": "ERROR", "offset": 45, "msg": "用户查询请求失败: 数据库连接不可用，影响用户数: 1500"},
        {"service": "user-service", "level": "WARN", "offset": 40, "msg": "正在释放空闲连接，尝试重建连接池"},
        {"service": "user-service", "level": "INFO", "offset": 35, "msg": "数据库连接池恢复正常，活跃连接: 40/100"},
    ]
    
    # ===== 场景4: Kafka消息积压 =====
    scenario4_logs = [
        {"service": "inventory-service", "level": "INFO", "offset": 80, "msg": "Kafka消费者组inventory-consumer启动，分配分区: [0,1,2]"},
        {"service": "inventory-service", "level": "WARN", "offset": 75, "msg": "Kafka消费延迟增加，当前lag: 15000条消息"},
        {"service": "inventory-service", "level": "WARN", "offset": 70, "msg": "消息处理速度下降，当前TPS: 500，目标TPS: 2000"},
        {"service": "inventory-service", "level": "ERROR", "offset": 65, "msg": "Kafka消费积压严重，lag已达50000条，超过告警阈值"},
        {"service": "inventory-service", "level": "ERROR", "offset": 60, "msg": "库存更新延迟，订单库存扣减出现不一致"},
        {"service": "order-service", "level": "WARN", "offset": 58, "msg": "库存校验超时，降级使用缓存数据"},
        {"service": "inventory-service", "level": "INFO", "offset": 55, "msg": "扩容消费者实例至5个，重新分配分区"},
        {"service": "inventory-service", "level": "INFO", "offset": 45, "msg": "消费积压逐渐减少，当前lag: 8000条"},
        {"service": "inventory-service", "level": "INFO", "offset": 30, "msg": "Kafka消费积压已清理，lag降至正常水平: 200条"},
    ]
    
    # ===== 场景5: 网络超时/连接异常 =====
    scenario5_logs = [
        {"service": "api-gateway", "level": "WARN", "offset": 90, "msg": "检测到网络延迟增加，到payment-service的RTT: 500ms"},
        {"service": "api-gateway", "level": "ERROR", "offset": 85, "msg": "连接payment-service超时: connect timed out after 10000ms"},
        {"service": "api-gateway", "level": "ERROR", "offset": 82, "msg": "java.net.SocketTimeoutException: Read timed out"},
        {"service": "payment-service", "level": "ERROR", "offset": 80, "msg": "无法连接到Redis集群: redis-cluster.internal:6379"},
        {"service": "payment-service", "level": "ERROR", "offset": 78, "msg": "Redis连接池无可用连接，请求被拒绝"},
        {"service": "api-gateway", "level": "WARN", "offset": 75, "msg": "熔断器开启，payment-service请求降级处理"},
        {"service": "api-gateway", "level": "INFO", "offset": 70, "msg": "网络恢复正常，RTT降至50ms"},
        {"service": "api-gateway", "level": "INFO", "offset": 65, "msg": "熔断器半开，尝试恢复请求"},
        {"service": "api-gateway", "level": "INFO", "offset": 60, "msg": "熔断器关闭，服务完全恢复"},
    ]
    
    # ===== 场景6: 磁盘空间不足 =====
    scenario6_logs = [
        {"service": "log-collector", "level": "WARN", "offset": 100, "msg": "磁盘使用率达到70%，剩余空间: 30GB"},
        {"service": "log-collector", "level": "WARN", "offset": 95, "msg": "磁盘使用率达到80%，日志轮转加速执行"},
        {"service": "log-collector", "level": "ERROR", "offset": 88, "msg": "磁盘使用率达到95%，即将触发只读模式"},
        {"service": "order-service", "level": "ERROR", "offset": 85, "msg": "无法写入日志文件: No space left on device"},
        {"service": "mysql", "level": "ERROR", "offset": 83, "msg": "磁盘空间不足，binlog写入失败，主从同步中断"},
        {"service": "log-collector", "level": "INFO", "offset": 75, "msg": "紧急清理历史日志，释放空间20GB"},
        {"service": "log-collector", "level": "INFO", "offset": 70, "msg": "磁盘使用率降至65%，服务恢复正常"},
    ]
    
    # 合并所有场景日志
    all_scenario_logs = [
        scenario1_logs, scenario2_logs, scenario3_logs,
        scenario4_logs, scenario5_logs, scenario6_logs
    ]
    
    for scenario_logs in all_scenario_logs:
        for log_item in scenario_logs:
            timestamp = now - timedelta(minutes=log_item["offset"])
            logs.append({
                "id": str(uuid.uuid4()),
                "timestamp": timestamp.isoformat() + "Z",
                "level": log_item["level"],
                "message": f"[{log_item['service']}] {log_item['msg']}",
                "source": log_item["service"],
                "index": f"app-logs-{timestamp.strftime('%Y.%m.%d')}",
            })
    
    # 添加一些正常运行日志作为背景噪音
    normal_logs = [
        {"service": "api-gateway", "level": "INFO", "msg": "健康检查通过，所有上游服务正常"},
        {"service": "user-service", "level": "INFO", "msg": "用户登录成功: user_id=12345"},
        {"service": "order-service", "level": "INFO", "msg": "订单创建成功: ORD-20260208-67890"},
        {"service": "payment-service", "level": "INFO", "msg": "支付完成: PAY-20260208-11111, 金额: ¥299.00"},
        {"service": "inventory-service", "level": "INFO", "msg": "库存更新成功: SKU-001, 当前库存: 150"},
        {"service": "api-gateway", "level": "DEBUG", "msg": "请求处理完成: GET /api/users/12345, 耗时: 45ms"},
        {"service": "user-service", "level": "DEBUG", "msg": "缓存命中: user:12345, TTL剩余: 3500s"},
    ]
    
    for i in range(20):
        log_item = random.choice(normal_logs)
        timestamp = now - timedelta(minutes=random.randint(1, 120))
        logs.append({
            "id": str(uuid.uuid4()),
            "timestamp": timestamp.isoformat() + "Z",
            "level": log_item["level"],
            "message": f"[{log_item['service']}] {log_item['msg']}",
            "source": log_item["service"],
            "index": f"app-logs-{timestamp.strftime('%Y.%m.%d')}",
        })
    
    # Sort by timestamp descending
    logs.sort(key=lambda x: x["timestamp"], reverse=True)
    return logs


def _generate_sample_metrics() -> List[Dict[str, Any]]:
    """Generate realistic sample metrics correlated with incident scenarios."""
    metrics = []
    
    # ===== CPU相关指标 (场景1: 订单服务CPU高负载) =====
    cpu_metrics = [
        {"name": "cpu_usage_percent", "labels": {"service": "order-service", "instance": "order-1"}, "value": 92.5, "help": "CPU使用率百分比"},
        {"name": "cpu_usage_percent", "labels": {"service": "order-service", "instance": "order-2"}, "value": 88.3, "help": "CPU使用率百分比"},
        {"name": "cpu_usage_percent", "labels": {"service": "api-gateway", "instance": "gw-1"}, "value": 45.2, "help": "CPU使用率百分比"},
        {"name": "cpu_usage_percent", "labels": {"service": "user-service", "instance": "user-1"}, "value": 38.7, "help": "CPU使用率百分比"},
        {"name": "cpu_usage_percent", "labels": {"service": "payment-service", "instance": "pay-1"}, "value": 52.1, "help": "CPU使用率百分比"},
        {"name": "gc_pause_seconds", "labels": {"service": "order-service", "gc_type": "full"}, "value": 2.5, "help": "GC暂停时间秒"},
        {"name": "gc_count_total", "labels": {"service": "order-service", "gc_type": "full"}, "value": 15, "help": "GC次数"},
        {"name": "thread_pool_active", "labels": {"service": "order-service", "pool": "worker"}, "value": 195, "help": "活跃线程数"},
        {"name": "thread_pool_queue_size", "labels": {"service": "order-service", "pool": "worker"}, "value": 2500, "help": "线程池队列大小"},
    ]
    
    # ===== 内存相关指标 (场景2: 支付服务内存溢出) =====
    memory_metrics = [
        {"name": "jvm_memory_used_bytes", "labels": {"service": "payment-service", "area": "heap"}, "value": 2850000000, "help": "JVM堆内存使用量"},
        {"name": "jvm_memory_max_bytes", "labels": {"service": "payment-service", "area": "heap"}, "value": 3000000000, "help": "JVM堆内存最大值"},
        {"name": "jvm_memory_used_bytes", "labels": {"service": "order-service", "area": "heap"}, "value": 1200000000, "help": "JVM堆内存使用量"},
        {"name": "jvm_memory_max_bytes", "labels": {"service": "order-service", "area": "heap"}, "value": 2000000000, "help": "JVM堆内存最大值"},
        {"name": "memory_usage_percent", "labels": {"service": "payment-service"}, "value": 95.0, "help": "内存使用率百分比"},
        {"name": "memory_usage_percent", "labels": {"service": "order-service"}, "value": 60.0, "help": "内存使用率百分比"},
        {"name": "gc_pause_seconds", "labels": {"service": "payment-service", "gc_type": "full"}, "value": 8.5, "help": "GC暂停时间秒"},
    ]
    
    # ===== 数据库连接池指标 (场景3: 连接池耗尽) =====
    db_metrics = [
        {"name": "db_connections_active", "labels": {"service": "user-service", "pool": "primary"}, "value": 100, "help": "活跃数据库连接数"},
        {"name": "db_connections_max", "labels": {"service": "user-service", "pool": "primary"}, "value": 100, "help": "最大数据库连接数"},
        {"name": "db_connections_pending", "labels": {"service": "user-service", "pool": "primary"}, "value": 25, "help": "等待连接数"},
        {"name": "db_query_duration_seconds", "labels": {"service": "user-service", "query": "user_orders"}, "value": 3.5, "help": "SQL查询耗时"},
        {"name": "db_connections_active", "labels": {"service": "order-service", "pool": "primary"}, "value": 45, "help": "活跃数据库连接数"},
        {"name": "db_connections_max", "labels": {"service": "order-service", "pool": "primary"}, "value": 100, "help": "最大数据库连接数"},
    ]
    
    # ===== Kafka消息队列指标 (场景4: 消息积压) =====
    kafka_metrics = [
        {"name": "kafka_consumer_lag", "labels": {"service": "inventory-service", "topic": "inventory-events", "group": "inventory-consumer"}, "value": 50000, "help": "Kafka消费积压"},
        {"name": "kafka_consumer_lag", "labels": {"service": "order-service", "topic": "order-events", "group": "order-consumer"}, "value": 200, "help": "Kafka消费积压"},
        {"name": "kafka_messages_consumed_rate", "labels": {"service": "inventory-service", "topic": "inventory-events"}, "value": 500, "help": "每秒消费消息数"},
        {"name": "kafka_messages_produced_rate", "labels": {"service": "order-service", "topic": "inventory-events"}, "value": 2000, "help": "每秒生产消息数"},
    ]
    
    # ===== 网络和延迟指标 (场景5: 网络超时) =====
    network_metrics = [
        {"name": "http_request_duration_seconds", "labels": {"service": "api-gateway", "target": "payment-service", "method": "POST"}, "value": 10.5, "help": "HTTP请求延迟"},
        {"name": "http_request_duration_seconds", "labels": {"service": "api-gateway", "target": "order-service", "method": "POST"}, "value": 0.25, "help": "HTTP请求延迟"},
        {"name": "network_rtt_seconds", "labels": {"source": "api-gateway", "target": "payment-service"}, "value": 0.5, "help": "网络往返延迟"},
        {"name": "circuit_breaker_state", "labels": {"service": "api-gateway", "target": "payment-service"}, "value": 1, "help": "熔断器状态(0=closed,1=open)"},
        {"name": "redis_connection_errors_total", "labels": {"service": "payment-service", "cluster": "redis-cluster"}, "value": 150, "help": "Redis连接错误数"},
    ]
    
    # ===== 磁盘指标 (场景6: 磁盘空间不足) =====
    disk_metrics = [
        {"name": "disk_usage_percent", "labels": {"host": "log-server-1", "mount": "/data"}, "value": 95.0, "help": "磁盘使用率百分比"},
        {"name": "disk_free_bytes", "labels": {"host": "log-server-1", "mount": "/data"}, "value": 5000000000, "help": "磁盘剩余空间"},
        {"name": "disk_usage_percent", "labels": {"host": "db-server-1", "mount": "/var/lib/mysql"}, "value": 78.0, "help": "磁盘使用率百分比"},
    ]
    
    # ===== HTTP请求指标 =====
    http_metrics = [
        {"name": "http_requests_total", "labels": {"service": "api-gateway", "method": "GET", "status": "200"}, "value": 125000, "help": "HTTP请求总数"},
        {"name": "http_requests_total", "labels": {"service": "api-gateway", "method": "POST", "status": "200"}, "value": 45000, "help": "HTTP请求总数"},
        {"name": "http_requests_total", "labels": {"service": "api-gateway", "method": "POST", "status": "500"}, "value": 1250, "help": "HTTP请求总数"},
        {"name": "http_requests_total", "labels": {"service": "api-gateway", "method": "POST", "status": "504"}, "value": 350, "help": "HTTP请求总数"},
        {"name": "http_error_rate", "labels": {"service": "order-service"}, "value": 0.02, "help": "HTTP错误率"},
        {"name": "http_error_rate", "labels": {"service": "payment-service"}, "value": 0.15, "help": "HTTP错误率"},
        {"name": "http_error_rate", "labels": {"service": "user-service"}, "value": 0.08, "help": "HTTP错误率"},
    ]
    
    # ===== 业务指标 =====
    business_metrics = [
        {"name": "orders_created_total", "labels": {"service": "order-service"}, "value": 8500, "help": "创建订单总数"},
        {"name": "orders_failed_total", "labels": {"service": "order-service"}, "value": 125, "help": "失败订单总数"},
        {"name": "payments_processed_total", "labels": {"service": "payment-service"}, "value": 7800, "help": "支付处理总数"},
        {"name": "payments_failed_total", "labels": {"service": "payment-service"}, "value": 350, "help": "支付失败总数"},
        {"name": "active_users", "labels": {"service": "user-service"}, "value": 15000, "help": "当前活跃用户数"},
    ]
    
    # 合并所有指标
    all_metrics = (
        cpu_metrics + memory_metrics + db_metrics + 
        kafka_metrics + network_metrics + disk_metrics + 
        http_metrics + business_metrics
    )
    
    for m in all_metrics:
        metrics.append({
            "name": m["name"],
            "labels": m["labels"],
            "value": m["value"],
            "type": "gauge" if "total" not in m["name"] else "counter",
            "help": m["help"],
        })
    
    return metrics


async def init_test_data():
    """Initialize test data with sample entries."""
    global _test_logs
    _test_logs = _generate_sample_logs()
    
    # Generate and push sample metrics to Prometheus
    metrics = _generate_sample_metrics()
    await _push_metrics_to_pushgateway(metrics)


async def get_test_logs(
    query: Optional[str] = None,
    level: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Get test log entries from in-memory storage."""
    if not _test_logs:
        await init_test_data()
    
    results = _test_logs.copy()
    
    if query:
        # Split query into keywords and search for any match
        keywords = query.lower().replace(",", " ").replace("，", " ").split()
        filtered = []
        for log in results:
            msg_lower = log["message"].lower()
            source_lower = log.get("source", "").lower()
            # Match if any keyword is found in message or source
            if any(kw in msg_lower or kw in source_lower for kw in keywords):
                filtered.append(log)
        
        # If no matches found with query, return all logs (fallback)
        if filtered:
            results = filtered
    
    if level:
        results = [log for log in results if log["level"] == level.upper()]
    
    if start_time:
        results = [log for log in results if log["timestamp"] >= start_time]
    
    if end_time:
        results = [log for log in results if log["timestamp"] <= end_time]
    
    return results[:limit]


async def get_test_metrics(
    name: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Get test metrics from Prometheus or generate sample data."""
    metrics = []
    
    # Try to get from Prometheus first
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Query Prometheus for metrics from pushgateway
            params = {"query": name if name else '{job="test_metrics"}'}
            response = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    for result in data.get("data", {}).get("result", [])[:limit]:
                        metric_name = result.get("metric", {}).get("__name__", "unknown")
                        labels = {k: v for k, v in result.get("metric", {}).items() if not k.startswith("__") and k not in ["job", "instance"]}
                        value = float(result.get("value", [0, 0])[1])
                        timestamp = datetime.fromtimestamp(float(result.get("value", [0, 0])[0])).isoformat() + "Z"
                        
                        metrics.append({
                            "id": f"{metric_name}_{hash(str(labels))}",
                            "timestamp": timestamp,
                            "name": metric_name,
                            "labels": labels,
                            "value": value,
                            "type": "gauge",
                        })
    except Exception as e:
        print(f"Error querying Prometheus metrics: {e}")
    
    # If no metrics from Prometheus, generate sample data
    if not metrics:
        sample_metrics = _generate_sample_metrics()
        now = datetime.utcnow().isoformat() + "Z"
        for m in sample_metrics[:limit]:
            metrics.append({
                "id": f"{m['name']}_{hash(str(m['labels']))}",
                "timestamp": now,
                "name": m["name"],
                "labels": m["labels"],
                "value": m["value"],
                "type": m["type"],
            })
    
    return metrics


async def add_test_log(log_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new test log entry to in-memory storage."""
    log_entry = {
        "id": str(uuid.uuid4()),
        "timestamp": log_data.get("timestamp", datetime.utcnow().isoformat() + "Z"),
        "level": log_data.get("level", "INFO").upper(),
        "message": log_data.get("message", ""),
        "source": log_data.get("source", "test-service"),
        "index": log_data.get("index", "test-logs"),
    }
    _test_logs.insert(0, log_entry)
    return log_entry


async def _push_metrics_to_pushgateway(metrics: List[Dict[str, Any]]):
    """Push metrics to Prometheus Pushgateway."""
    # Group metrics by name to avoid duplicate HELP/TYPE lines
    metrics_by_name: Dict[str, List[Dict[str, Any]]] = {}
    for metric in metrics:
        name = metric["name"]
        if name not in metrics_by_name:
            metrics_by_name[name] = []
        metrics_by_name[name].append(metric)
    
    lines = []
    for name, metric_list in metrics_by_name.items():
        first_metric = metric_list[0]
        help_text = first_metric.get("help", f"Test metric {name}")
        metric_type = first_metric.get("type", "gauge")
        
        # Add HELP and TYPE once per metric name
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} {metric_type}")
        
        # Add all values for this metric
        for metric in metric_list:
            labels = metric["labels"]
            value = metric["value"]
            
            if labels:
                labels_str = ",".join([f'{k}="{v}"' for k, v in labels.items()])
                lines.append(f"{name}{{{labels_str}}} {value}")
            else:
                lines.append(f"{name} {value}")
    
    body = "\n".join(lines) + "\n"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{PUSHGATEWAY_URL}/metrics/job/test_metrics",
                content=body,
                headers={"Content-Type": "text/plain"}
            )
            if response.status_code not in [200, 202]:
                print(f"Failed to push metrics: {response.status_code} {response.text}")
    except Exception as e:
        print(f"Error pushing metrics: {e}")


async def add_test_metric(metric_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new test metric to Prometheus via Pushgateway."""
    metric = {
        "name": metric_data.get("name", "test_metric"),
        "labels": metric_data.get("labels", {}),
        "value": metric_data.get("value", 0),
        "type": metric_data.get("type", "gauge"),
        "help": f"Test metric {metric_data.get('name', 'test_metric')}",
    }
    
    await _push_metrics_to_pushgateway([metric])
    
    return {
        "id": f"{metric['name']}_{hash(str(metric['labels']))}",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "name": metric["name"],
        "labels": metric["labels"],
        "value": metric["value"],
        "type": metric["type"],
    }


async def delete_test_log(log_id: str) -> bool:
    """Delete a test log entry from in-memory storage."""
    global _test_logs
    original_len = len(_test_logs)
    _test_logs = [log for log in _test_logs if log["id"] != log_id]
    return len(_test_logs) < original_len


async def delete_test_metric(metric_id: str) -> bool:
    """Delete a test metric - not directly supported by Prometheus."""
    # Prometheus doesn't support deleting individual metrics easily
    return True


async def clear_test_logs():
    """Clear all test logs from in-memory storage."""
    global _test_logs
    _test_logs = []


async def clear_test_metrics():
    """Clear all test metrics from Pushgateway."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.delete(f"{PUSHGATEWAY_URL}/metrics/job/test_metrics")
    except Exception as e:
        print(f"Error clearing metrics: {e}")


async def regenerate_test_data() -> Dict[str, Any]:
    """Regenerate all test data with new samples."""
    global _test_logs
    
    # Clear and regenerate logs
    _test_logs = _generate_sample_logs()
    
    # Clear and regenerate metrics
    await clear_test_metrics()
    metrics = _generate_sample_metrics()
    await _push_metrics_to_pushgateway(metrics)
    
    return {
        "logs_count": len(_test_logs),
        "metrics_count": len(metrics),
    }


async def get_test_data_stats() -> Dict[str, Any]:
    """Get statistics about test data."""
    if not _test_logs:
        await init_test_data()
    
    log_levels = {}
    for log in _test_logs:
        level = log["level"]
        log_levels[level] = log_levels.get(level, 0) + 1
    
    metrics = await get_test_metrics(limit=1000)
    metric_names = {}
    for metric in metrics:
        name = metric["name"]
        metric_names[name] = metric_names.get(name, 0) + 1
    
    return {
        "logs_total": len(_test_logs),
        "logs_by_level": log_levels,
        "metrics_total": len(metrics),
        "metrics_by_name": metric_names,
    }


async def get_test_datasource_config() -> Dict[str, Any]:
    """Get configuration for test data sources."""
    return {
        "logs": {
            "storage": "in-memory",
            "note": "Elasticsearch disabled due to memory constraints (needs 512MB+)",
        },
        "prometheus": {
            "host": "prometheus",
            "port": 9090,
        }
    }
