"""Custom exceptions for SKCC Awards application."""


class SKCCAwardsError(Exception):
    """Base exception for SKCC Awards application."""

    pass


class ValidationError(SKCCAwardsError):
    """Raised when input validation fails."""

    pass


class FileProcessingError(SKCCAwardsError):
    """Raised when file processing fails."""

    pass


class NetworkError(SKCCAwardsError):
    """Raised when network operations fail."""

    pass


class DataParsingError(SKCCAwardsError):
    """Raised when data parsing fails."""

    pass


class CalculationError(SKCCAwardsError):
    """Raised when calculation operations fail."""

    pass


class ConfigurationError(SKCCAwardsError):
    """Raised when configuration is invalid."""

    pass
