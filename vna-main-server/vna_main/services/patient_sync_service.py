"""Patient auto-sync from DICOM (Orthanc) server."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from vna_main.config import settings
from vna_main.models.database import PatientMapping, ResourceIndex

logger = logging.getLogger(__name__)


class DicomPatientSync:
    def __init__(
        self,
        session: AsyncSession,
        dicom_url: str | None = None,
        dicom_user: str | None = None,
        dicom_pass: str | None = None,
    ):
        self.session = session
        self.dicom_url = dicom_url or settings.DICOM_SERVER_URL
        self.dicom_user = dicom_user or settings.DICOM_SERVER_USER
        self.dicom_pass = dicom_pass or settings.DICOM_SERVER_PASSWORD

    async def _get_dicom_patients(self, limit: int = 1000) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{self.dicom_url}/patients",
                    params={"expand": "true", "limit": limit},
                    auth=(self.dicom_user, self.dicom_pass) if self.dicom_user else None,
                )
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "patients" in data:
                    return data["patients"]
                return []
        except (httpx.HTTPError, httpx.TimeoutException, OSError) as e:
            logger.error("Failed to fetch patients from Orthanc: %s", e, exc_info=True)
            return []

    async def _get_dicom_patient_studies(self, patient_id: str) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{self.dicom_url}/patients/{patient_id}/studies",
                    params={"expand": "true"},
                    auth=(self.dicom_user, self.dicom_pass) if self.dicom_user else None,
                )
                resp.raise_for_status()
                data = resp.json()
                return data if isinstance(data, list) else []
        except (httpx.HTTPError, httpx.TimeoutException, OSError) as e:
            logger.error("Failed to fetch studies for patient %s: %s", patient_id, e, exc_info=True)
            return []

    async def sync_all_patients(
        self,
        *,
        hospital_id: str = "default",
        source: str = "dicom",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        dicom_patients = await self._get_dicom_patients()
        synced = 0
        skipped = 0
        errors = 0

        for dp in dicom_patients:
            try:
                patient_id = dp.get("ID") or dp.get("PatientID")
                if not patient_id:
                    errors += 1
                    continue

                patient_name = dp.get("PatientName", "")
                birth_date = dp.get("PatientBirthDate")
                sex = dp.get("PatientSex")

                stmt = select(PatientMapping).where(
                    PatientMapping.hospital_id == hospital_id,
                    PatientMapping.source == source,
                    PatientMapping.external_system == patient_id,
                )
                result = await self.session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    if patient_name and existing.patient_ref:
                        logger.debug("Patient %s already mapped as %s, skipping", patient_id, existing.patient_ref)
                    skipped += 1
                else:
                    new_patient = PatientMapping(
                        hospital_id=hospital_id,
                        source=source,
                        external_system=patient_id,
                    )
                    self.session.add(new_patient)
                    synced += 1

                    if not dry_run:
                        await self.session.flush()

                        study_count = 0
                        studies = await self._get_dicom_patient_studies(patient_id)
                        for study in studies:
                            study_uid = study.get("ID") or study.get("StudyInstanceUID")
                            if not study_uid:
                                continue
                            study_count += 1
                            resource = ResourceIndex(
                                patient_ref=new_patient.patient_ref,
                                source_type="dicom_only",
                                dicom_study_uid=study_uid,
                                data_type="dicom",
                                metadata_={
                                    "patient_name": patient_name,
                                    "patient_birth_date": birth_date,
                                    "patient_sex": sex,
                                    "study_date": study.get("StudyDate"),
                                    "study_description": study.get("StudyDescription"),
                                    "modality": study.get("ModalitiesInStudy", ""),
                                },
                            )
                            self.session.add(resource)

                        if study_count > 0:
                            await self.session.flush()

            except (httpx.HTTPError, SQLAlchemyError) as e:
                logger.error("Error syncing patient %s: %s", dp.get("ID"), e, exc_info=True)
                errors += 1

        if not dry_run:
            await self.session.flush()

        return {
            "total_dicom_patients": len(dicom_patients),
            "synced": synced,
            "skipped": skipped,
            "errors": errors,
        }

    async def sync_single_patient(
        self,
        dicom_patient_id: str,
        *,
        hospital_id: str = "default",
        source: str = "dicom",
    ) -> PatientMapping | None:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{self.dicom_url}/patients/{dicom_patient_id}",
                    params={"expand": "true"},
                    auth=(self.dicom_user, self.dicom_pass) if self.dicom_user else None,
                )
                resp.raise_for_status()
                dp = resp.json()
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.error("Failed to fetch patient %s from Orthanc: %s", dicom_patient_id, e, exc_info=True)
            return None

        stmt = select(PatientMapping).where(
            PatientMapping.hospital_id == hospital_id,
            PatientMapping.source == source,
            PatientMapping.external_system == dicom_patient_id,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        patient_name = dp.get("PatientName", "")
        birth_date = dp.get("PatientBirthDate")
        sex = dp.get("PatientSex")

        if existing:
            return existing

        new_patient = PatientMapping(
            hospital_id=hospital_id,
            source=source,
            external_system=dicom_patient_id,
        )
        self.session.add(new_patient)
        await self.session.flush()

        studies = await self._get_dicom_patient_studies(dicom_patient_id)
        for study in studies:
            study_uid = study.get("ID") or study.get("StudyInstanceUID")
            if not study_uid:
                continue
            resource = ResourceIndex(
                patient_ref=new_patient.patient_ref,
                source_type="dicom_only",
                dicom_study_uid=study_uid,
                data_type="dicom",
                metadata_={
                    "patient_name": patient_name,
                    "patient_birth_date": birth_date,
                    "patient_sex": sex,
                    "study_date": study.get("StudyDate"),
                    "study_description": study.get("StudyDescription"),
                    "modality": study.get("ModalitiesInStudy", ""),
                },
            )
            self.session.add(resource)

        await self.session.flush()
        return new_patient


class PatientSyncService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def sync_from_dicom(
        self,
        *,
        hospital_id: str = "default",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        syncer = DicomPatientSync(self.session, dicom_url=settings.DICOM_SERVER_URL)
        return await syncer.sync_all_patients(
            hospital_id=hospital_id,
            source="dicom",
            dry_run=dry_run,
        )

    async def get_sync_status(self) -> dict[str, Any]:
        total_patients = (await self.session.execute(
            select(func.count()).select_from(PatientMapping)
        )).scalar() or 0

        dicom_patients = (await self.session.execute(
            select(func.count()).select_from(PatientMapping).where(
                PatientMapping.source == "dicom"
            )
        )).scalar() or 0

        bids_patients = (await self.session.execute(
            select(func.count()).select_from(PatientMapping).where(
                PatientMapping.source == "bids"
            )
        )).scalar() or 0

        mapped_resources = (await self.session.execute(
            select(func.count()).select_from(ResourceIndex).where(
                ResourceIndex.patient_ref.isnot(None)
            )
        )).scalar() or 0

        total_resources = (await self.session.execute(
            select(func.count()).select_from(ResourceIndex)
        )).scalar() or 0

        return {
            "total_patients": total_patients,
            "dicom_patients": dicom_patients,
            "bids_patients": bids_patients,
            "mapped_resources": mapped_resources,
            "unmapped_resources": total_resources - mapped_resources,
            "total_resources": total_resources,
        }
