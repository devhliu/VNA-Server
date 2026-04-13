"""Custom exceptions for the BIDS Server SDK."""

from typing import Any, Optional


class BidsError(Exception):
    """Base exception for all BIDS SDK errors."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.details = details


class BidsHTTPError(BidsError):
    """Raised when the BIDS server returns an HTTP error."""

    def __init__(
        self,
        message: str,
        status_code: int,
        response_body: Optional[Any] = None,
        headers: Optional[dict] = None,
    ):
        super().__init__(message, details=response_body)
        self.status_code = status_code
        self.response_body = response_body
        self.headers = headers or {}


class BidsValidationError(BidsError):
    """Raised when request validation fails."""

    pass


class BidsNotFoundError(BidsHTTPError):
    """Raised when a requested resource is not found (404)."""

    def __init__(self, message: str = "Resource not found", **kwargs: Any):
        super().__init__(message, status_code=404, **kwargs)


class BidsAuthenticationError(BidsHTTPError):
    """Raised when authentication fails (401)."""

    def __init__(self, message: str = "Authentication failed", **kwargs: Any):
        super().__init__(message, status_code=401, **kwargs)


class BidsServerError(BidsHTTPError):
    """Raised when the server returns a 5xx error."""

    pass


class BidsTimeoutError(BidsError):
    """Raised when a request times out."""

    def __init__(self, message: str = "Request timed out"):
        super().__init__(message)


class BidsConnectionError(BidsError):
    """Raised when connection to the server fails."""

    def __init__(self, message: str = "Connection to BIDS server failed"):
        super().__init__(message)
