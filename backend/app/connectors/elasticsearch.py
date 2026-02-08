"""Elasticsearch connector for ELK data source."""
import time
from typing import Dict, Any, List
import httpx
from app.connectors import BaseConnector


class ElasticsearchConnector(BaseConnector):
    """Connector for Elasticsearch / ELK stack."""
    
    def _get_base_url(self) -> str:
        """Get the base URL for Elasticsearch."""
        protocol = self.config.get("protocol", "http")
        return f"{protocol}://{self.host}:{self.port}"
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers
    
    async def test_connection(self) -> tuple[bool, str, float]:
        """Test connection to Elasticsearch."""
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self._get_base_url()}/_cluster/health",
                    headers=self._get_headers(),
                )
                latency = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "unknown")
                    return True, f"Connected. Cluster status: {status}", latency
                else:
                    return False, f"Connection failed: HTTP {response.status_code}", latency
        except httpx.TimeoutException:
            latency = (time.time() - start_time) * 1000
            return False, "Connection timeout", latency
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return False, f"Connection error: {str(e)}", latency
    
    async def query(
        self,
        query_str: str,
        start_time: str,
        end_time: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Query logs from Elasticsearch.
        
        Args:
            query_str: Search query (keywords to search in logs)
            start_time: ISO format start time
            end_time: ISO format end time
            **kwargs: Additional parameters like index, size, log_level
        """
        index = kwargs.get("index") or self.config.get("index", "*")
        size = kwargs.get("size", 100)
        log_level = kwargs.get("log_level")  # Optional: ERROR, WARN, INFO
        
        # Build Elasticsearch query
        must_clauses = [
            {
                "range": {
                    "@timestamp": {
                        "gte": start_time,
                        "lte": end_time,
                    }
                }
            }
        ]
        
        if query_str:
            must_clauses.append({
                "query_string": {
                    "query": query_str,
                    "default_field": "message",
                }
            })
        
        if log_level:
            must_clauses.append({
                "match": {"level": log_level}
            })
        
        query_body = {
            "query": {
                "bool": {
                    "must": must_clauses
                }
            },
            "sort": [{"@timestamp": {"order": "desc"}}],
            "size": size,
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._get_base_url()}/{index}/_search",
                    headers=self._get_headers(),
                    json=query_body,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    hits = data.get("hits", {}).get("hits", [])
                    
                    results = []
                    for hit in hits:
                        source = hit.get("_source", {})
                        results.append({
                            "timestamp": source.get("@timestamp", ""),
                            "level": source.get("level", "INFO"),
                            "message": source.get("message", ""),
                            "source": source.get("source", hit.get("_index", "")),
                        })
                    return results
                else:
                    return []
        except Exception as e:
            print(f"Elasticsearch query error: {e}")
            return []
