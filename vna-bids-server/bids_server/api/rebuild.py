"""Rebuild API - Reconstruct database from filesystem."""
import json
import logging
import time
import asyncio
from pathlib import Path

import aiofiles

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bids_server.db.session import get_db
from bids_server.models.database import Resource, Subject, Session, Label
from bids_server.models.schemas import RebuildRequest, RebuildResponse
from bids_server.core.storage import storage
from bids_server.core.hash import hash_file
from bids_server.core.bids_validator import guess_file_type
from bids_server.services.search_service import search_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rebuild", tags=["Rebuild"])


@router.post("", response_model=RebuildResponse)
async def rebuild_database(
    req: RebuildRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Rebuild database indexes from BIDS filesystem.
    
    Scans the BIDS directory tree and rebuilds:
    - subjects: from sub-* directories
    - sessions: from ses-* directories
    - resources: from all data files
    - labels: from JSON sidecar files
    
    This is the recovery mechanism - filesystem is the source of truth.
    """
    start_time = time.time()
    subjects_found = 0
    sessions_found = 0
    resources_found = 0
    labels_found = 0

    # Clear existing data if requested
    if req.clear_existing:
        if req.target in ("all", "labels"):
            await db.execute(delete(Label))
        if req.target in ("all", "resources"):
            await db.execute(delete(Resource))
        if req.target in ("all", "sessions"):
            await db.execute(delete(Session))
        if req.target in ("all", "subjects"):
            await db.execute(delete(Subject))
        await db.flush()

    # Scan filesystem
    fs_tree = await storage.scan_bids_tree()
    seen_subjects = set()
    seen_sessions = set()

    for entry in fs_tree:
        subject_id = entry["subject_id"]
        session_label = entry.get("session_label")
        bids_path = entry["bids_path"]
        file_path = Path(entry["file_path"])

        # Create subject if new
        if subject_id not in seen_subjects:
            existing = await db.get(Subject, subject_id)
            if not existing:
                subject = Subject(subject_id=subject_id)
                db.add(subject)
                subjects_found += 1
            seen_subjects.add(subject_id)

        # Create session if new
        if session_label:
            session_id = f"{subject_id}_{session_label}"
            if session_id not in seen_sessions:
                existing = await db.get(Session, session_id)
                if not existing:
                    session = Session(
                        session_id=session_id,
                        subject_id=subject_id,
                        session_label=session_label,
                    )
                    db.add(session)
                    sessions_found += 1
                seen_sessions.add(session_id)

        # Check if resource exists in DB
        existing_res = await db.execute(
            Resource.__table__.select().where(Resource.bids_path == bids_path)
        )
        if existing_res.fetchone():
            continue

        # Determine session_id for resource
        session_id = f"{subject_id}_{session_label}" if session_label else None

        # Create resource
        modality = entry.get("modality", "other")
        file_name = file_path.name
        
        file_exists = await asyncio.to_thread(file_path.exists)
        file_size = 0
        if file_exists:
            stat = await asyncio.to_thread(file_path.stat)
            file_size = stat.st_size
        
        content_hash = None
        try:
            if file_exists and file_size < 500 * 1024 * 1024:  # Skip hashing >500MB for speed
                content_hash = await hash_file(file_path)
        except (OSError, ValueError) as exc:
            logger.warning("Failed to hash file %s: %s", file_path, exc)

        # Read metadata from JSON sidecar
        metadata = {}
        if file_name.endswith(".json"):
            try:
                async with aiofiles.open(file_path, "r") as f:
                    metadata = json.loads(await f.read())
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Failed to read JSON sidecar %s: %s", file_path, exc)

        resource = Resource(
            subject_id=subject_id,
            session_id=session_id,
            modality=modality,
            bids_path=bids_path,
            file_name=file_name,
            file_type=guess_file_type(file_name),
            file_size=file_size,
            content_hash=content_hash,
            source="recovered",
            metadata_=metadata,
        )
        db.add(resource)
        resources_found += 1

        # Extract labels from JSON sidecar
        if file_name.endswith(".json") and "VNA" in metadata:
            vna_data = metadata.get("VNA", {})
            labels = vna_data.get("labels", {})
            for key, value in labels.items():
                label = Label(
                    resource_id=resource.resource_id,
                    level="file",
                    tag_key=key,
                    tag_value=str(value) if not isinstance(value, (dict, list)) else json.dumps(value),
                    tagged_by="rebuild",
                )
                db.add(label)
                labels_found += 1

        # Also look for sidecar JSON for data files
        elif not file_name.endswith(".json"):
            json_path = str(file_path).rsplit(".", 1)[0] + ".json"
            json_file = Path(json_path)
            json_exists = await asyncio.to_thread(json_file.exists)
            if json_exists:
                try:
                    async with aiofiles.open(json_file) as f:
                        sidecar = json.loads(await f.read())
                    vna_data = sidecar.get("VNA", {})
                    labels = vna_data.get("labels", {})
                    for key, value in labels.items():
                        label = Label(
                            resource_id=resource.resource_id,
                            level="file",
                            tag_key=key,
                            tag_value=str(value) if not isinstance(value, (dict, list)) else json.dumps(value),
                            tagged_by="rebuild",
                        )
                        db.add(label)
                        labels_found += 1
                except (OSError, json.JSONDecodeError, KeyError) as exc:
                    logger.warning("Failed to read sidecar labels from %s: %s", json_file, exc)

    await db.flush()

    # Update search vectors
    all_resources = (await db.execute(select(Resource))).scalars().all()
    for resource in all_resources:
        await search_service.update_search_vector(db, resource.resource_id)

    await db.flush()

    duration = time.time() - start_time

    return RebuildResponse(
        target=req.target,
        subjects_found=subjects_found,
        sessions_found=sessions_found,
        resources_found=resources_found,
        labels_found=labels_found,
        duration_seconds=round(duration, 2),
    )
