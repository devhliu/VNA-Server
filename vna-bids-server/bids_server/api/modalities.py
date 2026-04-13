"""Modalities API - Data type registration."""
import asyncio

import yaml
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bids_server.db.session import get_db
from bids_server.models.database import ModalityRegistry
from bids_server.models.schemas import ModalityCreate, ModalityResponse

router = APIRouter(prefix="/api/modalities", tags=["Modalities"])


@router.get("", response_model=list[ModalityResponse])
async def list_modalities(db: AsyncSession = Depends(get_db)):
    """List all registered modalities."""
    result = await db.execute(
        select(ModalityRegistry).order_by(ModalityRegistry.modality_id)
    )
    return [ModalityResponse.model_validate(m) for m in result.scalars().all()]


@router.post("", response_model=ModalityResponse, status_code=201)
async def register_modality(
    req: ModalityCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new modality (data type)."""
    existing = await db.execute(
        select(ModalityRegistry).where(ModalityRegistry.modality_id == req.modality_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"Modality {req.modality_id} already exists")

    modality = ModalityRegistry(
        modality_id=req.modality_id,
        directory=req.directory,
        description=req.description,
        extensions=req.extensions,
        required_files=req.required_files,
        category=req.category,
        is_system=False,
    )
    db.add(modality)
    await db.flush()
    return ModalityResponse.model_validate(modality)


async def load_default_modalities(db: AsyncSession):
    """Load modalities from config file on startup."""
    config_path = Path(__file__).parent.parent.parent / "config" / "modalities.yaml"
    if not await asyncio.to_thread(config_path.exists):
        return

    async with aiofiles.open(config_path) as f:
        content = await f.read()
    config = yaml.safe_load(content)

    for mod_id, mod_config in config.get("modalities", {}).items():
        existing = await db.execute(
            select(ModalityRegistry).where(ModalityRegistry.modality_id == mod_id)
        )
        if not existing.scalar_one_or_none():
            modality = ModalityRegistry(
                modality_id=mod_id,
                directory=mod_config.get("directory", mod_id),
                description=mod_config.get("description", ""),
                extensions=mod_config.get("extensions", []),
                required_files=mod_config.get("required_files", ["json"]),
                category=mod_config.get("category", "other"),
                is_system=True,
            )
            db.add(modality)

    await db.commit()
