"""Pydantic models for DICOM SDK data structures."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class QueryResult(BaseModel):
    """Result from a QIDO-RS query."""

    study_instance_uid: Optional[str] = Field(None, alias="0020000D")
    patient_id: Optional[str] = Field(None, alias="00100020")
    patient_name: Optional[str] = Field(None, alias="00100010")
    study_date: Optional[str] = Field(None, alias="00080020")
    study_description: Optional[str] = Field(None, alias="00081030")
    accession_number: Optional[str] = Field(None, alias="00080050")
    modalities_in_study: Optional[list[str]] = Field(None, alias="00080061")
    number_of_study_related_series: Optional[int] = Field(None, alias="00201206")
    number_of_study_related_instances: Optional[int] = Field(None, alias="00201208")

    model_config = {"populate_by_name": True}


class StudyMetadata(BaseModel):
    """Metadata for a DICOM study."""

    study_instance_uid: str
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    study_date: Optional[str] = None
    study_description: Optional[str] = None
    accession_number: Optional[str] = None
    modalities_in_study: Optional[list[str]] = None
    institution_name: Optional[str] = None
    referring_physician: Optional[str] = None
    number_of_series: Optional[int] = None
    number_of_instances: Optional[int] = None
    series: Optional[list[SeriesMetadata]] = None
    raw_tags: Optional[dict[str, Any]] = None


class SeriesMetadata(BaseModel):
    """Metadata for a DICOM series."""

    study_instance_uid: Optional[str] = None
    series_instance_uid: str
    series_number: Optional[int] = None
    modality: Optional[str] = None
    series_description: Optional[str] = None
    body_part_examined: Optional[str] = None
    number_of_instances: Optional[int] = None
    instances: Optional[list[InstanceMetadata]] = None
    raw_tags: Optional[dict[str, Any]] = None


class InstanceMetadata(BaseModel):
    """Metadata for a DICOM instance."""

    study_instance_uid: Optional[str] = None
    series_instance_uid: Optional[str] = None
    sop_instance_uid: str
    sop_class_uid: Optional[str] = None
    instance_number: Optional[int] = None
    rows: Optional[int] = None
    columns: Optional[int] = None
    bits_allocated: Optional[int] = None
    photometric_interpretation: Optional[str] = None
    raw_tags: Optional[dict[str, Any]] = None


class ServerStatistics(BaseModel):
    """Server statistics from Orthanc."""

    count_patients: int = 0
    count_studies: int = 0
    count_series: int = 0
    count_instances: int = 0
    total_disk_size: Optional[int] = None
    total_uncompressed_size: Optional[int] = None
    disk_size_human: Optional[str] = None

    @property
    def total_patients(self) -> int:
        """Alias for count_patients."""
        return self.count_patients

    @property
    def total_studies(self) -> int:
        """Alias for count_studies."""
        return self.count_studies

    @property
    def total_series(self) -> int:
        """Alias for count_series."""
        return self.count_series

    @property
    def total_instances(self) -> int:
        """Alias for count_instances."""
        return self.count_instances

    @property
    def total_disk_size_mb(self) -> Optional[float]:
        """Total disk size in megabytes."""
        if self.total_disk_size is None:
            return None
        return round(self.total_disk_size / (1024 * 1024), 2)


class ModalityInfo(BaseModel):
    """Information about a configured modality."""

    name: str
    aet: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None


class StoreResult(BaseModel):
    """Result from a STOW-RS store operation."""

    success: bool
    study_instance_uid: Optional[str] = None
    series_instance_uid: Optional[str] = None
    sop_instance_uid: Optional[str] = None
    status_code: Optional[int] = None
    message: Optional[str] = None


class BatchStoreResult(BaseModel):
    """Result from a batch store operation."""

    total: int
    succeeded: int
    failed: int
    results: list[StoreResult]
    errors: list[dict[str, Any]]


class DicomTag(BaseModel):
    """A single DICOM tag with value."""

    group: str
    element: str
    vr: Optional[str] = None
    value: Optional[str] = None
    name: Optional[str] = None

    @property
    def tag_id(self) -> str:
        return f"({self.group},{self.element})"


class PatientMetadata(BaseModel):
    """Patient-level metadata from DICOM."""

    patient_id: Optional[str] = Field(None, alias="00100020")
    patient_name: Optional[str] = Field(None, alias="00100010")
    patient_birth_date: Optional[str] = Field(None, alias="00100030")
    patient_sex: Optional[str] = Field(None, alias="00100040")
    patient_age: Optional[str] = Field(None, alias="00101010")
    patient_address: Optional[str] = Field(None, alias="00101040")
    other_patient_ids: Optional[str] = Field(None, alias="00101020")
    patient_telephone_numbers: Optional[str] = Field(None, alias="00102110")
    raw_tags: Optional[dict[str, Any]] = None

    model_config = {"populate_by_name": True}


class QueryParams(BaseModel):
    """Query parameters for flexible QIDO-RS queries."""

    level: str = "study"
    limit: int = 100
    offset: int = 0
    fuzzy_matching: bool = False
    case_sensitive: bool = False
    study_uid: Optional[str] = None
    series_uid: Optional[str] = None
    instance_uid: Optional[str] = None
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    patient_birth_date: Optional[str] = None
    study_date: Optional[str] = None
    study_date_from: Optional[str] = None
    study_date_to: Optional[str] = None
    modality: Optional[str] = None
    series_description: Optional[str] = None
    study_description: Optional[str] = None
    accession_number: Optional[str] = None
    referring_physician_name: Optional[str] = None
    institution_name: Optional[str] = None
    operator_name: Optional[str] = None
    body_part: Optional[str] = None
