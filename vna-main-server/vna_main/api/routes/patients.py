"""Patient mapping API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from vna_main.models.database import get_session
from vna_main.services.patient_service import PatientService
from vna_main.api.responses import PaginatedResponse
from vna_main.services.audit_service import AuditService

router = APIRouter(prefix="/patients", tags=["patients"])


class PatientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_ref: str | None = None
    hospital_id: str
    source: str
    external_system: str | None = None


class PatientUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hospital_id: str | None = None
    source: str | None = None
    external_system: str | None = None


def _serialize(p) -> dict:
    if isinstance(p, dict):
        return {
            "patient_ref": p["patient_ref"],
            "hospital_id": p["hospital_id"],
            "source": p["source"],
            "external_system": p.get("external_system"),
            "created_at": p.get("created_at"),
            "updated_at": p.get("updated_at"),
        }
    return {
        "patient_ref": p.patient_ref,
        "hospital_id": p.hospital_id,
        "source": p.source,
        "external_system": p.external_system,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _serialize_detail(p) -> dict:
    if isinstance(p, dict):
        return {
            "patient_ref": p["patient_ref"],
            "hospital_id": p["hospital_id"],
            "source": p["source"],
            "external_system": p.get("external_system"),
            "created_at": p.get("created_at"),
            "updated_at": p.get("updated_at"),
            "resources": p.get("resources", []),
        }
    data = _serialize(p)
    data["resources"] = [
        {
            "resource_id": r.resource_id,
            "source_type": r.source_type,
            "data_type": r.data_type,
            "file_name": r.file_name,
        }
        for r in (p.resources or [])
    ]
    return data


@router.get("", response_model=PaginatedResponse[dict])
async def list_patients(
    source: str | None = None,
    hospital_id: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    svc = PatientService(session)
    items, total = await svc.list_patients(
        source=source, hospital_id=hospital_id, offset=offset, limit=limit
    )
    return PaginatedResponse(
        items=[_serialize(p) for p in items],
        total=total,
        offset=offset,
        limit=limit
    )


@router.get("/{patient_ref}/resources")
async def get_patient_resources(
    patient_ref: str,
    session: AsyncSession = Depends(get_session),
):
    svc = PatientService(session)
    patient = await svc.get_patient(patient_ref)
    if patient is None:
        raise HTTPException(404, "Patient not found")
    if isinstance(patient, dict):
        return {
            "patient_ref": patient_ref,
            "total": len(patient.get("resources", [])),
            "items": patient.get("resources", []),
        }
    return {
        "patient_ref": patient_ref,
        "total": len(patient.resources or []),
        "items": [
            {
                "resource_id": r.resource_id,
                "patient_ref": r.patient_ref,
                "source_type": r.source_type,
                "data_type": r.data_type,
                "file_name": r.file_name,
                "dicom_study_uid": r.dicom_study_uid,
                "bids_subject_id": r.bids_subject_id,
            }
            for r in (patient.resources or [])
        ],
    }


@router.get("/{patient_ref}")
async def get_patient(
    patient_ref: str,
    session: AsyncSession = Depends(get_session),
):
    svc = PatientService(session)
    patient = await svc.get_patient(patient_ref)
    if patient is None:
        raise HTTPException(404, "Patient not found")
    return _serialize_detail(patient)


@router.post("", status_code=201)
async def create_patient(
    body: PatientCreate,
    session: AsyncSession = Depends(get_session),
):
    svc = PatientService(session)
    audit_svc = AuditService(session)
    patient = await svc.create_patient(body.model_dump(exclude_none=True))
    await session.commit()
    
    # Audit log
    await audit_svc.log(
        action="create",
        resource_type="patient",
        resource_id=patient.patient_ref,
        details={"hospital_id": patient.hospital_id, "source": patient.source}
    )
    
    return _serialize(patient)


@router.put("/{patient_ref}")
async def update_patient(
    patient_ref: str,
    body: PatientUpdate,
    session: AsyncSession = Depends(get_session),
):
    svc = PatientService(session)
    audit_svc = AuditService(session)
    patient = await svc.update_patient(patient_ref, body.model_dump(exclude_none=True))
    if patient is None:
        raise HTTPException(404, "Patient not found")
    await session.commit()
    
    # Audit log - handle both dict and object cases
    if isinstance(patient, dict):
        patient_id = patient["patient_ref"]
        hospital_id = patient["hospital_id"]
        source = patient["source"]
    else:
        patient_id = patient.patient_ref
        hospital_id = patient.hospital_id
        source = patient.source
    
    await audit_svc.log(
        action="update",
        resource_type="patient",
        resource_id=patient_id,
        details={"hospital_id": hospital_id, "source": source}
    )
    
    return _serialize(patient)


@router.delete("/{patient_ref}")
async def delete_patient(
    patient_ref: str,
    session: AsyncSession = Depends(get_session),
):
    svc = PatientService(session)
    audit_svc = AuditService(session)
    
    # Get patient info before deletion for audit
    patient = await svc.get_patient(patient_ref)
    if patient is None:
        raise HTTPException(404, "Patient not found")
    
    # Handle both dict and object cases
    if isinstance(patient, dict):
        patient_id = patient["patient_ref"]
        hospital_id = patient["hospital_id"]
        source = patient["source"]
    else:
        patient_id = patient.patient_ref
        hospital_id = patient.hospital_id
        source = patient.source
    
    ok = await svc.delete_patient(patient_ref)
    if not ok:
        raise HTTPException(404, "Patient not found")
    await session.commit()
    
    # Audit log
    await audit_svc.log(
        action="delete",
        resource_type="patient",
        resource_id=patient_id,
        details={"hospital_id": hospital_id, "source": source}
    )
    
    return {"deleted": patient_ref}
