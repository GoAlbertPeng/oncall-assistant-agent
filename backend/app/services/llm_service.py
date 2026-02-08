"""LLM service for alert analysis."""
import json
from typing import Optional
from openai import AsyncOpenAI
from app.config import get_settings
from app.schemas.analysis import AnalysisResult

settings = get_settings()

# Analysis prompt template
ANALYSIS_PROMPT = """你是一位专业的SRE工程师，负责分析告警并定位根因。

## 告警信息
{alert_content}

## 相关日志
{log_context}

## 相关指标
{metrics_context}

请用中文分析以上信息，输出JSON格式的结果：
{{
    "root_cause": "用中文简明描述问题根本原因（2-3句话）",
    "evidence": "用中文引用具体日志或指标作为依据",
    "category": "问题分类，可选值：code_issue(代码问题), config_issue(配置问题), resource_bottleneck(资源瓶颈), dependency_failure(依赖故障)",
    "temporary_solution": "用中文描述临时缓解方案（具体可执行的步骤）",
    "permanent_solution": "用中文描述根本解决方案（长期改进建议）",
    "confidence": 0.0到1.0之间的置信度
}}

重要要求：
1. 所有分析内容必须使用中文输出，不要使用英文
2. 如果日志或指标信息不足，请在evidence中说明，并给出合理的推测
3. category必须是以下之一：code_issue, config_issue, resource_bottleneck, dependency_failure
4. 只输出JSON，不要有其他内容
5. 回答要专业、具体、有针对性"""


def _format_logs(logs: list) -> str:
    """Format log entries for the prompt."""
    if not logs:
        return "无相关日志数据"
    
    formatted = []
    for log in logs[:50]:  # Limit to 50 entries to avoid token limits
        formatted.append(f"[{log.get('timestamp', '')}] [{log.get('level', 'INFO')}] {log.get('message', '')}")
    
    return "\n".join(formatted)


def _format_metrics(metrics: list) -> str:
    """Format metrics for the prompt."""
    if not metrics:
        return "无相关指标数据"
    
    formatted = []
    for metric in metrics[:20]:  # Limit to 20 metrics
        name = metric.get("metric_name", "unknown")
        labels = metric.get("labels", {})
        values = metric.get("values", [])
        
        # Get recent values summary
        if values:
            recent_values = [v.get("value", 0) for v in values[-5:]]
            avg_value = sum(recent_values) / len(recent_values)
            max_value = max(recent_values)
            min_value = min(recent_values)
            formatted.append(
                f"指标: {name} (标签: {labels})\n"
                f"  最近5个值: {recent_values}\n"
                f"  平均值: {avg_value:.2f}, 最大值: {max_value:.2f}, 最小值: {min_value:.2f}"
            )
    
    return "\n".join(formatted) if formatted else "无相关指标数据"


async def analyze_alert(
    alert_content: str,
    logs: list,
    metrics: list,
) -> Optional[AnalysisResult]:
    """
    Analyze an alert using LLM.
    
    Args:
        alert_content: The alert message
        logs: List of log entries
        metrics: List of metric data
    
    Returns:
        AnalysisResult or None if analysis fails
    """
    if settings.llm_provider == "openai":
        return await _analyze_with_openai(alert_content, logs, metrics)
    else:
        # Default to OpenAI compatible API
        return await _analyze_with_openai(alert_content, logs, metrics)


async def _analyze_with_openai(
    alert_content: str,
    logs: list,
    metrics: list,
) -> Optional[AnalysisResult]:
    """Analyze using OpenAI API."""
    if not settings.openai_api_key:
        # Return a mock result for testing
        return AnalysisResult(
            root_cause="API密钥未配置，无法进行分析",
            evidence="请配置LLM API密钥环境变量",
            category="config_issue",
            temporary_solution="配置LLM API密钥",
            permanent_solution="在docker-compose.yml中设置OPENAI_API_KEY",
            confidence=0.0,
        )
    
    prompt = ANALYSIS_PROMPT.format(
        alert_content=alert_content,
        log_context=_format_logs(logs),
        metrics_context=_format_metrics(metrics),
    )
    
    try:
        client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=120.0,  # 60 seconds timeout for Doubao model
        )
        
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": "你是一位专业的SRE工程师，擅长分析系统告警和定位问题根因。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        
        content = response.choices[0].message.content
        
        # Parse JSON response
        # Try to extract JSON from the response
        try:
            # Handle case where response might have markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            result_data = json.loads(content.strip())
            return AnalysisResult(
                root_cause=result_data.get("root_cause", "未能确定根因"),
                evidence=result_data.get("evidence", ""),
                category=result_data.get("category", "code_issue"),
                temporary_solution=result_data.get("temporary_solution", ""),
                permanent_solution=result_data.get("permanent_solution", ""),
                confidence=result_data.get("confidence", 0.5),
            )
        except json.JSONDecodeError:
            # If JSON parsing fails, return a basic result
            return AnalysisResult(
                root_cause=content[:500],
                evidence="LLM返回非JSON格式",
                category="code_issue",
                temporary_solution="请查看原始分析结果",
                permanent_solution="请查看原始分析结果",
                confidence=0.3,
            )
    except Exception as e:
        print(f"LLM analysis error: {e}")
        return AnalysisResult(
            root_cause=f"分析过程出错: {str(e)}",
            evidence="",
            category="code_issue",
            temporary_solution="请检查LLM配置和网络连接",
            permanent_solution="确保API密钥正确且网络畅通",
            confidence=0.0,
        )
