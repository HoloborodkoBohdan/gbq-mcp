"""Configuration management service."""

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional

from dotenv import load_dotenv


@dataclass
class AccessConfig:
    """Access control configuration."""
    allowed_tables: list[str]
    allowed_datasets: Dict[str, Dict[str, Any]]
    allowed_patterns: list[str]


@dataclass
class QueryLimits:
    """Query execution limits."""
    max_results: int
    maximum_bytes_billed: int


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
        load_dotenv()

        self._access_config = access_config or self._load_access_config()
        self._query_limits = query_limits or self._load_query_limits()
        self._service_account_path = service_account_path or self._load_service_account_path()

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

    def _load_service_account_path(self) -> str:
        """Load service account path from environment or default."""
        env_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if env_path:
            return env_path

        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(script_dir, "service-account.json")

    def _load_query_limits(self) -> QueryLimits:
        """Load query limits from environment variables."""
        max_results = int(os.getenv("MAX_QUERY_RESULTS", "10000"))
        max_bytes_mb = int(os.getenv("MAX_BYTES_BILLED_MB", "100"))

        return QueryLimits(
            max_results=max_results,
            maximum_bytes_billed=max_bytes_mb * 1024 * 1024
        )

    def _load_access_config(self) -> AccessConfig:
        """Load access configuration from environment or file."""
        access_control_file = os.getenv("ACCESS_CONTROL_FILE", "./access-control.json")

        if os.path.exists(access_control_file):
            try:
                with open(access_control_file, 'r') as f:
                    config_data = json.load(f)
                    return AccessConfig(
                        allowed_tables=config_data.get("allowed_tables", []),
                        allowed_datasets=config_data.get("allowed_datasets", {}),
                        allowed_patterns=config_data.get("allowed_patterns", [])
                    )
            except (IOError, json.JSONDecodeError) as e:
                print(f"Warning: Failed to load {access_control_file}: {e}")

        return self._get_default_access_config()

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
