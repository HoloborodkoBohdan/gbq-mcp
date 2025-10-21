"""BigQuery client lifecycle management service."""

from abc import ABC, abstractmethod
from typing import Optional

from google.cloud import bigquery
from google.oauth2 import service_account

from .configuration import IConfigurationProvider


class IBigQueryClient(ABC):
    """Interface for BigQuery client."""

    @abstractmethod
    def get_client(self) -> bigquery.Client:
        """Get BigQuery client instance."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close client and cleanup resources."""
        pass


class BigQueryClientService(IBigQueryClient):
    """BigQuery client lifecycle management."""

    def __init__(self, config_provider: IConfigurationProvider):
        self._config = config_provider
        self._client: Optional[bigquery.Client] = None
        self._project_id: Optional[str] = None

    def initialize(self) -> None:
        """Initialize BigQuery client."""
        if self._client is not None:
            return

        service_account_path = self._config.get_service_account_path()

        if service_account_path:
            credentials = service_account.Credentials.from_service_account_file(
                service_account_path,
                scopes=['https://www.googleapis.com/auth/bigquery']
            )
            self._project_id = self._config.get_project_id()
            self._client = bigquery.Client(
                credentials=credentials,
                project=self._project_id
            )
        else:
            self._client = bigquery.Client()
            self._project_id = self._client.project

    def get_client(self) -> bigquery.Client:
        """Get BigQuery client instance."""
        if self._client is None:
            raise RuntimeError(
                "BigQuery client not initialized. Call initialize() first."
            )
        return self._client

    def get_project_id(self) -> Optional[str]:
        """Get current project ID."""
        return self._project_id

    def close(self) -> None:
        """Close client and cleanup resources."""
        if self._client is not None:
            self._client.close()
            self._client = None
            self._project_id = None
