"""DICOM Server SDK - Python client for Orthanc-compatible DICOMweb servers."""

from dicom_sdk.async_client import AsyncDicomClient
from dicom_sdk.client import DicomClient
from dicom_sdk.exceptions import (
    DicomAuthenticationError,
    DicomConnectionError,
    DicomError,
    DicomNotFoundError,
    DicomServerError,
    DicomValidationError,
)
from dicom_sdk.models import (
    BatchStoreResult,
    DicomTag,
    InstanceMetadata,
    ModalityInfo,
    PatientMetadata,
    QueryParams,
    QueryResult,
    SeriesMetadata,
    ServerStatistics,
    StoreResult,
    StudyMetadata,
)
from dicom_sdk.sync_watcher import ChangeWatcher, SyncWatcher

__version__ = "0.1.0"

__all__ = [
    "DicomClient",
    "AsyncDicomClient",
    "DicomError",
    "DicomConnectionError",
    "DicomNotFoundError",
    "DicomAuthenticationError",
    "DicomValidationError",
    "DicomServerError",
    "BatchStoreResult",
    "DicomTag",
    "InstanceMetadata",
    "ModalityInfo",
    "PatientMetadata",
    "QueryParams",
    "QueryResult",
    "SeriesMetadata",
    "ServerStatistics",
    "StoreResult",
    "StudyMetadata",
    "ChangeWatcher",
    "SyncWatcher",
]
