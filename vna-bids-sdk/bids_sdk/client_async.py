"""Asynchronous BIDS Server client."""

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import httpx

from bids_sdk.client import _normalize_label_map, _raise_for_status
from bids_sdk.exceptions import (
    BidsConnectionError,
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


class AsyncBidsClient:
    """Asynchronous client for the BIDS Server (BIDSweb) API.

    Args:
        base_url: Base URL of the BIDS server.
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

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers=_headers,
            verify=verify_ssl,
            follow_redirects=True,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncBidsClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Any] = None,
        data: Optional[Any] = None,
        files: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Make an async HTTP request and handle errors."""
        try:
            response = await self._client.request(
                method, path, params=params, json=json, data=data, files=files, headers=headers
            )
            _raise_for_status(response)
            return response
        except httpx.TimeoutException as e:
            raise BidsTimeoutError(f"Request to {path} timed out: {e}") from e
        except httpx.ConnectError as e:
            raise BidsConnectionError(f"Failed to connect to {self.base_url}: {e}") from e

    # ------------------------------------------------------------------
    # Data Transfer
    # ------------------------------------------------------------------

    async def upload(
        self,
        file_path: Union[str, Path],
        subject_id: str,
        session_id: str,
        modality: str,
        labels: Optional[Union[List[str], Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Resource:
        """Upload a single file asynchronously."""
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

        with open(path, "rb") as f:
            file_content = f.read()

        if progress_callback:
            progress_callback(len(file_content), file_size)

        files = {"file": (path.name, file_content)}
        response = await self._request("POST", "/api/store", data=data, files=files)
        result = response.json()
        return Resource(**result) if isinstance(result, dict) else Resource(resource_id=str(result))

    async def upload_chunked(
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
        """Upload a large file using chunked transfer asynchronously."""
        path = Path(file_path)
        if not path.is_file():
            raise BidsValidationError(f"File not found: {file_path}")

        file_size = path.stat().st_size
        total_chunks = (file_size + chunk_size - 1) // chunk_size

        init_response = await self._request(
            "POST",
            "/api/store/init",
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
                await self._request(
                    "POST",
                    f"/api/store/{upload_id}",
                    data={"chunk_index": str(chunk_index)},
                    files=files,
                )
                bytes_uploaded += len(chunk_data)
                if progress_callback:
                    progress_callback(bytes_uploaded, file_size)

        response = await self._request("POST", f"/api/store/{upload_id}/complete")
        result = response.json()
        return Resource(**result) if isinstance(result, dict) else Resource(resource_id=str(result))

    async def download(
        self,
        resource_id: str,
        output_path: Union[str, Path],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """Download a file asynchronously."""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        try:
            async with self._client.stream("GET", f"/api/objects/{resource_id}/stream") as response:
                _raise_for_status(response)
                total = int(response.headers.get("content-length", 0))
                written = 0
                with open(output, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        written += len(chunk)
                        if progress_callback:
                            progress_callback(written, total)
        except httpx.TimeoutException as e:
            raise BidsTimeoutError(f"Download timed out: {e}") from e
        except httpx.ConnectError as e:
            raise BidsConnectionError(f"Connection failed: {e}") from e

        return output

    async def download_stream(
        self,
        resource_id: str,
        output_path: Union[str, Path],
        range_start: Optional[int] = None,
        range_end: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """Download a file using HTTP range requests asynchronously."""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        headers: Dict[str, str] = {}
        if range_start is not None or range_end is not None:
            start = range_start or 0
            end = range_end if range_end is not None else ""
            headers["Range"] = f"bytes={start}-{end}"

        try:
            async with self._client.stream(
                "GET", f"/api/objects/{resource_id}/stream", headers=headers
            ) as response:
                _raise_for_status(response)
                total = int(response.headers.get("content-length", 0))
                written = 0
                with open(output, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        written += len(chunk)
                        if progress_callback:
                            progress_callback(written, total)
        except httpx.TimeoutException as e:
            raise BidsTimeoutError(f"Download timed out: {e}") from e
        except httpx.ConnectError as e:
            raise BidsConnectionError(f"Connection failed: {e}") from e

        return output

    async def batch_download(
        self,
        resource_ids: List[str],
        output_path: Union[str, Path],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """Download multiple files as a zip archive asynchronously."""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        try:
            async with self._client.stream(
                "POST", "/api/objects/batch-download", json={"resource_ids": resource_ids}
            ) as response:
                _raise_for_status(response)
                total = int(response.headers.get("content-length", 0))
                written = 0
                with open(output, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
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

    async def query(
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
        """Query resources with flexible filters."""
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

        response = await self._request("GET", "/api/query", params=params)
        data = response.json()
        return QueryResult(**data) if isinstance(data, dict) else QueryResult(resources=[], total=0)

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    async def get_labels(self, resource_id: str) -> List[Dict[str, Any]]:
        response = await self._request("GET", f"/api/objects/{resource_id}/labels")
        return response.json()

    async def set_labels(
        self, resource_id: str, labels: Union[List[str], Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        response = await self._request(
            "PUT",
            f"/api/objects/{resource_id}/labels",
            json={"labels": _normalize_label_map(labels)},
        )
        return response.json()

    async def patch_labels(
        self,
        resource_id: str,
        add: Optional[Union[List[str], Dict[str, Any]]] = None,
        remove: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        body: Dict[str, Any] = {}
        if add:
            body["add"] = _normalize_label_map(add)
        if remove:
            body["remove"] = remove
        response = await self._request("PATCH", f"/api/objects/{resource_id}/labels", json=body)
        return response.json()

    async def list_all_tags(self) -> List[Dict[str, Any]]:
        response = await self._request("GET", "/api/labels")
        return response.json()

    # ------------------------------------------------------------------
    # Annotations
    # ------------------------------------------------------------------

    async def create_annotation(
        self,
        resource_id: str,
        ann_type: str,
        label: str,
        data: Optional[Dict[str, Any]] = None,
        confidence: Optional[float] = None,
    ) -> Annotation:
        body: Dict[str, Any] = {
            "resource_id": resource_id,
            "type": ann_type,
            "label": label,
        }
        if data is not None:
            body["data"] = data
        if confidence is not None:
            body["confidence"] = confidence
        response = await self._request("POST", "/api/annotations", json=body)
        return Annotation(**response.json())

    async def list_annotations(self, resource_id: str) -> List[Annotation]:
        response = await self._request("GET", f"/api/objects/{resource_id}/annotations")
        data = response.json()
        if isinstance(data, list):
            return [Annotation(**a) for a in data]
        return []

    # ------------------------------------------------------------------
    # Subjects / Sessions
    # ------------------------------------------------------------------

    async def create_subject(
        self,
        subject_id: str,
        patient_ref: Optional[str] = None,
        hospital_ids: Optional[List[str]] = None,
    ) -> Subject:
        body: Dict[str, Any] = {"subject_id": subject_id}
        if patient_ref is not None:
            body["patient_ref"] = patient_ref
        if hospital_ids is not None:
            body["hospital_ids"] = hospital_ids
        response = await self._request("POST", "/api/subjects", json=body)
        return Subject(**response.json())

    async def get_subject(self, subject_id: str) -> Subject:
        response = await self._request("GET", f"/api/subjects/{subject_id}")
        return Subject(**response.json())

    async def list_subjects(self) -> List[Subject]:
        response = await self._request("GET", "/api/subjects")
        data = response.json()
        if isinstance(data, list):
            return [Subject(**s) for s in data]
        return []

    async def create_session(
        self,
        session_id: str,
        subject_id: str,
        session_label: Optional[str] = None,
    ) -> Session:
        body: Dict[str, Any] = {
            "session_id": session_id,
            "subject_id": subject_id,
        }
        if session_label is not None:
            body["session_label"] = session_label
        response = await self._request("POST", "/api/sessions", json=body)
        return Session(**response.json())

    async def list_sessions(self, subject_id: Optional[str] = None) -> List[Session]:
        params: Dict[str, Any] = {}
        if subject_id:
            params["subject_id"] = subject_id
        response = await self._request("GET", "/api/sessions", params=params)
        data = response.json()
        if isinstance(data, list):
            return [Session(**s) for s in data]
        return []

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    async def submit_task(
        self,
        action: str,
        resource_ids: List[str],
        params: Optional[Dict[str, Any]] = None,
    ) -> Task:
        body: Dict[str, Any] = {
            "action": action,
            "resource_ids": resource_ids,
        }
        if params:
            body["params"] = params
        response = await self._request("POST", "/api/tasks", json=body)
        return Task(**response.json())

    async def get_task(self, task_id: str) -> Task:
        response = await self._request("GET", f"/api/tasks/{task_id}")
        return Task(**response.json())

    async def cancel_task(self, task_id: str) -> Task:
        response = await self._request("POST", f"/api/tasks/{task_id}/cancel")
        return Task(**response.json())

    # ------------------------------------------------------------------
    # Webhooks
    # ------------------------------------------------------------------

    async def create_webhook(
        self,
        url: str,
        events: List[str],
        name: Optional[str] = None,
        secret: Optional[str] = None,
    ) -> Webhook:
        body: Dict[str, Any] = {"url": url, "events": events}
        if name:
            body["name"] = name
        if secret:
            body["secret"] = secret
        response = await self._request("POST", "/api/webhooks", json=body)
        return Webhook(**response.json())

    async def list_webhooks(self) -> List[Webhook]:
        response = await self._request("GET", "/api/webhooks")
        data = response.json()
        if isinstance(data, list):
            return [Webhook(**w) for w in data]
        return []

    async def delete_webhook(self, webhook_id: str) -> None:
        await self._request("DELETE", f"/api/webhooks/{webhook_id}")

    # ------------------------------------------------------------------
    # System
    # ------------------------------------------------------------------

    async def verify(
        self,
        target: Optional[str] = None,
        check_hash: bool = True,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"check_hash": str(check_hash).lower()}
        if target:
            params["target"] = target
        response = await self._request("GET", "/api/verify", params=params)
        return response.json()

    async def rebuild(
        self,
        target: Optional[str] = None,
        clear_existing: bool = False,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"clear_existing": clear_existing}
        if target:
            body["target"] = target
        response = await self._request("POST", "/api/rebuild", json=body)
        return response.json()

    async def list_modalities(self) -> List[Modality]:
        response = await self._request("GET", "/api/modalities")
        data = response.json()
        if isinstance(data, list):
            return [Modality(**m) for m in data]
        return []

    async def register_modality(
        self,
        modality_id: str,
        directory: str,
        extensions: Optional[List[str]] = None,
    ) -> Modality:
        body: Dict[str, Any] = {
            "modality_id": modality_id,
            "directory": directory,
        }
        if extensions:
            body["extensions"] = extensions
        response = await self._request("POST", "/api/modalities", json=body)
        return Modality(**response.json())

    # ─── Validation ───────────────────────────────────────────────────────

    async def validate_file(
        self,
        filepath: str,
        strict: bool = False,
    ) -> Dict[str, Any]:
        """Validate a BIDS file."""
        body = {"filepath": filepath, "strict": strict}
        response = await self._request("POST", "/api/validation/file", json=body)
        return response.json()

    async def get_validation_rules(self) -> Dict[str, Any]:
        """Get BIDS validation rules."""
        response = await self._request("GET", "/api/validation/rules")
        return response.json()

    async def get_valid_entities(self) -> Dict[str, Any]:
        """Get list of valid BIDS entities."""
        response = await self._request("GET", "/api/validation/entities")
        return response.json()

    async def get_modality_info(self) -> Dict[str, Any]:
        """Get modality-specific validation information."""
        response = await self._request("GET", "/api/validation/modalities")
        return response.json()

    # ─── Health & System ──────────────────────────────────────────────────

    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the BIDS server."""
        response = await self._request("GET", "/health")
        return response.json()

    async def get_statistics(self) -> Dict[str, Any]:
        """Get server statistics."""
        response = await self._request("GET", "/api/statistics")
        return response.json()
