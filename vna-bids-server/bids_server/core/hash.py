"""File hashing for integrity verification."""
import hashlib
from pathlib import Path

import aiofiles

from bids_server.config import settings


async def hash_file(file_path: Path, algorithm: str = None) -> str:
    """Compute hash of a file asynchronously."""
    algo = algorithm or settings.hash_algorithm
    h = hashlib.new(algo)
    async with aiofiles.open(file_path, "rb") as f:
        while chunk := await f.read(8192):
            h.update(chunk)
    return f"{algo}:{h.hexdigest()}"


async def hash_bytes(data: bytes, algorithm: str = None) -> str:
    """Compute hash of bytes data."""
    algo = algorithm or settings.hash_algorithm
    h = hashlib.new(algo)
    h.update(data)
    return f"{algo}:{h.hexdigest()}"


def verify_hash(data: bytes, expected_hash: str) -> bool:
    """Verify data against expected hash."""
    if not expected_hash or ":" not in expected_hash:
        return False
    algo, expected = expected_hash.split(":", 1)
    h = hashlib.new(algo)
    h.update(data)
    return h.hexdigest() == expected
