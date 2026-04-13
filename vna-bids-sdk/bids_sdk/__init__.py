"""BIDS Server SDK - Python client for BIDSweb API."""

from bids_sdk.client import BidsClient
from bids_sdk.client_async import AsyncBidsClient
from bids_sdk.exceptions import (
    BidsError,
    BidsHTTPError,
    BidsValidationError,
    BidsNotFoundError,
    BidsAuthenticationError,
    BidsServerError,
    BidsTimeoutError,
    BidsConnectionError,
)
from bids_sdk.models import (
    Resource,
    Subject,
    Session,
    Label,
    Annotation,
    Task,
    Webhook,
    Modality,
    QueryResult,
)

__version__ = "0.1.0"

__all__ = [
    "BidsClient",
    "AsyncBidsClient",
    "BidsError",
    "BidsHTTPError",
    "BidsValidationError",
    "BidsNotFoundError",
    "BidsAuthenticationError",
    "BidsServerError",
    "BidsTimeoutError",
    "BidsConnectionError",
    "Resource",
    "Subject",
    "Session",
    "Label",
    "Annotation",
    "Task",
    "Webhook",
    "Modality",
    "QueryResult",
]
