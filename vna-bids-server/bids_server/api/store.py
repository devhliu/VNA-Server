"""Store API - Upload files (BIDSweb equivalent of STOW-RS)."""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from bids_server.config import settings
from bids_server.db.session import get_db
from bids_server.models.schemas import (
    UploadInitRequest,
    UploadInitResponse,
    UploadStatusResponse,
    ResourceResponse,
)
from bids_server.core.upload import upload_manager
from bids_server.core.storage import storage
from bids_server.core.hash import hash_bytes, hash_file
from bids_server.core.bids_validator import guess_modality_from_path, guess_file_type
from bids_server.core.webhook_manager import webhook_manager
from bids_server.models.database import Resource, Subject, Session, Label
from bids_server.services.search_service import search_service
from sqlalchemy import select
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/store", tags=["Store"])


@router.post("/init", response_model=UploadInitResponse)
async def init_upload(req: UploadInitRequest):
    """Initialize a chunked upload session."""
    state = await upload_manager.init_upload(
        file_name=req.file_name,
        file_size=req.file_size,
        modality=req.modality,
        subject_id=req.subject_id,
        session_id=req.session_id,
        source=req.source,
        labels=req.labels,
        metadata=req.metadata,
        dicom_ref=req.dicom_ref,
    )
    return UploadInitResponse(
        upload_id=state["upload_id"],
        chunk_size=state["chunk_size"],
        total_chunks=state["total_chunks"],
    )


@router.patch("/{upload_id}", response_model=UploadStatusResponse)
async def upload_chunk(
    upload_id: str,
    chunk_index: int = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a chunk for a resumable upload."""
    # Check file size
    content = await file.read()
    file_size = len(content)
    if file_size > settings.chunk_size:
        raise HTTPException(
            status_code=413,
            detail=f"Chunk size {file_size} exceeds maximum allowed size {settings.chunk_size} bytes"
        )
    state = await upload_manager.write_chunk(upload_id, chunk_index, content)
    return UploadStatusResponse(
        upload_id=upload_id,
        file_name=state["file_name"],
        file_size=state["file_size"],
        bytes_received=state["bytes_received"],
        chunks_received=state["chunks_received"],
        status=state["status"],
    )


@router.post("/{upload_id}/complete", response_model=ResourceResponse)
async def complete_upload(upload_id: str, db: AsyncSession = Depends(get_db)):
    """Complete a chunked upload - assemble and register in database."""
    state = await upload_manager.complete_upload(upload_id)

    # Build BIDS path
    bids_path = _build_bids_path(state)

    # Move file to final location
    from pathlib import Path
    assembled_path = Path(state["assembled_path"])
    await storage.write_file_streaming(bids_path, assembled_path)

    # Hash the file
    content_hash = await hash_file(storage.get_full_path(bids_path))

    # Create resource in DB
    resource = Resource(
        subject_id=state.get("subject_id"),
        session_id=state.get("session_id"),
        modality=state["modality"],
        bids_path=bids_path,
        file_name=state["file_name"],
        file_type=guess_file_type(state["file_name"]),
        file_size=state["file_size"],
        content_hash=content_hash,
        source=state.get("source", "user_upload"),
        dicom_ref=state.get("dicom_ref"),
        metadata_=state.get("metadata") or {},
    )
    db.add(resource)
    await db.flush()

    # Write JSON sidecar if labels provided
    if state.get("labels"):
        json_path = bids_path.rsplit(".", 1)[0] + ".json"
        sidecar = {"VNA": {"resourceId": resource.resource_id, "labels": state["labels"]}}
        await storage.write_file(json_path, json.dumps(sidecar, indent=2, ensure_ascii=False).encode())

        for key, value in state["labels"].items():
            label = Label(
                resource_id=resource.resource_id,
                level="file",
                tag_key=key,
                tag_value=str(value) if not isinstance(value, (dict, list)) else json.dumps(value),
            )
            db.add(label)

    await db.commit()
    response = ResourceResponse.model_validate(resource)

    # Clean up temp files
    await upload_manager.cleanup_completed(upload_id)

    # Dispatch webhook (non-critical)
    try:
        await webhook_manager.dispatch(
            "resource.created",
            {"resource_id": resource.resource_id, "bids_path": bids_path},
            resource.resource_id,
        )
    except Exception as exc:
        logger.warning("Webhook dispatch failed: %s", exc)

    return response


@router.post("", response_model=ResourceResponse)
async def upload_single_file(
    file: UploadFile = File(...),
    subject_id: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    modality: str = Form("other"),
    source: str = Form("user_upload"),
    labels: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None),
    dicom_ref: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload a single file directly (non-chunked)."""
    # Check file size
    data = await file.read()
    file_size = len(data)
    if file_size > settings.max_upload_size:
        raise HTTPException(
            status_code=413,
            detail=f"File size {file_size} exceeds maximum allowed size {settings.max_upload_size} bytes"
        )
    
    # Build BIDS path
    bids_path = _build_bids_path_simple(
        file_name=file.filename or "unnamed",
        subject_id=subject_id,
        session_id=session_id,
        modality=modality,
    )

    # Write file
    await storage.write_file(bids_path, data)

    # Hash
    content_hash = await hash_bytes(data)

    # Parse optional JSON fields
    labels_dict = json.loads(labels) if labels else {}
    metadata_dict = json.loads(metadata) if metadata else {}

    # Create resource
    resource = Resource(
        subject_id=subject_id,
        session_id=session_id,
        modality=modality,
        bids_path=bids_path,
        file_name=file.filename,
        file_type=guess_file_type(file.filename),
        file_size=file_size,
        content_hash=content_hash,
        source=source,
        dicom_ref=dicom_ref,
        metadata_=metadata_dict,
    )
    db.add(resource)
    await db.flush()

    # Labels
    if labels_dict:
        json_path = bids_path.rsplit(".", 1)[0] + ".json"
        sidecar = {"VNA": {"resourceId": resource.resource_id, "labels": labels_dict}}
        await storage.write_file(json_path, json.dumps(sidecar, indent=2, ensure_ascii=False).encode())

        for key, value in labels_dict.items():
            label = Label(
                resource_id=resource.resource_id,
                level="file",
                tag_key=key,
                tag_value=str(value) if not isinstance(value, (dict, list)) else json.dumps(value),
            )
            db.add(label)

    await db.commit()

    # Build response before closing
    response = ResourceResponse.model_validate(resource)

    # Non-critical post-commit operations
    try:
        await webhook_manager.dispatch(
            "resource.created",
            {"resource_id": resource.resource_id, "bids_path": bids_path},
            resource.resource_id,
        )
    except Exception as exc:
        logger.warning("Webhook dispatch failed: %s", exc)

    return response


def _build_bids_path(state: dict) -> str:
    """Build BIDS file path from upload state."""
    parts = []
    if state.get("subject_id"):
        parts.append(state["subject_id"])
    if state.get("session_id"):
        session_label = state["session_id"].split("_")[-1] if "_" in state["session_id"] else state["session_id"]
        parts.append(session_label)
    parts.append(state["modality"])
    parts.append(state["file_name"])
    return "/".join(parts)


def _build_bids_path_simple(
    file_name: str,
    subject_id: Optional[str],
    session_id: Optional[str],
    modality: str,
) -> str:
    """Build BIDS path from form params."""
    parts = []
    if subject_id:
        parts.append(subject_id)
    if session_id:
        session_label = session_id.split("_")[-1] if "_" in session_id else session_id
        parts.append(session_label)
    parts.append(modality)
    parts.append(file_name)
    return "/".join(parts)
