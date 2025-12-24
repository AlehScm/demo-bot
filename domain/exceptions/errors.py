class DomainError(Exception):
    """Base class for domain-specific errors."""


class DataProviderError(DomainError):
    """Raised when a data provider fails to deliver valid data."""


class UnsupportedTimeframeError(DomainError):
    """Raised when a timeframe is not supported by the current policy."""
