"""Advanced BIDS validation API."""

from typing import Any

from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from bids_server.db.session import get_db
from bids_server.services.advanced_validator import (
    AdvancedBIDSValidator,
    validate_bids_dataset,
    validate_bids_file,
)


router = APIRouter(prefix="/api/validation", tags=["Validation"])


class ValidateFileRequest(BaseModel):
    filepath: str
    strict: bool = False


class ValidateDatasetRequest(BaseModel):
    strict: bool = False


@router.post("/file")
async def validate_single_file(
    request: ValidateFileRequest,
) -> dict[str, Any]:
    return validate_bids_file(request.filepath, strict=request.strict)


@router.post("/upload")
async def validate_uploaded_file(
    file: UploadFile = File(...),
    strict: bool = Query(False),
) -> dict[str, Any]:
    content = await file.read()
    return validate_bids_file(file.filename, content=content, strict=strict)


@router.get("/rules")
async def get_validation_rules() -> dict[str, Any]:
    return {
        "required_files": [
            {"file": "dataset_description.json", "description": "Root level dataset description"},
        ],
        "recommended_files": [
            {"file": "participants.tsv", "description": "Participant information"},
            {"file": "participants.json", "description": "Participant metadata"},
            {"file": "README", "description": "Dataset documentation"},
            {"file": "CHANGES", "description": "Version history"},
        ],
        "valid_entities": [
            {"entity": "sub", "description": "Subject label"},
            {"entity": "ses", "description": "Session label"},
            {"entity": "task", "description": "Task name"},
            {"entity": "acq", "description": "Acquisition label"},
            {"entity": "ce", "description": "Contrast enhanced"},
            {"entity": "rec", "description": "Reconstruction label"},
            {"entity": "dir", "description": "Phase encoding direction"},
            {"entity": "run", "description": "Run index"},
            {"entity": "echo", "description": "Echo index"},
            {"entity": "part", "description": "Part (mag/phase/real/imag)"},
            {"entity": "proc", "description": "Processed label"},
            {"entity": "space", "description": "Space label"},
            {"entity": "desc", "description": "Description label"},
        ],
        "modality_requirements": [
            {
                "modality": "func",
                "required_entities": ["task"],
                "valid_extensions": [".nii", ".nii.gz", ".json", ".tsv"],
            },
            {
                "modality": "dwi",
                "required_entities": [],
                "valid_extensions": [".nii", ".nii.gz", ".json", ".bval", ".bvec"],
            },
            {
                "modality": "anat",
                "required_entities": [],
                "valid_extensions": [".nii", ".nii.gz", ".json"],
            },
            {
                "modality": "fmap",
                "required_entities": [],
                "valid_extensions": [".nii", ".nii.gz", ".json"],
            },
            {
                "modality": "eeg",
                "required_entities": [],
                "valid_extensions": [".edf", ".vhdr", ".vmrk", ".eeg", ".set", ".fdt", ".json", ".tsv"],
            },
            {
                "modality": "meg",
                "required_entities": [],
                "valid_extensions": [".fif", ".ds", ".json", ".tsv"],
            },
            {
                "modality": "pet",
                "required_entities": ["trc"],
                "valid_extensions": [".nii", ".nii.gz", ".json"],
            },
            {
                "modality": "ct",
                "required_entities": [],
                "valid_extensions": [".nii", ".nii.gz", ".json"],
            },
        ],
    }


@router.get("/entities")
async def get_valid_entities() -> dict[str, Any]:
    from bids_server.services.advanced_validator import VALID_ENTITIES
    return {
        "entities": sorted(list(VALID_ENTITIES)),
        "total": len(VALID_ENTITIES),
    }


@router.get("/modalities")
async def get_modality_info() -> dict[str, Any]:
    from bids_server.services.advanced_validator import (
        MODALITY_REQUIRED_ENTITIES,
        MODALITY_FILE_EXTENSIONS,
    )
    
    modalities = []
    for modality in sorted(MODALITY_REQUIRED_ENTITIES.keys()):
        modalities.append({
            "name": modality,
            "required_entities": MODALITY_REQUIRED_ENTITIES.get(modality, []),
            "valid_extensions": sorted(list(MODALITY_FILE_EXTENSIONS.get(modality, set()))),
        })
    
    return {
        "modalities": modalities,
        "total": len(modalities),
    }
