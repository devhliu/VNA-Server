"""Streaming utilities for large file transfers."""
from pathlib import Path
from typing import AsyncGenerator, Optional, Tuple

import aiofiles


async def stream_file(
    file_path: Path,
    chunk_size: int = 8 * 1024 * 1024,  # 8MB
    offset: int = 0,
    length: Optional[int] = None,
) -> AsyncGenerator[bytes, None]:
    """Stream a file in chunks."""
    async with aiofiles.open(file_path, "rb") as f:
        if offset > 0:
            await f.seek(offset)

        bytes_read = 0
        while True:
            if length is not None:
                remaining = length - bytes_read
                if remaining <= 0:
                    break
                read_size = min(chunk_size, remaining)
            else:
                read_size = chunk_size

            chunk = await f.read(read_size)
            if not chunk:
                break
            bytes_read += len(chunk)
            yield chunk


def parse_range_header(range_header: str, file_size: int) -> Optional[Tuple[int, int]]:
    """
    Parse HTTP Range header.
    Returns (start, end) inclusive, or None if invalid.
    Supports single range only: bytes=start-end
    """
    if not range_header or not range_header.startswith("bytes="):
        return None

    range_spec = range_header[6:].strip()
    if "," in range_spec:
        # Multiple ranges not supported, return first
        range_spec = range_spec.split(",")[0].strip()

    try:
        if range_spec.startswith("-"):
            # Suffix range: bytes=-500 (last 500 bytes)
            suffix_length = int(range_spec[1:])
            start = max(0, file_size - suffix_length)
            end = file_size - 1
        elif range_spec.endswith("-"):
            # Open-ended: bytes=500-
            start = int(range_spec[:-1])
            end = file_size - 1
        else:
            # Closed range: bytes=500-999
            parts = range_spec.split("-")
            start = int(parts[0])
            end = int(parts[1])

        # Clamp to file size
        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))
        return (start, end)
    except (ValueError, IndexError):
        return None
