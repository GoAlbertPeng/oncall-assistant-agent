"""Prometheus connector for metrics data source."""
import time
from typing import Dict, Any, List
from datetime import datetime
import httpx
from app.connectors import BaseConnector


class PrometheusConnector(BaseConnector):
    """Connector for Prometheus metrics."""
    
    def _get_base_url(self) -> str:
        """Get the base URL for Prometheus."""
        protocol = self.config.get("protocol", "http")
        return f"{protocol}://{self.host}:{self.port}"
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers
    
    async def test_connection(self) -> tuple[bool, str, float]:
        """Test connection to Prometheus."""
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self._get_base_url()}/-/ready",
                    headers=self._get_headers(),
                )
                latency = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    return True, "Connected. Prometheus is ready.", latency
                else:
                    # Try alternative health endpoint
                    response = await client.get(
                        f"{self._get_base_url()}/api/v1/status/config",
                        headers=self._get_headers(),
                    )
                    if response.status_code == 200:
                        return True, "Connected. Prometheus is ready.", latency
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
        Query metrics from Prometheus.
        
        Args:
            query_str: PromQL query
            start_time: ISO format start time
            end_time: ISO format end time
            **kwargs: Additional parameters like step
        """
        step = kwargs.get("step", "60s")  # Default 1 minute resolution
        
        # Convert ISO time to Unix timestamp
        start_ts = datetime.fromisoformat(start_time.replace("Z", "+00:00")).timestamp()
        end_ts = datetime.fromisoformat(end_time.replace("Z", "+00:00")).timestamp()
        
        params = {
            "query": query_str,
            "start": start_ts,
            "end": end_ts,
            "step": step,
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self._get_base_url()}/api/v1/query_range",
                    headers=self._get_headers(),
                    params=params,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    results = []
                    
                    if data.get("status") == "success":
                        for result in data.get("data", {}).get("result", []):
                            metric_name = result.get("metric", {}).get("__name__", "unknown")
                            labels = {k: v for k, v in result.get("metric", {}).items() if k != "__name__"}
                            
                            values = []
                            for value in result.get("values", []):
                                timestamp, val = value
                                values.append({
                                    "timestamp": datetime.fromtimestamp(timestamp).isoformat(),
                                    "value": float(val),
                                })
                            
                            results.append({
                                "metric_name": metric_name,
                                "labels": labels,
                                "values": values,
                            })
                    
                    return results
                else:
                    return []
        except Exception as e:
            print(f"Prometheus query error: {e}")
            return []
    
    async def query_instant(self, query_str: str) -> List[Dict[str, Any]]:
        """
        Execute an instant query against Prometheus.
        
        Args:
            query_str: PromQL query
        """
        params = {"query": query_str}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self._get_base_url()}/api/v1/query",
                    headers=self._get_headers(),
                    params=params,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    results = []
                    
                    if data.get("status") == "success":
                        for result in data.get("data", {}).get("result", []):
                            metric_name = result.get("metric", {}).get("__name__", "unknown")
                            labels = {k: v for k, v in result.get("metric", {}).items() if k != "__name__"}
                            
                            timestamp, value = result.get("value", [0, 0])
                            results.append({
                                "metric_name": metric_name,
                                "labels": labels,
                                "timestamp": datetime.fromtimestamp(timestamp).isoformat(),
                                "value": float(value),
                            })
                    
                    return results
                else:
                    return []
        except Exception as e:
            print(f"Prometheus instant query error: {e}")
            return []
