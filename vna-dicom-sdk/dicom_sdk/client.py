"""Synchronous DICOMweb client for Orthanc-compatible servers."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, BinaryIO, Optional, Union
from urllib.parse import urlencode

import httpx

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

logger = logging.getLogger(__name__)
_DICOMWEB_PREFIX = "/dicom-web"


def _raise_for_status(response: httpx.Response) -> None:
    """Convert HTTP errors to DICOM SDK exceptions."""
    if response.is_success:
        return
    status = response.status_code
    try:
        detail = response.json().get("details", response.text)
    except (json.JSONDecodeError, ValueError):
        detail = response.text
    if status == 401:
        raise DicomAuthenticationError(detail, status)
    elif status == 404:
        raise DicomNotFoundError(detail, status)
    elif 400 <= status < 500:
        raise DicomValidationError(detail, status)
    elif status >= 500:
        raise DicomServerError(detail, status)
    else:
        raise DicomError(detail, status)


def _safe_int(value: Any) -> Optional[int]:
    """Safely convert a value to int, returning None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _tag_value(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = item.get(key)
        if isinstance(value, dict):
            nested = value.get("Value")
            if isinstance(nested, list) and nested:
                return nested[0]
            if nested is not None:
                return nested
            if "Alphabetic" in value:
                return value.get("Alphabetic")
        elif value is not None:
            return value
    return None


def _qido_to_query_result(item: dict[str, Any]) -> QueryResult:
    return QueryResult(
        study_instance_uid=_tag_value(item, "StudyInstanceUID", "0020000D"),
        patient_id=_tag_value(item, "PatientID", "00100020"),
        patient_name=_tag_value(item, "PatientName", "00100010"),
        study_date=_tag_value(item, "StudyDate", "00080020"),
        study_description=_tag_value(item, "StudyDescription", "00081030"),
        accession_number=_tag_value(item, "AccessionNumber", "00080050"),
        modalities_in_study=_tag_value(item, "ModalitiesInStudy", "00080061"),
        number_of_study_related_series=_safe_int(_tag_value(item, "NumberOfStudyRelatedSeries", "00201206")),
        number_of_study_related_instances=_safe_int(_tag_value(item, "NumberOfStudyRelatedInstances", "00201208")),
    )


def _qido_to_study(item: dict[str, Any]) -> StudyMetadata:
    return StudyMetadata(
        study_instance_uid=_tag_value(item, "StudyInstanceUID", "0020000D") or "",
        patient_id=_tag_value(item, "PatientID", "00100020"),
        patient_name=_tag_value(item, "PatientName", "00100010"),
        study_date=_tag_value(item, "StudyDate", "00080020"),
        study_description=_tag_value(item, "StudyDescription", "00081030"),
        accession_number=_tag_value(item, "AccessionNumber", "00080050"),
        modalities_in_study=_tag_value(item, "ModalitiesInStudy", "00080061"),
        institution_name=_tag_value(item, "InstitutionName", "00080080"),
        referring_physician=_tag_value(item, "ReferringPhysicianName", "00080090"),
        number_of_series=_safe_int(_tag_value(item, "NumberOfStudyRelatedSeries", "00201206")),
        number_of_instances=_safe_int(_tag_value(item, "NumberOfStudyRelatedInstances", "00201208")),
        raw_tags=item,
    )


def _qido_to_series(item: dict[str, Any], study_uid: Optional[str] = None) -> SeriesMetadata:
    return SeriesMetadata(
        study_instance_uid=study_uid or _tag_value(item, "StudyInstanceUID", "0020000D"),
        series_instance_uid=_tag_value(item, "SeriesInstanceUID", "0020000E") or "",
        series_number=_safe_int(_tag_value(item, "SeriesNumber", "00200011")),
        modality=_tag_value(item, "Modality", "00080060"),
        series_description=_tag_value(item, "SeriesDescription", "0008103E"),
        body_part_examined=_tag_value(item, "BodyPartExamined", "00180015"),
        number_of_instances=_safe_int(_tag_value(item, "NumberOfSeriesRelatedInstances", "00201209")),
        raw_tags=item,
    )


def _metadata_to_instance(item: dict[str, Any]) -> InstanceMetadata:
    return InstanceMetadata(
        study_instance_uid=_tag_value(item, "StudyInstanceUID", "0020000D"),
        series_instance_uid=_tag_value(item, "SeriesInstanceUID", "0020000E"),
        sop_instance_uid=_tag_value(item, "SOPInstanceUID", "00080018") or "",
        sop_class_uid=_tag_value(item, "SOPClassUID", "00080016"),
        instance_number=_safe_int(_tag_value(item, "InstanceNumber", "00200013")),
        rows=_safe_int(_tag_value(item, "Rows", "00280010")),
        columns=_safe_int(_tag_value(item, "Columns", "00280011")),
        bits_allocated=_safe_int(_tag_value(item, "BitsAllocated", "00280100")),
        photometric_interpretation=_tag_value(item, "PhotometricInterpretation", "00280004"),
        raw_tags=item,
    )


def _multipart_dicom_payload(data: bytes) -> tuple[bytes, str]:
    boundary = "dicom-sdk-boundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Type: application/dicom\r\n\r\n'
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    return body, f'multipart/related; type="application/dicom"; boundary={boundary}'


def _parse_orthanc_study(data: dict[str, Any]) -> StudyMetadata:
    """Parse Orthanc study response into StudyMetadata."""
    main_tags = data.get("MainDicomTags", {})
    patient_tags = data.get("PatientMainDicomTags", {})
    return StudyMetadata(
        study_instance_uid=main_tags.get("StudyInstanceUID", data.get("ID", "")),
        patient_id=patient_tags.get("PatientID"),
        patient_name=patient_tags.get("PatientName"),
        study_date=main_tags.get("StudyDate"),
        study_description=main_tags.get("StudyDescription"),
        accession_number=main_tags.get("AccessionNumber"),
        modalities_in_study=[main_tags.get("Modality")]
        if main_tags.get("Modality")
        else None,
        institution_name=main_tags.get("InstitutionName"),
        referring_physician=main_tags.get("ReferringPhysicianName"),
        number_of_series=len(data.get("Series", [])),
        raw_tags=main_tags,
    )


def _parse_orthanc_series(data: dict[str, Any]) -> SeriesMetadata:
    """Parse Orthanc series response into SeriesMetadata."""
    tags = data.get("MainDicomTags", {})
    return SeriesMetadata(
        study_instance_uid=tags.get("StudyInstanceUID"),
        series_instance_uid=tags.get("SeriesInstanceUID", data.get("ID", "")),
        series_number=_safe_int(tags.get("SeriesNumber")),
        modality=tags.get("Modality"),
        series_description=tags.get("SeriesDescription"),
        body_part_examined=tags.get("BodyPartExamined"),
        number_of_instances=len(data.get("Instances", [])),
        raw_tags=tags,
    )


def _parse_orthanc_instance(data: dict[str, Any]) -> InstanceMetadata:
    """Parse Orthanc instance response into InstanceMetadata."""
    tags = data.get("MainDicomTags", {})
    return InstanceMetadata(
        study_instance_uid=tags.get("StudyInstanceUID"),
        series_instance_uid=tags.get("SeriesInstanceUID"),
        sop_instance_uid=tags.get("SOPInstanceUID", data.get("ID", "")),
        sop_class_uid=tags.get("SOPClassUID"),
        instance_number=_safe_int(tags.get("InstanceNumber")),
        rows=_safe_int(tags.get("Rows")),
        columns=_safe_int(tags.get("Columns")),
        bits_allocated=_safe_int(tags.get("BitsAllocated")),
        photometric_interpretation=tags.get("PhotometricInterpretation"),
        raw_tags=tags,
    )


class DicomClient:
    """Synchronous DICOMweb client for Orthanc-compatible servers.

    Supports STOW-RS (store), QIDO-RS (query), WADO-RS (retrieve),
    and native Orthanc API operations.

    Args:
        base_url: Base URL of the DICOM server (e.g. http://localhost:8042).
        username: Username for basic authentication (optional).
        password: Password for basic authentication (optional).
        timeout: Request timeout in seconds (default 30).
        verify_ssl: Whether to verify SSL certificates (default True).
    """

    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 30.0,
        verify_ssl: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        auth = httpx.BasicAuth(username, password) if username and password else None
        self._client = httpx.Client(
            base_url=self.base_url,
            auth=auth,
            timeout=timeout,
            verify=verify_ssl,
            headers={"Accept": "application/json"},
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> DicomClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Make an HTTP request to the DICOM server."""
        target = path if path.startswith(("http://", "https://")) else f"{self.base_url}{path}"
        try:
            response = self._client.request(method, path, **kwargs)
            _raise_for_status(response)
            return response
        except httpx.ConnectError as e:
            raise DicomConnectionError(f"Failed to connect to {target}: {e}") from e
        except httpx.TimeoutException as e:
            raise DicomConnectionError(f"Request timed out: {e}") from e

    # ─── STOW-RS: Store ─────────────────────────────────────────────

    def store(self, file_path: Union[str, Path]) -> StoreResult:
        """Store a DICOM file on the server (STOW-RS).

        Args:
            file_path: Path to the DICOM file to upload.

        Returns:
            StoreResult with upload details.

        Raises:
            DicomValidationError: If file does not exist or is not readable.
        """
        path = Path(file_path)
        if not path.is_file():
            raise DicomValidationError(f"File not found: {file_path}")
        data = path.read_bytes()
        return self.upload_dicom(data)

    def upload_dicom(self, data: bytes) -> StoreResult:
        """Upload raw DICOM data to the server.

        Args:
            data: Raw DICOM file bytes.

        Returns:
            StoreResult with upload details.
        """
        payload, content_type = _multipart_dicom_payload(data)
        response = self._request(
            "POST",
            f"{_DICOMWEB_PREFIX}/studies",
            content=payload,
            headers={"Content-Type": content_type},
        )
        result_data = response.json()
        return StoreResult(
            success=True,
            study_instance_uid=result_data.get("StudyInstanceUID") or result_data.get("ParentStudy"),
            sop_instance_uid=result_data.get("SOPInstanceUID") or result_data.get("ID"),
            status_code=response.status_code,
            message="Instance stored successfully",
        )

    # ─── QIDO-RS: Query ─────────────────────────────────────────────

    def query(
        self,
        study_uid: str | None = None,
        patient_id: str | None = None,
        patient_name: str | None = None,
        study_date: str | None = None,
        modality: str | None = None,
        accession_number: str | None = None,
        limit: int = 100,
        level: str = "study",
    ) -> list[QueryResult]:
        """Query studies/series/instances (QIDO-RS).

        Args:
            study_uid: Filter by Study Instance UID.
            patient_id: Filter by Patient ID.
            patient_name: Filter by Patient Name.
            study_date: Filter by Study Date (YYYYMMDD).
            modality: Filter by Modality.
            accession_number: Filter by Accession Number.
            limit: Maximum results to return.
            level: Query level ('study', 'series', 'instance').

        Returns:
            List of QueryResult objects.
        """
        params: dict[str, Any] = {"limit": limit}
        if study_uid:
            params["StudyInstanceUID"] = study_uid
        if patient_id:
            params["PatientID"] = patient_id
        if patient_name:
            params["PatientName"] = patient_name
        if study_date:
            params["StudyDate"] = study_date
        if modality:
            params["ModalitiesInStudy"] = modality
        if accession_number:
            params["AccessionNumber"] = accession_number

        if level == "study":
            path = f"{_DICOMWEB_PREFIX}/studies"
        elif level == "series":
            if not study_uid:
                raise DicomValidationError("study_uid is required for series-level DICOMweb queries")
            path = f"{_DICOMWEB_PREFIX}/studies/{study_uid}/series"
        elif level == "instance":
            raise DicomValidationError("Use query_instances() for instance-level DICOMweb queries")
        else:
            raise DicomValidationError(f"Unsupported query level: {level}")

        response = self._request("GET", path, params=params)
        data = response.json()

        if isinstance(data, list):
            return [_qido_to_query_result(item) for item in data]
        return []

    # ─── WADO-RS: Retrieve ──────────────────────────────────────────

    def retrieve(
        self,
        study_uid: str,
        series_uid: str | None = None,
        instance_uid: str | None = None,
        output_dir: str | None = None,
    ) -> list[bytes]:
        """Retrieve DICOM files (WADO-RS).

        Args:
            study_uid: Study Instance UID.
            series_uid: Optional Series Instance UID.
            instance_uid: Optional SOP Instance UID.
            output_dir: If provided, save files to this directory.

        Returns:
            List of DICOM file contents as bytes.
        """
        headers = {"Accept": 'multipart/related; type="application/dicom"'}
        parts = [f"{_DICOMWEB_PREFIX}/studies", study_uid]
        if series_uid:
            parts.extend(["/series", series_uid])
        if instance_uid:
            parts.extend(["/instances", instance_uid])
        path = "".join(parts)

        response = self._request("GET", path, headers=headers)

        # Response may be multipart or single DICOM
        content_type = response.headers.get("content-type", "")
        if "multipart" in content_type:
            files = self._parse_multipart(response)
        else:
            files = [response.content]

        if output_dir:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            for i, file_data in enumerate(files):
                out_path = out / f"dicom_{i:04d}.dcm"
                out_path.write_bytes(file_data)

        return files

    def _parse_multipart(self, response: httpx.Response) -> list[bytes]:
        """Parse a multipart DICOM response."""
        content_type = response.headers.get("content-type", "")
        boundary = ""
        for part in content_type.split(";"):
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part.split("=", 1)[1].strip('"')
                break
        if not boundary:
            return [response.content]

        parts = response.content.split(f"--{boundary}".encode())
        files = []
        for part in parts:
            if b"\r\n\r\n" in part:
                _, body = part.split(b"\r\n\r\n", 1)
                body = body.rstrip(b"\r\n-")
                if body:
                    files.append(body)
        return files

    # ─── Delete ─────────────────────────────────────────────────────

    def delete(
        self,
        study_uid: str,
        series_uid: str | None = None,
        instance_uid: str | None = None,
    ) -> bool:
        """Delete study, series, or instance.

        Args:
            study_uid: Study Instance UID (Orthanc ID or DICOM UID).
            series_uid: Optional Series Instance UID.
            instance_uid: Optional SOP Instance UID.

        Returns:
            True if deletion was successful.
        """
        # Find the Orthanc resource ID
        orthanc_id = self._resolve_orthanc_id(study_uid, series_uid, instance_uid)
        if not orthanc_id:
            raise DicomNotFoundError(f"Resource not found: study={study_uid}")
        self._request("DELETE", f"/{orthanc_id}")
        return True

    def _resolve_orthanc_id(
        self,
        study_uid: str,
        series_uid: str | None = None,
        instance_uid: str | None = None,
    ) -> str | None:
        """Resolve DICOM UID to Orthanc resource ID."""
        try:
            if instance_uid:
                # Try direct lookup by SOP Instance UID
                resp = self._request(
                    "POST",
                    "/tools/find",
                    json={
                        "Level": "Instance",
                        "Query": {"SOPInstanceUID": instance_uid},
                        "Expand": False,
                    },
                )
                data = resp.json()
                return data[0] if data else None
            if series_uid:
                resp = self._request(
                    "POST",
                    "/tools/find",
                    json={
                        "Level": "Series",
                        "Query": {
                            "StudyInstanceUID": study_uid,
                            "SeriesInstanceUID": series_uid,
                        },
                        "Expand": False,
                    },
                )
                data = resp.json()
                return data[0] if data else None
            # Study level
            resp = self._request(
                "POST",
                "/tools/find",
                json={
                    "Level": "Study",
                    "Query": {"StudyInstanceUID": study_uid},
                    "Expand": False,
                },
            )
            data = resp.json()
            return data[0] if data else None
        except DicomError:
            return None

    # ─── Metadata ───────────────────────────────────────────────────

    def get_study(self, study_uid: str) -> StudyMetadata:
        """Get detailed study metadata.

        Args:
            study_uid: Study Instance UID.

        Returns:
            StudyMetadata with full study information.
        """
        results = self.query(study_uid=study_uid)
        if not results:
            raise DicomNotFoundError(f"Study not found: {study_uid}")
        response = self._request(
            "GET",
            f"{_DICOMWEB_PREFIX}/studies",
            params={"StudyInstanceUID": study_uid, "limit": 1},
        )
        return _qido_to_study(response.json()[0])

    def get_series(self, study_uid: str, series_uid: str) -> SeriesMetadata:
        """Get detailed series metadata.

        Args:
            study_uid: Study Instance UID.
            series_uid: Series Instance UID.

        Returns:
            SeriesMetadata with full series information.
        """
        response = self._request("GET", f"{_DICOMWEB_PREFIX}/studies/{study_uid}/series")
        items = response.json()
        for item in items:
            parsed = _qido_to_series(item, study_uid=study_uid)
            if parsed.series_instance_uid == series_uid:
                return parsed
        raise DicomNotFoundError(f"Series not found: {series_uid}")

    def get_instance(
        self,
        study_uid: str,
        series_uid: str,
        sop_uid: str,
    ) -> InstanceMetadata:
        """Get detailed instance metadata.

        Args:
            study_uid: Study Instance UID.
            series_uid: Series Instance UID.
            sop_uid: SOP Instance UID.

        Returns:
            InstanceMetadata with full instance information.
        """
        response = self._request(
            "GET",
            f"{_DICOMWEB_PREFIX}/studies/{study_uid}/series/{series_uid}/instances/{sop_uid}/metadata",
        )
        items = response.json()
        if isinstance(items, list) and items:
            return _metadata_to_instance(items[0])
        raise DicomNotFoundError(f"Instance not found: {sop_uid}")

    # ─── Render ─────────────────────────────────────────────────────

    def render(
        self,
        study_uid: str,
        series_uid: str,
        instance_uid: str,
        output_format: str = "png",
        output_path: str | None = None,
    ) -> bytes:
        """Render a DICOM instance as an image.

        Args:
            study_uid: Study Instance UID.
            series_uid: Series Instance UID.
            instance_uid: SOP Instance UID.
            output_format: Image format ('png' or 'jpeg').
            output_path: If provided, save image to this path.

        Returns:
            Image bytes.
        """
        accept = f"image/{output_format}"
        response = self._request(
            "GET",
            f"{_DICOMWEB_PREFIX}/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/render",
            headers={"Accept": accept},
        )
        content = response.content

        if output_path:
            Path(output_path).write_bytes(content)

        return content

    # ─── Server Info ────────────────────────────────────────────────

    def list_modalities(self) -> list[ModalityInfo]:
        """List configured DICOM modalities.

        Returns:
            List of ModalityInfo objects.
        """
        response = self._request("GET", "/modalities")
        modalities = []
        for name, details in response.json().items():
            if isinstance(details, dict):
                modalities.append(
                    ModalityInfo(
                        name=name,
                        aet=details.get("AET"),
                        host=details.get("Host"),
                        port=details.get("Port"),
                    )
                )
            else:
                modalities.append(ModalityInfo(name=name))
        return modalities

    def get_statistics(self) -> ServerStatistics:
        """Get server statistics.

        Returns:
            ServerStatistics with counts and sizes.
        """
        response = self._request("GET", "/statistics")
        data = response.json()
        return ServerStatistics(
            count_patients=data.get("CountPatients", 0),
            count_studies=data.get("CountStudies", 0),
            count_series=data.get("CountSeries", 0),
            count_instances=data.get("CountInstances", 0),
            total_disk_size=_safe_int(data.get("TotalDiskSize")),
            total_uncompressed_size=_safe_int(data.get("TotalUncompressedSize")),
        )

    def list_studies(self) -> list[StudyMetadata]:
        """List all studies on the server.

        Returns:
            List of StudyMetadata objects.
        """
        response = self._request("GET", f"{_DICOMWEB_PREFIX}/studies")
        return [_qido_to_study(item) for item in response.json()]

    # ─── Batch Store ─────────────────────────────────────────────────

    def store_batch(self, file_paths: list[Union[str, Path]]) -> list[StoreResult]:
        """Store multiple DICOM files on the server.

        Args:
            file_paths: List of paths to DICOM files.

        Returns:
            List of StoreResult objects, one per file.
        """
        results = []
        for fp in file_paths:
            try:
                result = self.store(fp)
                results.append(result)
            except DicomError as e:
                results.append(
                    StoreResult(
                        success=False,
                        message=str(e),
                    )
                )
        return results

    def store_directory(
        self, directory: Union[str, Path], pattern: str = "**/*.dcm"
    ) -> list[StoreResult]:
        """Store all DICOM files in a directory.

        Args:
            directory: Path to directory containing DICOM files.
            pattern: Glob pattern for matching files.

        Returns:
            List of StoreResult objects.
        """
        dir_path = Path(directory)
        if not dir_path.is_dir():
            raise DicomValidationError(f"Directory not found: {directory}")
        files = list(dir_path.glob(pattern))
        return self.store_batch(files)

    # ─── Patient Query ────────────────────────────────────────────────

    def get_patient(self, patient_id: str) -> PatientMetadata | None:
        """Get patient metadata by Patient ID.

        Args:
            patient_id: The Patient ID to look up.

        Returns:
            PatientMetadata if found, None otherwise.
        """
        response = self._request(
            "GET",
            f"{_DICOMWEB_PREFIX}/studies",
            params={"PatientID": patient_id, "limit": 1},
        )
        items = response.json()
        if not items:
            return None
        item = items[0]
        return PatientMetadata(
            patient_id=_tag_value(item, "PatientID", "00100020"),
            patient_name=_tag_value(item, "PatientName", "00100010"),
            patient_birth_date=_tag_value(item, "PatientBirthDate", "00100030"),
            patient_sex=_tag_value(item, "PatientSex", "00100040"),
            patient_age=_tag_value(item, "PatientAge", "00101010"),
            raw_tags=item,
        )

    def list_patients(self, limit: int = 100) -> list[PatientMetadata]:
        """List all patients on the server.

        Args:
            limit: Maximum number of patients to return.

        Returns:
            List of PatientMetadata objects.
        """
        response = self._request("GET", f"{_DICOMWEB_PREFIX}/studies", params={"limit": limit})
        patients: list[PatientMetadata] = []
        seen: set[str] = set()
        for item in response.json():
            patient_id = _tag_value(item, "PatientID", "00100020")
            if not patient_id or patient_id in seen:
                continue
            seen.add(patient_id)
            patients.append(
                PatientMetadata(
                    patient_id=patient_id,
                    patient_name=_tag_value(item, "PatientName", "00100010"),
                    patient_birth_date=_tag_value(item, "PatientBirthDate", "00100030"),
                    patient_sex=_tag_value(item, "PatientSex", "00100040"),
                    patient_age=_tag_value(item, "PatientAge", "00101010"),
                    raw_tags=item,
                )
            )
        return patients

    # ─── Series Query ─────────────────────────────────────────────────

    def query_series(
        self,
        study_uid: str | None = None,
        series_uid: str | None = None,
        modality: str | None = None,
        series_description: str | None = None,
        body_part: str | None = None,
        limit: int = 100,
    ) -> list[SeriesMetadata]:
        """Query series (QIDO-RS at series level).

        Args:
            study_uid: Filter by Study Instance UID.
            series_uid: Filter by Series Instance UID.
            modality: Filter by Modality.
            series_description: Filter by Series Description.
            body_part: Filter by Body Part Examined.
            limit: Maximum results to return.

        Returns:
            List of SeriesMetadata objects.
        """
        if not study_uid:
            raise DicomValidationError("study_uid is required for series DICOMweb queries")
        params: dict[str, Any] = {"limit": limit}
        if series_uid:
            params["SeriesInstanceUID"] = series_uid
        if modality:
            params["Modality"] = modality
        if series_description:
            params["SeriesDescription"] = series_description
        if body_part:
            params["BodyPartExamined"] = body_part
        response = self._request("GET", f"{_DICOMWEB_PREFIX}/studies/{study_uid}/series", params=params)
        data = response.json()
        return [_qido_to_series(item, study_uid=study_uid) for item in data]

    def query_instances(
        self,
        study_uid: str | None = None,
        series_uid: str | None = None,
        modality: str | None = None,
        limit: int = 100,
    ) -> list[InstanceMetadata]:
        """Query instances (QIDO-RS at instance level).

        Args:
            study_uid: Filter by Study Instance UID.
            series_uid: Filter by Series Instance UID.
            modality: Filter by Modality.
            limit: Maximum results to return.

        Returns:
            List of InstanceMetadata objects.
        """
        if not study_uid or not series_uid:
            raise DicomValidationError("study_uid and series_uid are required for instance DICOMweb queries")
        params: dict[str, Any] = {"limit": limit}
        if modality:
            params["Modality"] = modality
        response = self._request(
            "GET",
            f"{_DICOMWEB_PREFIX}/studies/{study_uid}/series/{series_uid}/instances",
            params=params,
        )
        data = response.json()
        return [_metadata_to_instance(item) for item in data]

    # ─── Anonymization ───────────────────────────────────────────────

    def anonymize(
        self,
        study_uid: str,
        *,
        patient_name: str | None = None,
        patient_id: str | None = None,
        study_date: str | None = None,
    ) -> dict[str, Any]:
        """Anonymize a study.

        Args:
            study_uid: Study Instance UID.
            patient_name: New patient name.
            patient_id: New patient ID.
            study_date: New study date.

        Returns:
            Anonymization result with new IDs.
        """
        orthanc_id = self._resolve_orthanc_id(study_uid)
        if not orthanc_id:
            raise DicomNotFoundError(f"Study not found: {study_uid}")

        modifications: dict[str, Any] = {}
        if patient_name:
            modifications["PatientName"] = patient_name
        if patient_id:
            modifications["PatientID"] = patient_id
        if study_date:
            modifications["StudyDate"] = study_date

        payload = {"Permanently": False}
        if modifications:
            payload["Replace"] = modifications

        response = self._request(
            "POST", f"/studies/{orthanc_id}/anonymize", json=payload
        )
        return response.json()

    # ─── Peers ───────────────────────────────────────────────────────

    def list_peers(self) -> list[dict[str, Any]]:
        """List configured peer DICOM nodes.

        Returns:
            List of peer information dictionaries.
        """
        response = self._request("GET", "/peers")
        return response.json()

    def ping_peer(self, peer_name: str) -> bool:
        """Ping a peer DICOM node (C-ECHO).

        Args:
            peer_name: Name of the peer modality.

        Returns:
            True if ping succeeded.
        """
        response = self._request("GET", f"/modalities/{peer_name}/ping")
        return response.is_success

    # ─── Archive ─────────────────────────────────────────────────────

    def archive_study(self, study_uid: str) -> bytes:
        """Archive a study to a ZIP file.

        Args:
            study_uid: Study Instance UID.

        Returns:
            ZIP archive bytes.
        """
        orthanc_id = self._resolve_orthanc_id(study_uid)
        if not orthanc_id:
            raise DicomNotFoundError(f"Study not found: {study_uid}")
        response = self._request(
            "GET",
            f"/studies/{orthanc_id}/archive",
            headers={"Accept": "application/zip"},
        )
        return response.content

    def archive_series(self, study_uid: str, series_uid: str) -> bytes:
        """Archive a series to a ZIP file.

        Args:
            study_uid: Study Instance UID.
            series_uid: Series Instance UID.

        Returns:
            ZIP archive bytes.
        """
        orthanc_id = self._resolve_orthanc_id(study_uid, series_uid)
        if not orthanc_id:
            raise DicomNotFoundError(f"Series not found: {series_uid}")
        response = self._request(
            "GET",
            f"/series/{orthanc_id}/archive",
            headers={"Accept": "application/zip"},
        )
        return response.content

    # ─── System ───────────────────────────────────────────────────────

    def get_system(self) -> dict[str, Any]:
        """Get Orthanc system information.

        Returns:
            System information dictionary.
        """
        response = self._request("GET", "/system")
        return response.json()

    def get_changes(self, limit: int = 100, since: int = 0) -> dict[str, Any]:
        """Get change log (recent events).

        Args:
            limit: Maximum number of changes to return.
            since: Start from this sequence number.

        Returns:
            Change log dictionary with 'content' and 'last' keys.
        """
        response = self._request("GET", f"/changes?limit={limit}&since={since}")
        return response.json()

    # ─── Health Monitoring ───────────────────────────────────────────────

    def health_check(self) -> dict[str, Any]:
        """Perform a health check on the Orthanc server.

        Returns:
            Health status dictionary with:
            - status: 'healthy', 'degraded', or 'unhealthy'
            - database: database connectivity status
            - storage: storage availability
            - api: API responsiveness
            - uptime: server uptime in seconds
        """
        health = {
            "status": "healthy",
            "checks": {},
            "timestamp": None,
        }

        try:
            import time

            start = time.time()
            system = self.get_system()
            elapsed = time.time() - start

            health["checks"]["api"] = {
                "status": "healthy",
                "response_time_ms": round(elapsed * 1000, 2),
            }

            health["timestamp"] = system.get("DatabaseVersion", None)

            if elapsed > 5.0:
                health["status"] = "degraded"
                health["checks"]["api"]["status"] = "degraded"
                health["checks"]["api"]["message"] = "Slow response time"

        except DicomConnectionError as e:
            health["status"] = "unhealthy"
            health["checks"]["api"] = {"status": "unhealthy", "error": str(e)}
        except httpx.HTTPError as e:
            health["status"] = "unhealthy"
            health["checks"]["api"] = {"status": "unhealthy", "error": str(e)}
            logger.error("Health check API error", exc_info=True)

        try:
            stats = self.get_statistics()
            health["checks"]["database"] = {
                "status": "healthy",
                "patients": stats.total_patients,
                "studies": stats.total_studies,
                "series": stats.total_series,
                "instances": stats.total_instances,
                "storage_size_mb": round(stats.total_disk_size / (1024 * 1024), 2),
            }
        except (httpx.HTTPError, KeyError) as e:
            health["status"] = "unhealthy"
            health["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
            logger.error("Health check database error", exc_info=True)

        return health

    def get_database_info(self) -> dict[str, Any]:
        """Get database information and statistics.

        Returns:
            Database information dictionary.
        """
        response = self._request("GET", "/database")
        return response.json()

    def get_jobs(self, expand: bool = False) -> list[dict[str, Any]]:
        """List all jobs.

        Args:
            expand: Include full job details.

        Returns:
            List of job information dictionaries.
        """
        path = "/jobs"
        if expand:
            path += "?expand"
        response = self._request("GET", path)
        return response.json()

    def get_job(self, job_id: str) -> dict[str, Any]:
        """Get job details by ID.

        Args:
            job_id: The job ID.

        Returns:
            Job information dictionary.
        """
        response = self._request("GET", f"/jobs/{job_id}")
        return response.json()

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        """Cancel a running job.

        Args:
            job_id: The job ID.

        Returns:
            Cancellation result.
        """
        response = self._request("POST", f"/jobs/{job_id}/cancel")
        return response.json()

    def resubmit_job(self, job_id: str) -> dict[str, Any]:
        """Resubmit a failed job.

        Args:
            job_id: The job ID.

        Returns:
            Resubmission result.
        """
        response = self._request("POST", f"/jobs/{job_id}/resubmit")
        return response.json()

    def pause_job(self, job_id: str) -> dict[str, Any]:
        """Pause a running job.

        Args:
            job_id: The job ID.

        Returns:
            Pause result.
        """
        response = self._request("POST", f"/jobs/{job_id}/pause")
        return response.json()

    def resume_job(self, job_id: str) -> dict[str, Any]:
        """Resume a paused job.

        Args:
            job_id: The job ID.

        Returns:
            Resume result.
        """
        response = self._request("POST", f"/jobs/{job_id}/resume")
        return response.json()

    def get_metrics(self) -> dict[str, Any]:
        """Get server metrics for monitoring.

        Returns:
            Metrics dictionary with counts, sizes, and performance data.
        """
        stats = self.get_statistics()
        system = self.get_system()

        return {
            "counts": {
                "patients": stats.total_patients,
                "studies": stats.total_studies,
                "series": stats.total_series,
                "instances": stats.total_instances,
            },
            "storage": {
                "total_bytes": stats.total_disk_size,
                "total_mb": round(stats.total_disk_size / (1024 * 1024), 2),
                "total_gb": round(stats.total_disk_size / (1024 * 1024 * 1024), 2),
            },
            "system": {
                "version": system.get("Version", "unknown"),
                "database_version": system.get("DatabaseVersion", 0),
                "api_version": system.get("ApiVersion", 0),
            },
        }

    def get_storage_statistics(self) -> dict[str, Any]:
        """Get detailed storage statistics.

        Returns:
            Storage statistics with per-modality breakdown.
        """
        stats = self.get_statistics()

        result = {
            "total_instances": stats.total_instances,
            "total_size_bytes": stats.total_disk_size,
            "total_size_mb": round(stats.total_disk_size / (1024 * 1024), 2),
            "average_instance_size_kb": 0,
        }

        if stats.total_instances > 0:
            result["average_instance_size_kb"] = round(
                stats.total_disk_size / stats.total_instances / 1024, 2
            )

        return result
