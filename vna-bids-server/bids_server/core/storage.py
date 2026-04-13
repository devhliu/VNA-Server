"""File system storage operations for BIDS Server."""
import os
import shutil
import asyncio
from pathlib import Path
from typing import Optional

import aiofiles

from bids_server.config import settings


class BidsStorage:
    """Manages BIDS file system operations."""

    def __init__(self, root: Optional[str] = None):
        self.root = Path(root or settings.bids_root)

    def get_full_path(self, bids_path: str) -> Path:
        """Convert BIDS relative path to absolute path with traversal validation."""
        full_path = (self.root / bids_path).resolve()
        if not str(full_path).startswith(str(self.root.resolve())):
            raise ValueError(f"Path traversal detected: {bids_path}")
        return full_path

    def get_subject_dir(self, subject_id: str) -> Path:
        return self.root / subject_id

    def get_session_dir(self, subject_id: str, session_id: str) -> Path:
        # session_id format: sub-001_ses-001 -> extract ses-001
        session_label = session_id.split("_")[-1] if "_" in session_id else session_id
        return self.root / subject_id / session_label

    def get_modality_dir(self, subject_id: str, session_label: str, modality: str) -> Path:
        return self.root / subject_id / session_label / modality

    async def ensure_dir(self, path: Path) -> Path:
        """Ensure directory exists."""
        await asyncio.to_thread(path.mkdir, parents=True, exist_ok=True)
        return path

    async def write_file(self, bids_path: str, data: bytes) -> Path:
        """Write data to a BIDS file path."""
        full_path = self.get_full_path(bids_path)
        await self.ensure_dir(full_path.parent)
        async with aiofiles.open(full_path, "wb") as f:
            await f.write(data)
        return full_path

    async def write_file_streaming(self, bids_path: str, source_path: Path) -> Path:
        """Move/copy a temp file to final BIDS path."""
        full_path = self.get_full_path(bids_path)
        await self.ensure_dir(full_path.parent)
        await asyncio.to_thread(shutil.move, str(source_path), str(full_path))
        return full_path

    async def read_file(self, bids_path: str) -> bytes:
        """Read entire file into memory."""
        full_path = self.get_full_path(bids_path)
        async with aiofiles.open(full_path, "rb") as f:
            return await f.read()

    async def read_file_chunk(self, bids_path: str, offset: int, size: int) -> bytes:
        """Read a chunk of a file."""
        full_path = self.get_full_path(bids_path)
        async with aiofiles.open(full_path, "rb") as f:
            await f.seek(offset)
            return await f.read(size)

    async def get_file_size(self, bids_path: str) -> int:
        """Get file size in bytes."""
        full_path = self.get_full_path(bids_path)
        exists = await asyncio.to_thread(full_path.exists)
        if not exists:
            return 0
        stat = await asyncio.to_thread(full_path.stat)
        return stat.st_size

    async def file_exists(self, bids_path: str) -> bool:
        """Check if file exists."""
        full_path = self.get_full_path(bids_path)
        return await asyncio.to_thread(full_path.exists)

    async def delete_file(self, bids_path: str) -> bool:
        """Delete a file."""
        full_path = self.get_full_path(bids_path)
        exists = await asyncio.to_thread(full_path.exists)
        if exists:
            await asyncio.to_thread(full_path.unlink)
            return True
        return False

    async def delete_directory(self, bids_path: str) -> bool:
        """Delete a directory and all contents."""
        full_path = self.get_full_path(bids_path)
        exists = await asyncio.to_thread(full_path.exists)
        is_dir = await asyncio.to_thread(full_path.is_dir)
        if exists and is_dir:
            await asyncio.to_thread(shutil.rmtree, str(full_path))
            return True
        return False

    async def list_files(self, bids_path: str, recursive: bool = False) -> list[Path]:
        """List files in a BIDS directory."""
        full_path = self.get_full_path(bids_path)
        exists = await asyncio.to_thread(full_path.exists)
        if not exists:
            return []
        
        def _list():
            if recursive:
                return [p for p in full_path.rglob("*") if p.is_file()]
            return [p for p in full_path.iterdir() if p.is_file()]
        
        return await asyncio.to_thread(_list)

    async def scan_bids_tree(self) -> list[dict]:
        """
        Scan entire BIDS directory tree.
        Returns list of {subject_id, session_label, modality, file_path, bids_path}
        """
        results = []
        if not self.root.exists():
            return results

        for subject_dir in sorted(self.root.iterdir()):
            if not subject_dir.is_dir() or not subject_dir.name.startswith("sub-"):
                continue
            subject_id = subject_dir.name

            for session_dir in sorted(subject_dir.iterdir()):
                if not session_dir.is_dir():
                    # Could be sub-xxx.json at subject level
                    if session_dir.suffix == ".json":
                        results.append({
                            "subject_id": subject_id,
                            "session_label": None,
                            "modality": "metadata",
                            "file_path": str(session_dir),
                            "bids_path": str(session_dir.relative_to(self.root)),
                        })
                    continue

                session_label = session_dir.name
                if session_label.startswith("ses-"):
                    for modality_dir in sorted(session_dir.iterdir()):
                        if not modality_dir.is_dir():
                            # Session-level JSON
                            if modality_dir.suffix == ".json":
                                results.append({
                                    "subject_id": subject_id,
                                    "session_label": session_label,
                                    "modality": "metadata",
                                    "file_path": str(modality_dir),
                                    "bids_path": str(modality_dir.relative_to(self.root)),
                                })
                            continue
                        modality = modality_dir.name
                        for data_file in sorted(modality_dir.rglob("*")):
                            if data_file.is_file():
                                results.append({
                                    "subject_id": subject_id,
                                    "session_label": session_label,
                                    "modality": modality,
                                    "file_path": str(data_file),
                                    "bids_path": str(data_file.relative_to(self.root)),
                                })
                else:
                    # Non-session subdirectory (e.g., sourcedata at subject level)
                    for data_file in sorted(session_dir.rglob("*")):
                        if data_file.is_file():
                            results.append({
                                "subject_id": subject_id,
                                "session_label": None,
                                "modality": session_dir.name,
                                "file_path": str(data_file),
                                "bids_path": str(data_file.relative_to(self.root)),
                            })

        return results


# Singleton
storage = BidsStorage()
