"""Asynchronous DICOMweb client for Orthanc-compatible servers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Union

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
from dicom_sdk.client import (
    _DICOMWEB_PREFIX,
    _metadata_to_instance,
    _multipart_dicom_payload,
    _qido_to_query_result,
    _qido_to_series,
    _qido_to_study,
    _raise_for_status,
    _safe_int,
    _tag_value,
)


class AsyncDicomClient:
    """Asynchronous DICOMweb client for Orthanc-compatible servers.

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
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=auth,
            timeout=timeout,
            verify=verify_ssl,
            headers={"Accept": "application/json"},
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> AsyncDicomClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Make an async HTTP request to the DICOM server."""
        target = path if path.startswith(("http://", "https://")) else f"{self.base_url}{path}"
        try:
            response = await self._client.request(method, path, **kwargs)
            _raise_for_status(response)
            return response
        except httpx.ConnectError as e:
            raise DicomConnectionError(f"Failed to connect to {target}: {e}") from e
        except httpx.TimeoutException as e:
            raise DicomConnectionError(f"Request timed out: {e}") from e

    # ─── STOW-RS: Store ─────────────────────────────────────────────

    async def store(self, file_path: Union[str, Path]) -> StoreResult:
        """Store a DICOM file on the server."""
        path = Path(file_path)
        if not path.is_file():
            raise DicomValidationError(f"File not found: {file_path}")
        data = path.read_bytes()
        return await self.upload_dicom(data)

    async def upload_dicom(self, data: bytes) -> StoreResult:
        """Upload raw DICOM data to the server."""
        payload, content_type = _multipart_dicom_payload(data)
        response = await self._request(
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

    async def query(
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
        """Query studies/series/instances."""
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
        if level != "study":
            raise DicomValidationError("Use query_series() or query_instances() for nested DICOMweb queries")

        response = await self._request("GET", f"{_DICOMWEB_PREFIX}/studies", params=params)
        data = response.json()

        if isinstance(data, list):
            return [_qido_to_query_result(item) for item in data]
        return []

    # ─── WADO-RS: Retrieve ──────────────────────────────────────────

    async def retrieve(
        self,
        study_uid: str,
        series_uid: str | None = None,
        instance_uid: str | None = None,
        output_dir: str | None = None,
    ) -> list[bytes]:
        """Retrieve DICOM files."""
        headers = {"Accept": 'multipart/related; type="application/dicom"'}
        parts = [f"{_DICOMWEB_PREFIX}/studies", study_uid]
        if series_uid:
            parts.extend(["/series", series_uid])
        if instance_uid:
            parts.extend(["/instances", instance_uid])
        path = "".join(parts)

        response = await self._request("GET", path, headers=headers)
        content_type = response.headers.get("content-type", "")
        if "multipart" in content_type:
            files = self._parse_multipart(response)
        else:
            files = [response.content]

        if output_dir:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            for i, file_data in enumerate(files):
                (out / f"dicom_{i:04d}.dcm").write_bytes(file_data)

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

    async def delete(
        self,
        study_uid: str,
        series_uid: str | None = None,
        instance_uid: str | None = None,
    ) -> bool:
        """Delete study, series, or instance."""
        orthanc_id = await self._resolve_orthanc_id(study_uid, series_uid, instance_uid)
        if not orthanc_id:
            raise DicomNotFoundError(f"Resource not found: study={study_uid}")
        await self._request("DELETE", f"/{orthanc_id}")
        return True

    async def _resolve_orthanc_id(
        self,
        study_uid: str,
        series_uid: str | None = None,
        instance_uid: str | None = None,
    ) -> str | None:
        """Resolve DICOM UID to Orthanc resource ID."""
        level = "Instance" if instance_uid else ("Series" if series_uid else "Study")
        query: dict[str, str] = {}
        if study_uid:
            query["StudyInstanceUID"] = study_uid
        if series_uid:
            query["SeriesInstanceUID"] = series_uid
        if instance_uid:
            query["SOPInstanceUID"] = instance_uid
        try:
            resp = await self._request(
                "POST",
                "/tools/find",
                json={"Level": level, "Query": query, "Expand": False},
            )
        except DicomError:
            return None
        if resp.json():
            return resp.json()[0]
        return None

    # ─── Metadata ───────────────────────────────────────────────────

    async def get_study(self, study_uid: str) -> StudyMetadata:
        """Get detailed study metadata."""
        response = await self._request(
            "GET",
            f"{_DICOMWEB_PREFIX}/studies",
            params={"StudyInstanceUID": study_uid, "limit": 1},
        )
        items = response.json()
        if not items:
            raise DicomNotFoundError(f"Study not found: {study_uid}")
        return _qido_to_study(items[0])

    async def get_series(self, study_uid: str, series_uid: str) -> SeriesMetadata:
        """Get detailed series metadata."""
        response = await self._request("GET", f"{_DICOMWEB_PREFIX}/studies/{study_uid}/series")
        for item in response.json():
            parsed = _qido_to_series(item, study_uid=study_uid)
            if parsed.series_instance_uid == series_uid:
                return parsed
        raise DicomNotFoundError(f"Series not found: {series_uid}")

    async def get_instance(
        self, study_uid: str, series_uid: str, sop_uid: str
    ) -> InstanceMetadata:
        """Get detailed instance metadata."""
        response = await self._request(
            "GET",
            f"{_DICOMWEB_PREFIX}/studies/{study_uid}/series/{series_uid}/instances/{sop_uid}/metadata",
        )
        items = response.json()
        if isinstance(items, list) and items:
            return _metadata_to_instance(items[0])
        raise DicomNotFoundError(f"Instance not found: {sop_uid}")

    # ─── Render ─────────────────────────────────────────────────────

    async def render(
        self,
        study_uid: str,
        series_uid: str,
        instance_uid: str,
        output_format: str = "png",
        output_path: str | None = None,
    ) -> bytes:
        """Render a DICOM instance as an image."""
        response = await self._request(
            "GET",
            f"{_DICOMWEB_PREFIX}/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/render",
            headers={"Accept": f"image/{output_format}"},
        )
        content = response.content
        if output_path:
            Path(output_path).write_bytes(content)
        return content

    # ─── Server Info ────────────────────────────────────────────────

    async def list_modalities(self) -> list[ModalityInfo]:
        """List configured DICOM modalities."""
        response = await self._request("GET", "/modalities")
        modalities = []
        for name, details in response.json().items():
            if isinstance(details, dict):
                modalities.append(ModalityInfo(
                    name=name,
                    aet=details.get("AET"),
                    host=details.get("Host"),
                    port=details.get("Port"),
                ))
            else:
                modalities.append(ModalityInfo(name=name))
        return modalities

    async def get_statistics(self) -> ServerStatistics:
        """Get server statistics."""
        response = await self._request("GET", "/statistics")
        data = response.json()
        return ServerStatistics(
            count_patients=data.get("CountPatients", 0),
            count_studies=data.get("CountStudies", 0),
            count_series=data.get("CountSeries", 0),
            count_instances=data.get("CountInstances", 0),
            total_disk_size=_safe_int(data.get("TotalDiskSize")),
            total_uncompressed_size=_safe_int(data.get("TotalUncompressedSize")),
        )

    async def list_studies(self) -> list[StudyMetadata]:
        """List all studies on the server."""
        response = await self._request("GET", f"{_DICOMWEB_PREFIX}/studies")
        return [_qido_to_study(item) for item in response.json()]

    # ─── Batch Store ─────────────────────────────────────────────────

    async def store_batch(self, file_paths: list[Union[str, Path]]) -> list[StoreResult]:
        """Store multiple DICOM files on the server."""
        results = []
        for fp in file_paths:
            try:
                result = await self.store(fp)
                results.append(result)
            except DicomError as e:
                results.append(StoreResult(
                    success=False,
                    message=str(e),
                ))
        return results

    async def store_directory(self, directory: Union[str, Path], pattern: str = "**/*.dcm") -> list[StoreResult]:
        """Store all DICOM files in a directory."""
        dir_path = Path(directory)
        if not dir_path.is_dir():
            raise DicomValidationError(f"Directory not found: {directory}")
        files = list(dir_path.glob(pattern))
        return await self.store_batch(files)

    # ─── Patient Query ────────────────────────────────────────────────

    async def get_patient(self, patient_id: str) -> PatientMetadata | None:
        """Get patient metadata by Patient ID."""
        response = await self._request(
            "GET",
            f"{_DICOMWEB_PREFIX}/studies",
            params={"PatientID": patient_id, "limit": 1},
        )
        items = response.json()
        if not items:
            return None
        tags = items[0]
        return PatientMetadata(
            patient_id=_tag_value(tags, "PatientID", "00100020"),
            patient_name=_tag_value(tags, "PatientName", "00100010"),
            patient_birth_date=_tag_value(tags, "PatientBirthDate", "00100030"),
            patient_sex=_tag_value(tags, "PatientSex", "00100040"),
            patient_age=_tag_value(tags, "PatientAge", "00101010"),
            raw_tags=tags,
        )

    async def list_patients(self, limit: int = 100) -> list[PatientMetadata]:
        """List all patients on the server."""
        response = await self._request("GET", f"{_DICOMWEB_PREFIX}/studies", params={"limit": limit})
        patients = []
        seen: set[str] = set()
        for item in response.json():
            patient_id = _tag_value(item, "PatientID", "00100020")
            if not patient_id or patient_id in seen:
                continue
            seen.add(patient_id)
            patient = PatientMetadata(
                patient_id=patient_id,
                patient_name=_tag_value(item, "PatientName", "00100010"),
                patient_birth_date=_tag_value(item, "PatientBirthDate", "00100030"),
                patient_sex=_tag_value(item, "PatientSex", "00100040"),
                patient_age=_tag_value(item, "PatientAge", "00101010"),
                raw_tags=item,
            )
            patients.append(patient)
        return patients

    # ─── Series Query ─────────────────────────────────────────────────

    async def query_series(
        self,
        study_uid: str | None = None,
        series_uid: str | None = None,
        modality: str | None = None,
        series_description: str | None = None,
        body_part: str | None = None,
        limit: int = 100,
    ) -> list[SeriesMetadata]:
        """Query series (QIDO-RS at series level)."""
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
        response = await self._request("GET", f"{_DICOMWEB_PREFIX}/studies/{study_uid}/series", params=params)
        return [_qido_to_series(item, study_uid=study_uid) for item in response.json()]

    async def query_instances(
        self,
        study_uid: str | None = None,
        series_uid: str | None = None,
        modality: str | None = None,
        limit: int = 100,
    ) -> list[InstanceMetadata]:
        """Query instances (QIDO-RS at instance level)."""
        if not study_uid or not series_uid:
            raise DicomValidationError("study_uid and series_uid are required for instance DICOMweb queries")
        params: dict[str, Any] = {"limit": limit}
        if modality:
            params["Modality"] = modality
        response = await self._request(
            "GET",
            f"{_DICOMWEB_PREFIX}/studies/{study_uid}/series/{series_uid}/instances",
            params=params,
        )
        return [_metadata_to_instance(item) for item in response.json()]

    # ─── Anonymization ───────────────────────────────────────────────

    async def anonymize(
        self,
        study_uid: str,
        *,
        patient_name: str | None = None,
        patient_id: str | None = None,
        study_date: str | None = None,
    ) -> dict[str, Any]:
        """Anonymize a study."""
        orthanc_id = await self._resolve_orthanc_id(study_uid)
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

        response = await self._request("POST", f"/studies/{orthanc_id}/anonymize", json=payload)
        return response.json()

    # ─── Peers ───────────────────────────────────────────────────────

    async def list_peers(self) -> list[dict[str, Any]]:
        """List configured peer DICOM nodes."""
        response = await self._request("GET", "/peers")
        return response.json()

    async def ping_peer(self, peer_name: str) -> bool:
        """Ping a peer DICOM node (C-ECHO)."""
        response = await self._request("GET", f"/modalities/{peer_name}/ping")
        return response.is_success

    # ─── Archive ─────────────────────────────────────────────────────

    async def archive_study(self, study_uid: str) -> bytes:
        """Archive a study to a ZIP file."""
        orthanc_id = await self._resolve_orthanc_id(study_uid)
        if not orthanc_id:
            raise DicomNotFoundError(f"Study not found: {study_uid}")
        response = await self._request(
            "GET",
            f"/studies/{orthanc_id}/archive",
            headers={"Accept": "application/zip"},
        )
        return response.content

    async def archive_series(self, study_uid: str, series_uid: str) -> bytes:
        """Archive a series to a ZIP file."""
        orthanc_id = await self._resolve_orthanc_id(study_uid, series_uid)
        if not orthanc_id:
            raise DicomNotFoundError(f"Series not found: {series_uid}")
        response = await self._request(
            "GET",
            f"/series/{orthanc_id}/archive",
            headers={"Accept": "application/zip"},
        )
        return response.content

    # ─── System ───────────────────────────────────────────────────────

    async def get_system(self) -> dict[str, Any]:
        """Get Orthanc system information."""
        response = await self._request("GET", "/system")
        return response.json()

    async def get_changes(self, limit: int = 100, since: int = 0) -> dict[str, Any]:
        """Get change log (recent events)."""
        response = await self._request("GET", f"/changes?limit={limit}&since={since}")
        return response.json()

    # ─── Health Monitoring ───────────────────────────────────────────────

    async def health_check(self) -> dict[str, Any]:
        """Perform a health check on the Orthanc server."""
        health = {
            "status": "healthy",
            "checks": {},
            "timestamp": None,
        }

        try:
            import time
            start = time.time()
            system = await self.get_system()
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
        except Exception as e:
            health["status"] = "unhealthy"
            health["checks"]["api"] = {"status": "unhealthy", "error": str(e)}

        try:
            stats = await self.get_statistics()
            health["checks"]["database"] = {
                "status": "healthy",
                "patients": stats.total_patients,
                "studies": stats.total_studies,
                "series": stats.total_series,
                "instances": stats.total_instances,
                "storage_size_mb": round(stats.total_disk_size / (1024 * 1024), 2),
            }
        except Exception as e:
            health["status"] = "unhealthy"
            health["checks"]["database"] = {"status": "unhealthy", "error": str(e)}

        return health

    async def get_database_info(self) -> dict[str, Any]:
        """Get database information and statistics."""
        response = await self._request("GET", "/database")
        return response.json()

    async def get_jobs(self, expand: bool = False) -> list[dict[str, Any]]:
        """List all jobs."""
        path = "/jobs"
        if expand:
            path += "?expand"
        response = await self._request("GET", path)
        return response.json()

    async def get_job(self, job_id: str) -> dict[str, Any]:
        """Get job details by ID."""
        response = await self._request("GET", f"/jobs/{job_id}")
        return response.json()

    async def cancel_job(self, job_id: str) -> dict[str, Any]:
        """Cancel a running job."""
        response = await self._request("POST", f"/jobs/{job_id}/cancel")
        return response.json()

    async def resubmit_job(self, job_id: str) -> dict[str, Any]:
        """Resubmit a failed job."""
        response = await self._request("POST", f"/jobs/{job_id}/resubmit")
        return response.json()

    async def pause_job(self, job_id: str) -> dict[str, Any]:
        """Pause a running job."""
        response = await self._request("POST", f"/jobs/{job_id}/pause")
        return response.json()

    async def resume_job(self, job_id: str) -> dict[str, Any]:
        """Resume a paused job."""
        response = await self._request("POST", f"/jobs/{job_id}/resume")
        return response.json()

    async def get_metrics(self) -> dict[str, Any]:
        """Get server metrics for monitoring."""
        stats = await self.get_statistics()
        system = await self.get_system()

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

    async def get_storage_statistics(self) -> dict[str, Any]:
        """Get detailed storage statistics."""
        stats = await self.get_statistics()

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
