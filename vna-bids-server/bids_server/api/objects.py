"""Objects API - Retrieve/download files (BIDSweb equivalent of WADO-RS)."""

import io
import json
import logging
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bids_server.db.session import get_db
from bids_server.models.database import (
    Resource,
    Label,
    Annotation,
    ProcessingLog,
    Relationship,
)
from bids_server.models.schemas import (
    ResourceResponse,
    RelationshipResponse,
    RelationshipUpdate,
)
from bids_server.core.storage import storage
from bids_server.core.stream import stream_file, parse_range_header
from bids_server.core.hash import hash_file
from bids_server.core.webhook_manager import webhook_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bidsweb/v1/objects", tags=["Objects"])


@router.get("/{resource_id}")
async def get_object(
    resource_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Download a file by resource ID."""
    resource = await _get_resource(db, resource_id)
    file_path = storage.get_full_path(resource.bids_path)

    if not file_path.exists():
        raise HTTPException(404, "File not found on disk")

    # Determine media type
    media_type = _guess_media_type(resource.file_name)

    return StreamingResponse(
        stream_file(file_path),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{resource.file_name}"',
            "X-Resource-Id": resource_id,
            "X-Content-Hash": resource.content_hash or "",
        },
    )


@router.get("/{resource_id}/stream")
async def stream_object(
    resource_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Stream a file with Range support for large files."""
    resource = await _get_resource(db, resource_id)
    file_path = storage.get_full_path(resource.bids_path)

    if not file_path.exists():
        raise HTTPException(404, "File not found on disk")

    file_size = file_path.stat().st_size
    range_header = request.headers.get("range")
    media_type = _guess_media_type(resource.file_name)

    if range_header:
        range_spec = parse_range_header(range_header, file_size)
        if range_spec:
            start, end = range_spec
            length = end - start + 1
            return StreamingResponse(
                stream_file(file_path, offset=start, length=length),
                status_code=206,
                media_type=media_type,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(length),
                    "Accept-Ranges": "bytes",
                },
            )

    # Full file
    return StreamingResponse(
        stream_file(file_path),
        media_type=media_type,
        headers={
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        },
    )


@router.get("/{resource_id}/metadata")
async def get_metadata(
    resource_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the JSON sidecar metadata for a resource."""
    resource = await _get_resource(db, resource_id)

    # Try to find the sidecar JSON
    bids_path = resource.bids_path
    if bids_path.endswith(".json"):
        json_path = bids_path
    else:
        base = bids_path.rsplit(".", 1)[0]
        json_path = f"{base}.json"

    if storage.file_exists(json_path):
        data = await storage.read_file(json_path)
        return Response(content=data, media_type="application/json")

    # Return DB metadata as fallback
    return {"VNA": {"resourceId": resource_id, "metadata": resource.metadata_}}


@router.get("/{resource_id}/render")
async def render_object(
    resource_id: str,
    format: str = Query(default="jpeg", description="Output format: jpeg, png"),
    quality: int = Query(default=80, ge=1, le=100),
    slice_index: int | None = Query(
        default=None, description="Slice index for 3D volumes (middle slice if omitted)"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Render/preview a file. Supports images directly; NIfTI and DICOM via extraction."""
    resource = await _get_resource(db, resource_id)

    file_path = storage.get_full_path(resource.bids_path)
    if not file_path.exists():
        raise HTTPException(404, "File not found")

    ext = resource.file_name.lower()

    # Direct image formats
    if any(
        ext.endswith(e)
        for e in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".tiff", ".tif"]
    ):
        media_type = f"image/{format}" if format in ("jpeg", "png") else "image/jpeg"
        return StreamingResponse(
            stream_file(file_path),
            media_type=media_type,
        )

    # NIfTI rendering via nibabel
    if ext.endswith((".nii", ".nii.gz")):
        return await _render_nifti(file_path, resource.file_name, format, slice_index)

    # DICOM rendering via pydicom
    if ext.endswith(".dcm") or ext == "dicom":
        return await _render_dicom(file_path, format)

    raise HTTPException(
        status_code=501,
        detail={
            "error": "rendering_not_supported",
            "message": f"Rendering not supported for file type: {resource.file_type or 'unknown'}",
            "file_name": resource.file_name,
            "suggestion": "Use /stream to download the raw file",
        },
    )


