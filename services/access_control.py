"""Access control service."""

import re
import fnmatch
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

from .configuration import AccessConfig


@dataclass
class TableReference:
    """Represents a parsed table reference."""
    full_name: str
    project: str = ""
    dataset: str = ""
    table: str = ""

    @classmethod
    def parse(cls, table_id: str) -> 'TableReference':
        """Parse table ID into components."""
        parts = table_id.split('.')
        if len(parts) >= 3:
            return cls(
                full_name=table_id,
                project=parts[0],
                dataset=parts[1],
                table=parts[2]
            )
        elif len(parts) == 2:
            return cls(
                full_name=table_id,
                dataset=parts[0],
                table=parts[1]
            )
        else:
            return cls(full_name=table_id, table=parts[0] if parts else "")

    def get_dataset_id(self) -> str:
        """Get dataset ID (project.dataset)."""
        if self.project and self.dataset:
            return f"{self.project}.{self.dataset}"
        return self.dataset


class IAccessStrategy(ABC):
    """Interface for access control strategies."""

    @abstractmethod
    def is_allowed(self, table_ref: TableReference) -> bool:
        """Check if table access is allowed."""
        pass


class ExplicitTableAccessStrategy(IAccessStrategy):
    """Strategy for explicit table whitelist."""

    def __init__(self, allowed_tables: List[str]):
        self._allowed_tables = [t.lower() for t in allowed_tables]

    def is_allowed(self, table_ref: TableReference) -> bool:
        """Check if table is in explicit whitelist."""
        return table_ref.full_name.lower() in self._allowed_tables


class DatasetAccessStrategy(IAccessStrategy):
    """Strategy for dataset-level access with optional blacklist."""

    def __init__(self, allowed_datasets: dict):
        self._allowed_datasets = {
            k.lower(): v for k, v in allowed_datasets.items()
        }

    def is_allowed(self, table_ref: TableReference) -> bool:
        """Check if table's dataset is allowed and table not blacklisted."""
        dataset_id = table_ref.get_dataset_id().lower()

        if dataset_id not in self._allowed_datasets:
            return False

        config = self._allowed_datasets[dataset_id]
        blacklist = config.get("blacklisted_tables", [])
        blacklist_lower = [t.lower() for t in blacklist]

        # Check if table is blacklisted
        if table_ref.table.lower() in blacklist_lower:
            return False

        return True


class PatternAccessStrategy(IAccessStrategy):
    """Strategy for pattern-based access (wildcard matching)."""

    def __init__(self, allowed_patterns: List[str]):
        self._allowed_patterns = [p.lower() for p in allowed_patterns]

    def is_allowed(self, table_ref: TableReference) -> bool:
        """Check if table matches any allowed pattern."""
        table_lower = table_ref.full_name.lower()

        for pattern in self._allowed_patterns:
            if fnmatch.fnmatch(table_lower, pattern):
                return True

        return False


class CompositeAccessStrategy(IAccessStrategy):
    """Composite strategy that checks multiple strategies (OR logic)."""

    def __init__(self, strategies: List[IAccessStrategy]):
        self._strategies = strategies

    def is_allowed(self, table_ref: TableReference) -> bool:
        """Check if any strategy allows access (OR logic)."""
        for strategy in self._strategies:
            if strategy.is_allowed(table_ref):
                return True
        return False

    def add_strategy(self, strategy: IAccessStrategy) -> None:
        """Add a new strategy to the composite."""
        self._strategies.append(strategy)


class AccessControlService:
    """Main access control service."""

    def __init__(self, access_config: AccessConfig):
        self._access_config = access_config
        self._strategy = self._build_strategy(access_config)

    def is_table_allowed(self, table_id: str) -> bool:
        """Check if table access is allowed."""
        table_ref = TableReference.parse(table_id)
        return self._strategy.is_allowed(table_ref)

    def validate_query_tables(self, query: str) -> None:
        """Validate all tables in query are allowed."""
        tables = self._extract_tables_from_query(query)

        for table in tables:
            if not self.is_table_allowed(table):
                raise ValueError(
                    f"Table '{table}' is not allowed. "
                    f"Check allowed_tables, allowed_datasets, or allowed_patterns."
                )

    def get_all_allowed_tables(self) -> List[str]:
        """Get list of all allowed table patterns."""
        all_tables = []

        # Add explicit tables
        all_tables.extend(self._access_config.allowed_tables)

        # Add datasets (show as dataset.*)
        for dataset_id in self._access_config.allowed_datasets.keys():
            all_tables.append(f"{dataset_id}.*")

        # Add patterns
        all_tables.extend(self._access_config.allowed_patterns)

        return all_tables

    @staticmethod
    def _extract_tables_from_query(query: str) -> List[str]:
        """Extract table references from SQL query."""
        query_lower = query.lower()
        table_pattern = r'(?:from|join)\s+([`"]?[\w\-\.]+[`"]?)'
        found_tables = re.findall(table_pattern, query_lower, re.IGNORECASE)

        # Clean up table names (remove backticks/quotes and whitespace)
        return [table.strip('`"').strip() for table in found_tables]

    @staticmethod
    def _build_strategy(access_config: AccessConfig) -> IAccessStrategy:
        """Build composite access strategy from configuration."""
        strategies = []

        # Add explicit table strategy
        if access_config.allowed_tables:
            strategies.append(
                ExplicitTableAccessStrategy(access_config.allowed_tables)
            )

        # Add dataset strategy
        if access_config.allowed_datasets:
            strategies.append(
                DatasetAccessStrategy(access_config.allowed_datasets)
            )

        # Add pattern strategy
        if access_config.allowed_patterns:
            strategies.append(
                PatternAccessStrategy(access_config.allowed_patterns)
            )

        return CompositeAccessStrategy(strategies)
