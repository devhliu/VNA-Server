"""Synchronous BIDS Server client."""

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import httpx

from bids_sdk.exceptions import (
    BidsAuthenticationError,
    BidsConnectionError,
    BidsHTTPError,
    BidsNotFoundError,
    BidsServerError,
    BidsTimeoutError,
    BidsValidationError,
)
from bids_sdk.models import (
    Annotation,
    Modality,
    QueryResult,
    Resource,
    Session,
    Subject,
    Task,
    Webhook,
)

logger = logging.getLogger(__name__)


def _raise_for_status(response: httpx.Response) -> None:
    """Raise appropriate exception based on HTTP status code."""
    if response.is_success:
        return

    status_code = response.status_code
    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError):
        body = response.text

    message = f"HTTP {status_code}: {response.reason_phrase}"
    if isinstance(body, dict) and "message" in body:
        message = body["message"]
    elif isinstance(body, dict) and "error" in body:
        message = body["error"]

    headers = dict(response.headers)

    if status_code == 401:
        raise BidsAuthenticationError(message, response_body=body, headers=headers)
    elif status_code == 404:
        raise BidsNotFoundError(message, response_body=body, headers=headers)
    elif status_code == 400:
        raise BidsValidationError(message, details=body)
    elif status_code >= 500:
        raise BidsServerError(
            message, status_code=status_code, response_body=body, headers=headers
        )
    else:
        raise BidsHTTPError(
            message, status_code=status_code, response_body=body, headers=headers
        )


