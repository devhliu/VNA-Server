"""Chunked upload management for large files."""
import asyncio
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

import aiofiles

from bids_server.config import settings


class UploadManager:
    """Manages resumable chunked uploads."""

    def __init__(self, temp_dir: Optional[str] = None):
        self.temp_dir = Path(temp_dir or settings.upload_temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        # In-memory upload state (production would use Redis)
        self._uploads: dict[str, dict] = {}

    def _upload_dir(self, upload_id: str) -> Path:
        return self.temp_dir / upload_id

    async def init_upload(
        self,
        file_name: str,
        file_size: int,
        modality: str,
        chunk_size: Optional[int] = None,
        subject_id: Optional[str] = None,
        session_id: Optional[str] = None,
        source: str = "user_upload",
        labels: Optional[dict] = None,
        metadata: Optional[dict] = None,
        dicom_ref: Optional[str] = None,
    ) -> dict:
        """Initialize a new upload session."""
        upload_id = f"upl-{uuid.uuid4().hex[:12]}"
        chunk_size = chunk_size or settings.chunk_size
        total_chunks = (file_size + chunk_size - 1) // chunk_size

        upload_dir = self._upload_dir(upload_id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        state = {
            "upload_id": upload_id,
            "file_name": file_name,
            "file_size": file_size,
            "modality": modality,
            "subject_id": subject_id,
            "session_id": session_id,
            "source": source,
            "labels": labels,
            "metadata": metadata,
            "dicom_ref": dicom_ref,
            "chunk_size": chunk_size,
            "total_chunks": total_chunks,
            "chunks_received": [],
            "bytes_received": 0,
            "status": "uploading",
        }

        # Persist state to disk
        state_path = upload_dir / "state.json"
        async with aiofiles.open(state_path, "w") as f:
            await f.write(json.dumps(state))

        self._uploads[upload_id] = state
        return state

    async def write_chunk(self, upload_id: str, chunk_index: int, data: bytes) -> dict:
        """Write a chunk to the upload session."""
        state = await self._get_state(upload_id)
        if state["status"] != "uploading":
            raise ValueError(f"Upload {upload_id} is {state['status']}, not uploading")

        chunk_path = self._upload_dir(upload_id) / f"chunk_{chunk_index:06d}"
        async with aiofiles.open(chunk_path, "wb") as f:
            await f.write(data)

        if chunk_index not in state["chunks_received"]:
            state["chunks_received"].append(chunk_index)
            state["bytes_received"] += len(data)

        # Persist updated state
        await self._save_state(upload_id, state)
        return state

    async def complete_upload(self, upload_id: str) -> dict:
        """Assemble chunks into final file and return state."""
        state = await self._get_state(upload_id)
        upload_dir = self._upload_dir(upload_id)

        # Verify all chunks received
        expected_chunks = set(range(state["total_chunks"]))
        received_chunks = set(state["chunks_received"])
        if expected_chunks != received_chunks:
            missing = expected_chunks - received_chunks
            state["status"] = "incomplete"
            await self._save_state(upload_id, state)
            raise ValueError(f"Missing chunks: {sorted(missing)}")

        # Assemble chunks into single file
        assembled_path = upload_dir / state["file_name"]
        async with aiofiles.open(assembled_path, "wb") as out:
            for i in range(state["total_chunks"]):
                chunk_path = upload_dir / f"chunk_{i:06d}"
                async with aiofiles.open(chunk_path, "rb") as chunk:
                    while data := await chunk.read(8 * 1024 * 1024):
                        await out.write(data)

        state["status"] = "completed"
        state["assembled_path"] = str(assembled_path)
        await self._save_state(upload_id, state)
        return state

    async def get_status(self, upload_id: str) -> dict:
        """Get upload status."""
        return await self._get_state(upload_id)

    async def cancel_upload(self, upload_id: str) -> bool:
        """Cancel and clean up an upload."""
        upload_dir = self._upload_dir(upload_id)
        if upload_dir.exists():
            await asyncio.to_thread(shutil.rmtree, str(upload_dir))
        if upload_id in self._uploads:
            del self._uploads[upload_id]
        return True

    async def cleanup_completed(self, upload_id: str):
        """Clean up temp files after successful processing."""
        upload_dir = self._upload_dir(upload_id)
        if upload_dir.exists():
            await asyncio.to_thread(shutil.rmtree, str(upload_dir))
        if upload_id in self._uploads:
            del self._uploads[upload_id]

    async def _get_state(self, upload_id: str) -> dict:
        """Get upload state from memory or disk."""
        if upload_id in self._uploads:
            return self._uploads[upload_id]

        state_path = self._upload_dir(upload_id) / "state.json"
        if await asyncio.to_thread(state_path.exists):
            async with aiofiles.open(state_path) as f:
                state = json.loads(await f.read())
            self._uploads[upload_id] = state
            return state

        raise ValueError(f"Upload {upload_id} not found")

    async def _save_state(self, upload_id: str, state: dict):
        """Persist state to disk."""
        state_path = self._upload_dir(upload_id) / "state.json"
        async with aiofiles.open(state_path, "w") as f:
            await f.write(json.dumps(state))
        self._uploads[upload_id] = state


# Singleton
upload_manager = UploadManager()