async def _render_nifti(
    file_path: Path,
    file_name: str,
    format: str,
    slice_index: int | None,
) -> Response:
    """Extract a slice from a NIfTI volume and return as PNG/JPEG."""
    try:
        import nibabel as nib
        import numpy as np
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail={
                "error": "nifti_rendering_unavailable",
                "message": "nibabel is not installed. Cannot render NIfTI files.",
                "file_name": file_name,
                "suggestion": "Install nibabel: pip install nibabel",
            },
        )

    try:
        img = nib.load(str(file_path))
        data = img.get_fdata()

        # Handle 3D and 4D volumes
        if data.ndim == 4:
            data = data[:, :, :, 0]  # Take first volume
        if data.ndim != 3:
            raise HTTPException(422, f"Unsupported NIfTI dimensionality: {data.ndim}D")

        # Select middle slice along the axial axis if not specified
        if slice_index is None:
            slice_index = data.shape[2] // 2
        slice_index = max(0, min(slice_index, data.shape[2] - 1))
        slice_2d = data[:, :, slice_index]

        # Normalize to 0-255
        vmin, vmax = np.nanmin(slice_2d), np.nanmax(slice_2d)
        if vmax > vmin:
            normalized = ((slice_2d - vmin) / (vmax - vmin) * 255).astype(np.uint8)
        else:
            normalized = np.zeros_like(slice_2d, dtype=np.uint8)

        # Encode as PNG
        try:
            from PIL import Image

            img_obj = Image.fromarray(normalized, mode="L")
            buf = io.BytesIO()
            img_obj.save(buf, format="PNG")
            buf.seek(0)
            return Response(content=buf.read(), media_type="image/png")
        except ImportError:
            raise HTTPException(
                status_code=501,
                detail={
                    "error": "nifti_rendering_unavailable",
                    "message": "Pillow is not installed. Cannot encode NIfTI slice as image.",
                    "file_name": file_name,
                    "suggestion": "Install Pillow: pip install Pillow",
                },
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "nifti_rendering_failed",
                "message": f"Failed to render NIfTI: {exc}",
                "file_name": file_name,
            },
        )


async def _render_dicom(file_path: Path, format: str) -> Response:
    """Extract a frame from a DICOM file and return as PNG/JPEG."""
    try:
        import pydicom
        from pydicom.pixel_data_handlers.util import apply_voi_lut
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail={
                "error": "dicom_rendering_unavailable",
                "message": "pydicom is not installed. Cannot render DICOM files.",
                "file_name": file_path.name,
                "suggestion": "Install pydicom: pip install pydicom",
            },
        )

    try:
        ds = pydicom.dcmread(str(file_path))

        if not hasattr(ds, "PixelData"):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "dicom_no_pixel_data",
                    "message": "DICOM file has no pixel data to render.",
                    "file_name": file_path.name,
                },
            )

        # Get pixel array and normalize
        import numpy as np

        try:
            arr = apply_voi_lut(ds.pixel_array, ds)
        except Exception:
            logger.debug("VOI LUT not applicable for %s, using raw pixel array", file_path.name)
            arr = ds.pixel_array

        if arr.ndim == 3:
            arr = arr[:, :, 0]  # Take first frame for multi-frame

        # Normalize to 0-255
        if arr.dtype != np.uint8:
            vmin, vmax = arr.min(), arr.max()
            if vmax > vmin:
                arr = ((arr - vmin) / (vmax - vmin) * 255).astype(np.uint8)
            else:
                arr = np.zeros_like(arr, dtype=np.uint8)

        try:
            from PIL import Image

            img_obj = Image.fromarray(arr, mode="L")
            buf = io.BytesIO()
            img_obj.save(buf, format="PNG")
            buf.seek(0)
            return Response(content=buf.read(), media_type="image/png")
        except ImportError:
            raise HTTPException(
                status_code=501,
                detail={
                    "error": "dicom_rendering_unavailable",
                    "message": "Pillow is not installed. Cannot encode DICOM frame as image.",
                    "file_name": file_path.name,
                    "suggestion": "Install Pillow: pip install Pillow",
                },
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "dicom_rendering_failed",
                "message": f"Failed to render DICOM: {exc}",
                "file_name": file_path.name,
            },
        )


