"""Loki connector for log data source."""
import time
from typing import Dict, Any, List
from datetime import datetime
import httpx
from app.connectors import BaseConnector


class LokiConnector(BaseConnector):
    """Connector for Grafana Loki."""
    
    def _get_base_url(self) -> str:
        """Get the base URL for Loki."""
        protocol = self.config.get("protocol", "http")
        return f"{protocol}://{self.host}:{self.port}"
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers
    
    def _iso_to_nanoseconds(self, iso_time: str) -> str:
        """Convert ISO time to nanoseconds timestamp."""
        dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
        return str(int(dt.timestamp() * 1e9))
    
    async def test_connection(self) -> tuple[bool, str, float]:
        """Test connection to Loki."""
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self._get_base_url()}/ready",
                    headers=self._get_headers(),
                )
                latency = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    return True, "Connected. Loki is ready.", latency
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
        Query logs from Loki using LogQL.
        
        Args:
            query_str: LogQL query or simple keyword (will be converted to LogQL)
            start_time: ISO format start time
            end_time: ISO format end time
            **kwargs: Additional parameters like labels, limit
        """
        labels = kwargs.get("labels") or self.config.get("labels", {})
        limit = kwargs.get("limit", 100)
        
        # Build LogQL query
        # If query_str looks like LogQL (starts with {), use it directly
        # Otherwise, build a simple query
        if query_str.startswith("{"):
            logql = query_str
        else:
            # Build label selector
            if labels:
                label_parts = [f'{k}="{v}"' for k, v in labels.items()]
                label_selector = "{" + ",".join(label_parts) + "}"
            else:
                label_selector = '{job=~".+"}'  # Match all jobs
            
            # Add line filter if query_str provided
            if query_str:
                logql = f'{label_selector} |~ "{query_str}"'
            else:
                logql = label_selector
        
        params = {
            "query": logql,
            "start": self._iso_to_nanoseconds(start_time),
            "end": self._iso_to_nanoseconds(end_time),
            "limit": limit,
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self._get_base_url()}/loki/api/v1/query_range",
                    headers=self._get_headers(),
                    params=params,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    results = []
                    
                    for stream in data.get("data", {}).get("result", []):
                        stream_labels = stream.get("stream", {})
                        source = stream_labels.get("job", stream_labels.get("app", "unknown"))
                        
                        for value in stream.get("values", []):
                            timestamp_ns, log_line = value
                            # Convert nanoseconds to ISO format
                            timestamp = datetime.fromtimestamp(int(timestamp_ns) / 1e9).isoformat()
                            
                            # Try to extract log level from the line
                            level = "INFO"
                            log_lower = log_line.lower()
                            if "error" in log_lower:
                                level = "ERROR"
                            elif "warn" in log_lower:
                                level = "WARN"
                            elif "debug" in log_lower:
                                level = "DEBUG"
                            
                            results.append({
                                "timestamp": timestamp,
                                "level": level,
                                "message": log_line,
                                "source": source,
                            })
                    
                    return results
                else:
                    return []
        except Exception as e:
            print(f"Loki query error: {e}")
            return []
