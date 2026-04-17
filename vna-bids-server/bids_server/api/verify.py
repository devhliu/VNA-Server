"""Verify API - Data integrity verification."""
import time
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bids_server.db.session import get_db
from bids_server.models.database import Resource
from bids_server.models.schemas import VerifyRequest, VerifyResponse, VerifyResult
from bids_server.core.storage import storage
from bids_server.core.hash import hash_file

router = APIRouter(prefix="/api/verify", tags=["Verify"])


@router.post("", response_model=VerifyResponse)
async def verify_data(
    req: VerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify data integrity.
    
    Checks:
    - File exists on disk for each DB record
    - DB record exists for each file on disk
    - Optional: content hash matches
    - Optional: auto-repair database from filesystem
    """
    results = []
    ok_count = 0
    issue_count = 0
    repaired_count = 0

    # Check DB records against filesystem
    if req.target == "all":
        query = select(Resource)
    else:
        query = select(Resource).where(
            (Resource.resource_id == req.target) | (Resource.bids_path == req.target)
        )

    db_resources = (await db.execute(query)).scalars().all()

    for resource in db_resources:
        file_path = storage.get_full_path(resource.bids_path)
        if not file_path.exists():
            result = VerifyResult(
                resource_id=resource.resource_id,
                bids_path=resource.bids_path,
                status="missing_file",
                detail="File referenced in DB does not exist on disk",
            )
            results.append(result)
            issue_count += 1
            continue

        # Check hash if requested
        if req.check_hash and resource.content_hash:
            computed_hash = await hash_file(file_path)
            if computed_hash != resource.content_hash:
                result = VerifyResult(
                    resource_id=resource.resource_id,
                    bids_path=resource.bids_path,
                    status="hash_mismatch",
                    detail=f"Expected {resource.content_hash}, got {computed_hash}",
                )
                results.append(result)
                issue_count += 1
                continue

        results.append(VerifyResult(
            resource_id=resource.resource_id,
            bids_path=resource.bids_path,
            status="ok",
        ))
        ok_count += 1

    # Check filesystem for orphaned files (files without DB records)
    if req.target == "all":
        db_paths = {r.bids_path for r in db_resources}
        fs_files = await storage.scan_bids_tree()
        for f in fs_files:
            if f["bids_path"] not in db_paths:
                if req.repair:
                    # Auto-repair: create DB record
                    resource = Resource(
                        subject_id=f.get("subject_id"),
                        session_id=f.get("subject_id") + "_" + f.get("session_label") if f.get("session_label") else None,
                        modality=f.get("modality", "other"),
                        bids_path=f["bids_path"],
                        file_name=Path(f["file_path"]).name,
                        source="recovered",
                    )
                    db.add(resource)
                    results.append(VerifyResult(
                        resource_id=None,
                        bids_path=f["bids_path"],
                        status="repaired",
                        detail="Created DB record from filesystem",
                    ))
                    repaired_count += 1
                    ok_count += 1
                else:
                    results.append(VerifyResult(
                        resource_id=None,
                        bids_path=f["bids_path"],
                        status="missing_db",
                        detail="File exists on disk but not in database",
                    ))
                    issue_count += 1

    if repaired_count > 0:
        await db.flush()

    return VerifyResponse(
        total_checked=len(results),
        ok=ok_count,
        issues=issue_count,
        repaired=repaired_count,
        results=results,
    )
