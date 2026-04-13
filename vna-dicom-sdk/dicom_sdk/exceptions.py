"""Custom exceptions for the DICOM SDK."""


class DicomError(Exception):
    """Base exception for all DICOM SDK errors."""

    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        self.message = message
        super().__init__(self.message)


class DicomConnectionError(DicomError):
    """Raised when connection to the DICOM server fails."""


class DicomAuthenticationError(DicomError):
    """Raised when authentication with the DICOM server fails."""

    def __init__(self, message: str = "Authentication failed", status_code: int | None = 401):
        super().__init__(message, status_code)


class DicomNotFoundError(DicomError):
    """Raised when a requested resource is not found."""

    def __init__(self, message: str = "Resource not found", status_code: int | None = 404):
        super().__init__(message, status_code)


class DicomValidationError(DicomError):
    """Raised when input validation fails."""


class DicomServerError(DicomError):
    """Raised when the DICOM server returns a server error."""

    def __init__(self, message: str = "Server error", status_code: int | None = 500):
        super().__init__(message, status_code)