def _normalize_label_map(
    labels: Optional[Union[List[str], Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    """Normalize labels to the dict format expected by the current server."""
    if labels is None:
        return None
    if isinstance(labels, dict):
        return labels

    normalized: Dict[str, Any] = {}
    for item in labels:
        if ":" in item:
            key, value = item.split(":", 1)
            normalized[key] = value
        else:
            normalized[item] = True
    return normalized


class BidsClient:
    """Synchronous client for the BIDS Server (BIDSweb) API.

    Args:
        base_url: Base URL of the BIDS server (e.g., "http://localhost:8080").
        timeout: Request timeout in seconds.
        api_key: Optional API key for authentication.
        headers: Additional headers to include in all requests.
        verify_ssl: Whether to verify SSL certificates.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        verify_ssl: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        _headers = dict(headers or {})
        if api_key:
            _headers["Authorization"] = f"Bearer {api_key}"

        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers=_headers,
            verify=verify_ssl,
            follow_redirects=True,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> "BidsClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Any] = None,
        data: Optional[Any] = None,
        files: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Make an HTTP request and handle errors."""
        try:
            response = self._client.request(
                method,
                path,
                params=params,
                json=json,
                data=data,
                files=files,
                headers=headers,
            )
            _raise_for_status(response)
            return response
        except httpx.TimeoutException as e:
            raise BidsTimeoutError(f"Request to {path} timed out: {e}") from e
        except httpx.ConnectError as e:
            raise BidsConnectionError(
                f"Failed to connect to {self.base_url}: {e}"
            ) from e

    # ------------------------------------------------------------------
    # Data Transfer
    # ------------------------------------------------------------------

    def upload(
        self,
        file_path: Union[str, Path],
        subject_id: str,
        session_id: str,
        modality: str,
        labels: Optional[Union[List[str], Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Resource:
        """Upload a single file to the BIDS server.

        Args:
            file_path: Path to the file to upload.
            subject_id: Subject identifier.
            session_id: Session identifier.
            modality: Modality (e.g., "anat", "func", "dwi").
            labels: Optional list of labels.
            metadata: Optional metadata dict.
            progress_callback: Optional callback(bytes_read, total_bytes).

        Returns:
            Resource object for the uploaded file.
        """
        path = Path(file_path)
        if not path.is_file():
            raise BidsValidationError(f"File not found: {file_path}")

        file_size = path.stat().st_size

        data: Dict[str, Any] = {
            "subject_id": subject_id,
            "session_id": session_id,
            "modality": modality,
        }
        normalized_labels = _normalize_label_map(labels)
        if normalized_labels:
            data["labels"] = json.dumps(normalized_labels)
        if metadata:
            data["metadata"] = json.dumps(metadata)

        if progress_callback:
            # Read file and report progress
            with open(path, "rb") as f:
                file_data = f.read()
                bytes_read = len(file_data)
                progress_callback(bytes_read, file_size)
            files = {"file": (path.name, file_data)}
        else:
            files = {"file": (path.name, open(path, "rb"))}

        try:
            response = self._request("POST", "/api/upload", data=data, files=files)
        finally:
            # Close file handle if we opened it
            if not progress_callback and "file" in files:
                files["file"][1].close()

        result = response.json()
        return (
            Resource(**result)
            if isinstance(result, dict)
            else Resource(resource_id=str(result))
        )

    def upload_chunked(
        self,
        file_path: Union[str, Path],
        subject_id: str,
        session_id: str,
        modality: str,
        chunk_size: int = 5 * 1024 * 1024,
        labels: Optional[Union[List[str], Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Resource:
        """Upload a large file using chunked transfer.

        Args:
            file_path: Path to the file to upload.
            subject_id: Subject identifier.
            session_id: Session identifier.
            modality: Modality.
            chunk_size: Size of each chunk in bytes (default 5MB).
            labels: Optional labels.
            metadata: Optional metadata.
            progress_callback: Optional callback(bytes_uploaded, total_bytes).

        Returns:
            Resource object for the uploaded file.
        """
        path = Path(file_path)
        if not path.is_file():
            raise BidsValidationError(f"File not found: {file_path}")

        file_size = path.stat().st_size
        total_chunks = (file_size + chunk_size - 1) // chunk_size
        upload_id = None

        # Initiate chunked upload
        init_response = self._request(
            "POST",
            "/api/upload/chunked/init",
            json={
                "file_name": path.name,
                "file_size": file_size,
                "chunk_size": chunk_size,
                "subject_id": subject_id,
                "session_id": session_id,
                "modality": modality,
                "labels": _normalize_label_map(labels),
                "metadata": metadata,
            },
        )
        init_data = init_response.json()
        upload_id = init_data.get("upload_id", init_data.get("id"))

        bytes_uploaded = 0
        with open(path, "rb") as f:
            for chunk_index in range(total_chunks):
                chunk_data = f.read(chunk_size)
                files = {"chunk": (f"chunk_{chunk_index}", chunk_data)}
                self._request(
                    "POST",
                    f"/api/upload/chunked/{upload_id}/chunk",
                    data={"chunk_index": str(chunk_index)},
                    files=files,
                )
                bytes_uploaded += len(chunk_data)
                if progress_callback:
                    progress_callback(bytes_uploaded, file_size)

        # Finalize
        response = self._request("POST", f"/api/upload/chunked/{upload_id}/complete")
        result = response.json()
        return (
            Resource(**result)
            if isinstance(result, dict)
            else Resource(resource_id=str(result))
        )

    def download(
        self,
        resource_id: str,
        output_path: Union[str, Path],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """Download a file from the BIDS server.

        Args:
            resource_id: Resource identifier.
            output_path: Local path to save the file.
            progress_callback: Optional callback(bytes_written, total_bytes).

        Returns:
            Path to the downloaded file.
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        try:
            with self._client.stream("GET", f"/api/download/{resource_id}") as response:
                _raise_for_status(response)
                total = int(response.headers.get("content-length", 0))
                written = 0
                with open(output, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                        written += len(chunk)
                        if progress_callback:
                            progress_callback(written, total)
        except httpx.TimeoutException as e:
            raise BidsTimeoutError(f"Download timed out: {e}") from e
        except httpx.ConnectError as e:
            raise BidsConnectionError(f"Connection failed: {e}") from e

        return output

    def download_stream(
        self,
        resource_id: str,
        output_path: Union[str, Path],
        range_start: Optional[int] = None,
        range_end: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """Download a file using HTTP range requests.

        Args:
            resource_id: Resource identifier.
            output_path: Local path to save the file.
            range_start: Start byte (inclusive).
            range_end: End byte (inclusive).
            progress_callback: Optional callback(bytes_written, total_bytes).

        Returns:
            Path to the downloaded file.
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        headers: Dict[str, str] = {}
        if range_start is not None or range_end is not None:
            start = range_start or 0
            end = range_end if range_end is not None else ""
            headers["Range"] = f"bytes={start}-{end}"

        try:
            with self._client.stream(
                "GET", f"/api/download/{resource_id}", headers=headers
            ) as response:
                _raise_for_status(response)
                total = int(response.headers.get("content-length", 0))
                written = 0
                with open(output, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                        written += len(chunk)
                        if progress_callback:
                            progress_callback(written, total)
        except httpx.TimeoutException as e:
            raise BidsTimeoutError(f"Download timed out: {e}") from e
        except httpx.ConnectError as e:
            raise BidsConnectionError(f"Connection failed: {e}") from e

        return output

    def batch_download(
        self,
        resource_ids: List[str],
        output_path: Union[str, Path],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """Download multiple files as a zip archive.

        Args:
            resource_ids: List of resource identifiers.
            output_path: Local path to save the zip file.
            progress_callback: Optional callback(bytes_written, total_bytes).

        Returns:
            Path to the downloaded zip file.
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        try:
            with self._client.stream(
                "POST", "/api/download/batch", json={"resource_ids": resource_ids}
            ) as response:
                _raise_for_status(response)
                total = int(response.headers.get("content-length", 0))
                written = 0
                with open(output, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                        written += len(chunk)
                        if progress_callback:
                            progress_callback(written, total)
        except httpx.TimeoutException as e:
            raise BidsTimeoutError(f"Batch download timed out: {e}") from e
        except httpx.ConnectError as e:
            raise BidsConnectionError(f"Connection failed: {e}") from e

        return output

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        subject_id: Optional[str] = None,
        session_id: Optional[str] = None,
        modality: Optional[str] = None,
        labels: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> QueryResult:
        """Query resources with flexible filters.

        Args:
            subject_id: Filter by subject ID.
            session_id: Filter by session ID.
            modality: Filter by modality.
            labels: Filter by labels.
            metadata: Filter by metadata.
            search: Full-text search query.
            limit: Max results to return.
            offset: Pagination offset.

        Returns:
            QueryResult with matching resources.
        """
        params: Dict[str, Any] = {}
        if subject_id:
            params["subject_id"] = subject_id
        if session_id:
            params["session_id"] = session_id
        if modality:
            params["modality"] = modality
        if labels:
            params["labels"] = ",".join(labels)
        if metadata:
            params.update(metadata)
        if search:
            params["search"] = search
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        response = self._request("GET", "/api/query", params=params)
        data = response.json()
        return (
            QueryResult(**data)
            if isinstance(data, dict)
            else QueryResult(resources=[], total=0)
        )

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    def get_labels(self, resource_id: str) -> List[Dict[str, Any]]:
        """Get labels for a resource.

        Args:
            resource_id: Resource identifier.

        Returns:
            List of label dicts.
        """
        response = self._request("GET", f"/api/resources/{resource_id}/labels")
        return response.json()

    def set_labels(
        self, resource_id: str, labels: Union[List[str], Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Replace all labels on a resource.

        Args:
            resource_id: Resource identifier.
            labels: New labels (replaces all existing).

        Returns:
            Updated list of labels.
        """
        response = self._request(
            "PUT",
            f"/api/resources/{resource_id}/labels",
            json={"labels": _normalize_label_map(labels)},
        )
        return response.json()

    def patch_labels(
        self,
        resource_id: str,
        add: Optional[Union[List[str], Dict[str, Any]]] = None,
        remove: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Add and/or remove labels on a resource.

        Args:
            resource_id: Resource identifier.
            add: Labels to add.
            remove: Label keys to remove.

        Returns:
            Updated list of labels.
        """
        body: Dict[str, Any] = {}
        if add:
            body["add"] = _normalize_label_map(add)
        if remove:
            body["remove"] = remove
        response = self._request(
            "PATCH", f"/api/resources/{resource_id}/labels", json=body
        )
        return response.json()

    def list_all_tags(self) -> List[Dict[str, Any]]:
        """List all tags with usage counts.

        Returns:
            List of tag dicts with counts.
        """
        response = self._request("GET", "/api/tags")
        return response.json()

    # ------------------------------------------------------------------
    # Annotations
    # ------------------------------------------------------------------

    def create_annotation(
        self,
        resource_id: str,
        ann_type: str,
        label: str,
        data: Optional[Dict[str, Any]] = None,
        confidence: Optional[float] = None,
    ) -> Annotation:
        """Create an annotation on a resource.

        Args:
            resource_id: Resource identifier.
            ann_type: Annotation type.
            label: Annotation label.
            data: Optional annotation data.
            confidence: Optional confidence score.

        Returns:
            Created Annotation.
        """
        body: Dict[str, Any] = {
            "resource_id": resource_id,
            "type": ann_type,
            "label": label,
        }
        if data is not None:
            body["data"] = data
        if confidence is not None:
            body["confidence"] = confidence
        response = self._request("POST", "/api/annotations", json=body)
        return Annotation(**response.json())

    def list_annotations(self, resource_id: str) -> List[Annotation]:
        """List annotations for a resource.

        Args:
            resource_id: Resource identifier.

        Returns:
            List of Annotation objects.
        """
        response = self._request("GET", f"/api/resources/{resource_id}/annotations")
        data = response.json()
        if isinstance(data, list):
            return [Annotation(**a) for a in data]
        return []

    # ------------------------------------------------------------------
    # Subjects / Sessions
    # ------------------------------------------------------------------

    def create_subject(
        self,
        subject_id: str,
        patient_ref: Optional[str] = None,
        hospital_ids: Optional[List[str]] = None,
    ) -> Subject:
        """Create a new subject.

        Args:
            subject_id: Subject identifier.
            patient_ref: Patient reference.
            hospital_ids: Hospital identifiers.

        Returns:
            Created Subject.
        """
        body: Dict[str, Any] = {"subject_id": subject_id}
        if patient_ref is not None:
            body["patient_ref"] = patient_ref
        if hospital_ids is not None:
            body["hospital_ids"] = hospital_ids
        response = self._request("POST", "/api/subjects", json=body)
        return Subject(**response.json())

    def get_subject(self, subject_id: str) -> Subject:
        """Get a subject by ID.

        Args:
            subject_id: Subject identifier.

        Returns:
            Subject object.
        """
        response = self._request("GET", f"/api/subjects/{subject_id}")
        return Subject(**response.json())

    def list_subjects(self) -> List[Subject]:
        """List all subjects.

        Returns:
            List of Subject objects.
        """
        response = self._request("GET", "/api/subjects")
        data = response.json()
        if isinstance(data, list):
            return [Subject(**s) for s in data]
        return []

    def create_session(
        self,
        session_id: str,
        subject_id: str,
        session_label: Optional[str] = None,
    ) -> Session:
        """Create a new session.

        Args:
            session_id: Session identifier.
            subject_id: Subject identifier.
            session_label: Optional human-readable label.

        Returns:
            Created Session.
        """
        body: Dict[str, Any] = {
            "session_id": session_id,
            "subject_id": subject_id,
        }
        if session_label is not None:
            body["session_label"] = session_label
        response = self._request("POST", "/api/sessions", json=body)
        return Session(**response.json())

    def list_sessions(self, subject_id: Optional[str] = None) -> List[Session]:
        """List sessions, optionally filtered by subject.

        Args:
            subject_id: Optional subject filter.

        Returns:
            List of Session objects.
        """
        params: Dict[str, Any] = {}
        if subject_id:
            params["subject_id"] = subject_id
        response = self._request("GET", "/api/sessions", params=params)
        data = response.json()
        if isinstance(data, list):
            return [Session(**s) for s in data]
        return []

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def submit_task(
        self,
        action: str,
        resource_ids: List[str],
        params: Optional[Dict[str, Any]] = None,
    ) -> Task:
        """Submit an async task.

        Args:
            action: Task action type.
            resource_ids: Resource identifiers.
            params: Optional task parameters.

        Returns:
            Task object.
        """
        body: Dict[str, Any] = {
            "action": action,
            "resource_ids": resource_ids,
        }
        if params:
            body["params"] = params
        response = self._request("POST", "/api/tasks", json=body)
        return Task(**response.json())

    def get_task(self, task_id: str) -> Task:
        """Get task status.

        Args:
            task_id: Task identifier.

        Returns:
            Task object.
        """
        response = self._request("GET", f"/api/tasks/{task_id}")
        return Task(**response.json())

    def cancel_task(self, task_id: str) -> Task:
        """Cancel a running task.

        Args:
            task_id: Task identifier.

        Returns:
            Updated Task object.
        """
        response = self._request("POST", f"/api/tasks/{task_id}/cancel")
        return Task(**response.json())

    # ------------------------------------------------------------------
    # Webhooks
    # ------------------------------------------------------------------

    def create_webhook(
        self,
        url: str,
        events: List[str],
        name: Optional[str] = None,
        secret: Optional[str] = None,
    ) -> Webhook:
        """Register a webhook.

        Args:
            url: Webhook URL.
            events: List of event types to subscribe to.
            name: Optional name.
            secret: Optional signing secret.

        Returns:
            Created Webhook.
        """
        body: Dict[str, Any] = {
            "url": url,
            "events": events,
        }
        if name:
            body["name"] = name
        if secret:
            body["secret"] = secret
        response = self._request("POST", "/api/webhooks", json=body)
        return Webhook(**response.json())

    def list_webhooks(self) -> List[Webhook]:
        """List all webhooks.

        Returns:
            List of Webhook objects.
        """
        response = self._request("GET", "/api/webhooks")
        data = response.json()
        if isinstance(data, list):
            return [Webhook(**w) for w in data]
        return []

    def delete_webhook(self, webhook_id: str) -> None:
        """Delete a webhook.

        Args:
            webhook_id: Webhook identifier.
        """
        self._request("DELETE", f"/api/webhooks/{webhook_id}")

    # ------------------------------------------------------------------
    # System
    # ------------------------------------------------------------------

    def verify(
        self,
        target: Optional[str] = None,
        check_hash: bool = True,
    ) -> Dict[str, Any]:
        """Verify data integrity.

        Args:
            target: Optional target to verify (subject, session, or resource ID).
            check_hash: Whether to verify file hashes.

        Returns:
            Verification result dict.
        """
        params: Dict[str, Any] = {"check_hash": str(check_hash).lower()}
        if target:
            params["target"] = target
        response = self._request("GET", "/api/verify", params=params)
        return response.json()

    def rebuild(
        self,
        target: Optional[str] = None,
        clear_existing: bool = False,
    ) -> Dict[str, Any]:
        """Rebuild the database.

        Args:
            target: Optional target to rebuild.
            clear_existing: Whether to clear existing data.

        Returns:
            Rebuild result dict.
        """
        body: Dict[str, Any] = {"clear_existing": clear_existing}
        if target:
            body["target"] = target
        response = self._request("POST", "/api/rebuild", json=body)
        return response.json()

    def list_modalities(self) -> List[Modality]:
        """List all registered modalities.

        Returns:
            List of Modality objects.
        """
        response = self._request("GET", "/api/modalities")
        data = response.json()
        if isinstance(data, list):
            return [Modality(**m) for m in data]
        return []

    def register_modality(
        self,
        modality_id: str,
        directory: str,
        extensions: Optional[List[str]] = None,
    ) -> Modality:
        """Register a new modality.

        Args:
            modality_id: Modality identifier.
            directory: Directory name for this modality.
            extensions: List of file extensions.

        Returns:
            Created Modality.
        """
        body: Dict[str, Any] = {
            "modality_id": modality_id,
            "directory": directory,
        }
        if extensions:
            body["extensions"] = extensions
        response = self._request("POST", "/api/modalities", json=body)
        return Modality(**response.json())

    # ─── Validation ───────────────────────────────────────────────────────

    def validate_file(
        self,
        filepath: str,
        strict: bool = False,
    ) -> Dict[str, Any]:
        """Validate a BIDS file.

        Args:
            filepath: File path to validate.
            strict: Enable strict validation mode.

        Returns:
            Validation result with issues list.
        """
        body = {"filepath": filepath, "strict": strict}
        response = self._request("POST", "/api/validation/file", json=body)
        return response.json()

    def get_validation_rules(self) -> Dict[str, Any]:
        """Get BIDS validation rules.

        Returns:
            Dictionary of validation rules.
        """
        response = self._request("GET", "/api/validation/rules")
        return response.json()

    def get_valid_entities(self) -> Dict[str, Any]:
        """Get list of valid BIDS entities.

        Returns:
            Dictionary with entities list.
        """
        response = self._request("GET", "/api/validation/entities")
        return response.json()

    def get_modality_info(self) -> Dict[str, Any]:
        """Get modality-specific validation information.

        Returns:
            Dictionary with modality requirements.
        """
        response = self._request("GET", "/api/validation/modalities")
        return response.json()

    # ─── Health & System ──────────────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the BIDS server.

        Returns:
            Health status dictionary.
        """
        response = self._request("GET", "/health")
        return response.json()

    def get_statistics(self) -> Dict[str, Any]:
        """Get server statistics.

        Returns:
            Statistics dictionary.
        """
        response = self._request("GET", "/api/statistics")
        return response.json()
