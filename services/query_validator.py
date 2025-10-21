"""Query validation service."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple, List


@dataclass
class ValidationResult:
    """Result of query validation."""
    is_valid: bool
    error_message: str = ""


class IQueryValidator(ABC):
    """Interface for query validators."""

    @abstractmethod
    def validate(self, query: str) -> ValidationResult:
        """Validate a query."""
        pass


class SelectOnlyValidator(IQueryValidator):
    """Validator ensuring only SELECT queries are allowed."""

    def validate(self, query: str) -> ValidationResult:
        """Validate query starts with SELECT."""
        normalized = self._normalize_query(query)
        query_upper = normalized.upper()

        if not re.match(r'^SELECT\s', query_upper):
            return ValidationResult(
                is_valid=False,
                error_message="Only SELECT queries are allowed. Query must start with SELECT."
            )

        return ValidationResult(is_valid=True)

    @staticmethod
    def _normalize_query(query: str) -> str:
        """Normalize query by removing comments and string literals."""
        normalized = re.sub(r'\s+', ' ', query.strip())
        # Remove comments
        normalized = re.sub(r'/\*.*?\*/', ' ', normalized, flags=re.DOTALL)
        normalized = re.sub(r'--[^\n]*', ' ', normalized)
        # Remove string literals
        normalized = re.sub(r"'(?:[^']|'')*'", ' ', normalized)
        normalized = re.sub(r'"(?:[^"]|"")*"', ' ', normalized)
        return normalized.strip()


class ForbiddenKeywordValidator(IQueryValidator):
    """Validator checking for forbidden SQL keywords."""

    FORBIDDEN_KEYWORDS = (
        "DELETE", "UPDATE", "INSERT", "CREATE", "DROP", "ALTER",
        "MERGE", "TRUNCATE", "REPLACE", "GRANT", "REVOKE"
    )

    def __init__(self, forbidden_keywords: Tuple[str, ...] = None):
        self._forbidden_keywords = forbidden_keywords or self.FORBIDDEN_KEYWORDS

    def validate(self, query: str) -> ValidationResult:
        """Validate query doesn't contain forbidden keywords."""
        normalized = SelectOnlyValidator._normalize_query(query)
        query_upper = normalized.upper()

        for keyword in self._forbidden_keywords:
            if re.search(rf'\b{keyword}\b', query_upper):
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Forbidden keyword '{keyword}' detected. Only SELECT queries are allowed."
                )

        return ValidationResult(is_valid=True)


class MultiStatementValidator(IQueryValidator):
    """Validator ensuring single statement queries."""

    def validate(self, query: str) -> ValidationResult:
        """Validate query is a single statement."""
        normalized = SelectOnlyValidator._normalize_query(query)

        # Check for semicolons (excluding trailing semicolon)
        if ';' in normalized.rstrip(';'):
            return ValidationResult(
                is_valid=False,
                error_message="Multiple statements not allowed. Only single SELECT queries permitted."
            )

        return ValidationResult(is_valid=True)


class CompositeQueryValidator(IQueryValidator):
    """Composite validator that runs multiple validators."""

    def __init__(self, validators: List[IQueryValidator] = None):
        self._validators = validators or self._get_default_validators()

    def validate(self, query: str) -> ValidationResult:
        """Run all validators in sequence."""
        for validator in self._validators:
            result = validator.validate(query)
            if not result.is_valid:
                return result

        return ValidationResult(is_valid=True)

    def add_validator(self, validator: IQueryValidator) -> None:
        """Add a new validator to the chain."""
        self._validators.append(validator)

    @staticmethod
    def _get_default_validators() -> List[IQueryValidator]:
        """Get default validators for BigQuery queries."""
        return [
            SelectOnlyValidator(),
            ForbiddenKeywordValidator(),
            MultiStatementValidator()
        ]


class QueryValidatorService:
    """Main query validation service."""

    def __init__(self, validator: IQueryValidator = None):
        self._validator = validator or CompositeQueryValidator()

    def validate_query_safety(self, query: str) -> Tuple[bool, str]:
        """Validate query safety."""
        result = self._validator.validate(query)
        return result.is_valid, result.error_message

    def validate_or_raise(self, query: str) -> None:
        """Validate query and raise ValueError if invalid."""
        is_valid, error_message = self.validate_query_safety(query)
        if not is_valid:
            raise ValueError(f"Query validation failed: {error_message}")
