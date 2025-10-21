"""Configuration management service."""

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class AccessConfig:
    """Access control configuration."""
    allowed_tables: list[str]
    allowed_datasets: Dict[str, Dict[str, Any]]
    allowed_patterns: list[str]


@dataclass
class QueryLimits:
    """Query execution limits."""
    max_results: int = 10000
    maximum_bytes_billed: int = 100 * 1024 * 1024  # 100 MB


class IConfigurationProvider(ABC):
    """Interface for configuration providers."""

    @abstractmethod
    def get_access_config(self) -> AccessConfig:
        """Get access control configuration."""
        pass

    @abstractmethod
    def get_query_limits(self) -> QueryLimits:
        """Get query execution limits."""
        pass

    @abstractmethod
    def get_service_account_path(self) -> Optional[str]:
        """Get service account file path."""
        pass


class ConfigurationService(IConfigurationProvider):
    """Configuration management service."""

    def __init__(
        self,
        access_config: Optional[AccessConfig] = None,
        query_limits: Optional[QueryLimits] = None,
        service_account_path: Optional[str] = None
    ):
        self._access_config = access_config or self._get_default_access_config()
        self._query_limits = query_limits or QueryLimits()
        self._service_account_path = service_account_path or self._get_default_service_account_path()

    def get_access_config(self) -> AccessConfig:
        """Get access control configuration."""
        return self._access_config

    def get_query_limits(self) -> QueryLimits:
        """Get query execution limits."""
        return self._query_limits

    def get_service_account_path(self) -> Optional[str]:
        """Get service account file path if it exists."""
        if self._service_account_path and os.path.exists(self._service_account_path):
            return self._service_account_path
        return None

    def get_project_id(self) -> Optional[str]:
        """Get project ID from service account file."""
        sa_path = self.get_service_account_path()
        if sa_path:
            try:
                with open(sa_path, 'r') as f:
                    service_account_info = json.load(f)
                    return service_account_info.get('project_id')
            except (IOError, json.JSONDecodeError):
                return None
        return None

    @staticmethod
    def _get_default_service_account_path() -> str:
        """Get default service account path."""
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(script_dir, "service-account.json")

    @staticmethod
    def _get_default_access_config() -> AccessConfig:
        """Get default access control configuration."""
        return AccessConfig(
            allowed_tables=[
                "bigquery-public-data.iowa_liquor_sales.sales",
            ],
            allowed_datasets={
                "bigquery-public-data.austin_bikeshare": {
                    "allow_all_tables": True,
                    "blacklisted_tables": []
                },
            },
            allowed_patterns=[]
        )


class EnvironmentConfigurationService(ConfigurationService):
    """Configuration service that loads from environment variables."""

    def __init__(self):
        access_config = self._load_access_config_from_env()
        query_limits = self._load_query_limits_from_env()
        service_account_path = os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS",
            self._get_default_service_account_path()
        )

        super().__init__(access_config, query_limits, service_account_path)

    @staticmethod
    def _load_access_config_from_env() -> AccessConfig:
        """Load access configuration from environment variables."""
        allowed_tables_str = os.getenv("ALLOWED_TABLES", "")
        allowed_tables = [
            table.strip()
            for table in allowed_tables_str.split(",")
            if table.strip()
        ] if allowed_tables_str else []

        if not allowed_tables:
            return ConfigurationService._get_default_access_config()

        return AccessConfig(
            allowed_tables=allowed_tables,
            allowed_datasets={},
            allowed_patterns=[]
        )

    @staticmethod
    def _load_query_limits_from_env() -> QueryLimits:
        """Load query limits from environment variables."""
        max_results = int(os.getenv("MAX_QUERY_RESULTS", "10000"))
        max_bytes_mb = int(os.getenv("MAX_BYTES_BILLED_MB", "100"))

        return QueryLimits(
            max_results=max_results,
            maximum_bytes_billed=max_bytes_mb * 1024 * 1024
        )
