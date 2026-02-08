"""Data source connectors."""
from abc import ABC, abstractmethod
from typing import Dict, Any, List


class BaseConnector(ABC):
    """Base class for all data source connectors."""
    
    def __init__(self, host: str, port: int, auth_token: str = None, config: Dict[str, Any] = None):
        self.host = host
        self.port = port
        self.auth_token = auth_token
        self.config = config or {}
    
    @abstractmethod
    async def test_connection(self) -> tuple[bool, str, float]:
        """
        Test connection to the data source.
        Returns: (success, message, latency_ms)
        """
        pass
    
    @abstractmethod
    async def query(
        self,
        query_str: str,
        start_time: str,
        end_time: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Query data from the data source.
        Returns: List of results
        """
        pass