@router.delete("/{resource_id}")
async def delete_object(
    resource_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a resource and its file."""
    resource = await _get_resource(db, resource_id)
    bids_path = resource.bids_path

    # Delete file
    await storage.delete_file(bids_path)

    # Delete sidecar JSON if different file
    if not bids_path.endswith(".json"):
        base = bids_path.rsplit(".", 1)[0]
        json_path = f"{base}.json"
        await storage.delete_file(json_path)

    # Delete DB record (cascades to labels, annotations, etc.)
    await db.delete(resource)
    await db.flush()

    await webhook_manager.dispatch(
        "resource.deleted",
        {"resource_id": resource_id, "bids_path": bids_path},
        resource_id,
    )

    return {"deleted": True, "resource_id": resource_id}


@router.get("/{resource_id}/labels")
async def get_object_labels(
    resource_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all labels for a resource."""
    result = await db.execute(
        select(Label).where(Label.resource_id == resource_id).order_by(Label.tag_key)
    )
    labels = result.scalars().all()
    return [
        {
            "key": l.tag_key,
            "value": l.tag_value,
            "tagged_by": l.tagged_by,
            "tagged_at": l.tagged_at,
        }
        for l in labels
    ]


@router.get("/{resource_id}/annotations")
async def get_object_annotations(
    resource_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all annotations for a resource."""
    result = await db.execute(
        select(Annotation)
        .where(Annotation.resource_id == resource_id)
        .order_by(Annotation.created_at)
    )
    annotations = result.scalars().all()
    return [
        {
            "annotation_id": a.annotation_id,
            "resource_id": a.resource_id,
            "type": a.ann_type,
            "label": a.label,
            "data": a.data,
            "confidence": a.confidence,
            "created_by": a.created_by,
            "created_at": a.created_at,
        }
        for a in annotations
    ]


@router.get("/{resource_id}/processing")
async def get_object_processing(
    resource_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get processing history for a resource."""
    result = await db.execute(
        select(ProcessingLog)
        .where(ProcessingLog.resource_id == resource_id)
        .order_by(ProcessingLog.executed_at.desc())
    )
    logs = result.scalars().all()
    return [
        {
            "id": log.id,
            "pipeline": log.pipeline,
            "input_resources": log.input_resources,
            "params": log.params,
            "executed_by": log.executed_by,
            "executed_at": log.executed_at,
        }
        for log in logs
    ]


@router.get("/{resource_id}/relationships")
async def get_object_relationships(
    resource_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get data relationships for a resource."""
    result = await db.execute(
        select(Relationship).where(Relationship.resource_id == resource_id)
    )
    rel = result.scalar_one_or_none()
    if not rel:
        return {
            "resource_id": resource_id,
            "parent_refs": [],
            "children_refs": [],
            "dicom_ref": None,
            "same_subject": [],
        }
    return RelationshipResponse.model_validate(rel)


@router.put("/{resource_id}/relationships")
async def update_object_relationships(
    resource_id: str,
    req: RelationshipUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update data relationships."""
    result = await db.execute(
        select(Relationship).where(Relationship.resource_id == resource_id)
    )
    rel = result.scalar_one_or_none()

    if not rel:
        rel = Relationship(resource_id=resource_id)
        db.add(rel)

    if req.parent_refs is not None:
        rel.parent_refs = req.parent_refs
    if req.children_refs is not None:
        rel.children_refs = req.children_refs
    if req.dicom_ref is not None:
        rel.dicom_ref = req.dicom_ref
    if req.same_subject is not None:
        rel.same_subject = req.same_subject

    await db.flush()
    return RelationshipResponse.model_validate(rel)


@router.post("/batch-download")
async def batch_download(
    resource_ids: list[str],
    format: str = "zip",
    db: AsyncSession = Depends(get_db),
):
    """Download multiple files as a zip archive."""

    result = await db.execute(
        select(Resource).where(Resource.resource_id.in_(resource_ids))
    )
    resources = {r.resource_id: r for r in result.scalars().all()}

    async def generate_zip():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for rid in resource_ids:
                resource = resources.get(rid)
                if resource:
                    file_path = storage.get_full_path(resource.bids_path)
                    if file_path.exists():
                        zf.write(str(file_path), resource.bids_path)
        buf.seek(0)
        while chunk := buf.read(8 * 1024 * 1024):
            yield chunk

    return StreamingResponse(
        generate_zip(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=bids_batch.zip"},
    )


async def _get_resource(db: AsyncSession, resource_id: str) -> Resource:
    result = await db.execute(
        select(Resource).where(Resource.resource_id == resource_id)
    )
    resource = result.scalar_one_or_none()
    if not resource:
        raise HTTPException(404, f"Resource {resource_id} not found")
    return resource


def _guess_media_type(filename: str) -> str:
    name = filename.lower()
    if name.endswith(".nii.gz") or name.endswith(".nii"):
        return "application/gzip"
    elif name.endswith(".json"):
        return "application/json"
    elif name.endswith(".csv") or name.endswith(".tsv"):
        return "text/csv"
    elif name.endswith(".pdf"):
        return "application/pdf"
    elif name.endswith(".jpg") or name.endswith(".jpeg"):
        return "image/jpeg"
    elif name.endswith(".png"):
        return "image/png"
    elif name.endswith(".tiff") or name.endswith(".tif"):
        return "image/tiff"
    else:
        return "application/octet-stream"
