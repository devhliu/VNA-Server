"""Advanced BIDS validation service."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    code: str
    message: str
    severity: ValidationSeverity
    location: str | None = None
    suggestion: str | None = None


@dataclass
class ValidationResult:
    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    warnings: int = 0
    errors: int = 0

    def add_issue(self, issue: ValidationIssue):
        self.issues.append(issue)
        if issue.severity == ValidationSeverity.ERROR:
            self.errors += 1
            self.is_valid = False
        elif issue.severity == ValidationSeverity.WARNING:
            self.warnings += 1


BIDS_REQUIRED_FILES = {
    "dataset_description.json": "Root level dataset description",
}

BIDS_RECOMMENDED_FILES = {
    "participants.tsv": "Participant information",
    "participants.json": "Participant metadata",
    "README": "Dataset documentation",
    "CHANGES": "Version history",
}

VALID_ENTITIES = {
    "sub", "ses", "task", "acq", "ce", "rec", "dir", "run", "mod",
    "echo", "flip", "inv", "mt", "part", "recording", "res", "proc",
    "space", "suffix", "split", "chunk", "atlas", "label", "desc",
    "from", "to", "mode", "seg", "model", "subset", "tracksys",
    "sampling", "casing", "coord", "den", "fmap", "hemi", "space",
    "view", "scans", "sessions", "electrodes", "channels", "coordsystem",
    "photo", "tmp", "trace", "stim",
}

MODALITY_REQUIRED_ENTITIES = {
    "func": ["task"],
    "dwi": [],
    "fmap": [],
    "eeg": [],
    "meg": [],
    "ieeg": [],
    "pet": ["trc"],
    "ct": [],
    "anat": [],
    "beh": [],
    "microscopy": [],
    "motion": [],
    "nirs": [],
}

MODALITY_FILE_EXTENSIONS = {
    "anat": {".nii", ".nii.gz", ".json"},
    "func": {".nii", ".nii.gz", ".json", ".tsv", ".tsv.gz"},
    "dwi": {".nii", ".nii.gz", ".json", ".bval", ".bvec"},
    "fmap": {".nii", ".nii.gz", ".json"},
    "eeg": {".edf", ".vhdr", ".vmrk", ".eeg", ".set", ".fdt", ".json", ".tsv"},
    "meg": {".fif", ".ds", ".json", ".tsv"},
    "ieeg": {".edf", ".vhdr", ".vmrk", ".eeg", ".mef", ".nwb", ".json", ".tsv"},
    "pet": {".nii", ".nii.gz", ".json"},
    "ct": {".nii", ".nii.gz", ".json"},
    "microscopy": {".tif", ".tiff", ".png", ".jpg", ".json", ".tsv"},
    "beh": {".tsv", ".json", ".csv"},
    "motion": {".tsv", ".json", ".c3d"},
    "nirs": {".tsv", ".json", ".snirf"},
}

ENTITY_PATTERN = re.compile(r"^([a-zA-Z]+)-([a-zA-Z0-9]+)$")


class AdvancedBIDSValidator:
    """Advanced BIDS validation with comprehensive rule checking."""

    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
        self._dataset_files: dict[str, bytes] = {}

    def set_dataset_files(self, files: dict[str, bytes]):
        self._dataset_files = files

    def validate_dataset(self, files: dict[str, bytes] | None = None) -> ValidationResult:
        if files:
            self.set_dataset_files(files)

        result = ValidationResult(is_valid=True)

        self._validate_required_files(result)
        self._validate_recommended_files(result)
        self._validate_file_naming(result)
        self._validate_entity_consistency(result)
        self._validate_json_sidecars(result)
        self._validate_modality_specific(result)

        return result

    def validate_file(self, filepath: str, content: bytes | None = None) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        self._validate_single_file(filepath, content, result)

        return result

    def _validate_required_files(self, result: ValidationResult):
        for filename, description in BIDS_REQUIRED_FILES.items():
            found = any(
                fp == filename or fp.endswith(f"/{filename}")
                for fp in self._dataset_files.keys()
            )
            if not found:
                result.add_issue(ValidationIssue(
                    code="MISSING_REQUIRED_FILE",
                    message=f"Missing required file: {filename} ({description})",
                    severity=ValidationSeverity.ERROR,
                    location=filename,
                    suggestion=f"Create {filename} at the dataset root",
                ))

    def _validate_recommended_files(self, result: ValidationResult):
        for filename, description in BIDS_RECOMMENDED_FILES.items():
            found = any(
                fp == filename or fp.endswith(f"/{filename}")
                for fp in self._dataset_files.keys()
            )
            if not found:
                result.add_issue(ValidationIssue(
                    code="MISSING_RECOMMENDED_FILE",
                    message=f"Missing recommended file: {filename} ({description})",
                    severity=ValidationSeverity.WARNING,
                    location=filename,
                    suggestion=f"Consider adding {filename}",
                ))

    def _validate_file_naming(self, result: ValidationResult):
        for filepath in self._dataset_files.keys():
            filename = Path(filepath).name

            if filename.startswith("."):
                continue

            if filename in BIDS_REQUIRED_FILES or filename in BIDS_RECOMMENDED_FILES:
                continue

            if not self._is_valid_bids_filename(filename):
                result.add_issue(ValidationIssue(
                    code="INVALID_FILENAME",
                    message=f"Invalid BIDS filename: {filename}",
                    severity=ValidationSeverity.ERROR if self.strict_mode else ValidationSeverity.WARNING,
                    location=filepath,
                    suggestion="Follow BIDS naming convention: sub-<label>[_ses-<label>]_key-value_suffix.ext",
                ))

    def _validate_entity_consistency(self, result: ValidationResult):
        subjects = set()
        sessions = set()

        for filepath in self._dataset_files.keys():
            parts = Path(filepath).parts

            for part in parts:
                if part.startswith("sub-"):
                    subjects.add(part)
                elif part.startswith("ses-"):
                    sessions.add(part)

                for entity_str in part.split("_"):
                    if "-" in entity_str:
                        match = ENTITY_PATTERN.match(entity_str)
                        if match:
                            entity_name = match.group(1)
                            if entity_name not in VALID_ENTITIES:
                                result.add_issue(ValidationIssue(
                                    code="UNKNOWN_ENTITY",
                                    message=f"Unknown entity: {entity_name}",
                                    severity=ValidationSeverity.WARNING,
                                    location=filepath,
                                    suggestion=f"Check if '{entity_name}' is a valid BIDS entity",
                                ))

    def _validate_json_sidecars(self, result: ValidationResult):
        for filepath, content in self._dataset_files.items():
            if not filepath.endswith(".json"):
                continue

            try:
                data = json.loads(content)
                self._validate_json_content(filepath, data, result)
            except json.JSONDecodeError as e:
                result.add_issue(ValidationIssue(
                    code="INVALID_JSON",
                    message=f"Invalid JSON in {filepath}: {e}",
                    severity=ValidationSeverity.ERROR,
                    location=filepath,
                    suggestion="Fix JSON syntax errors",
                ))

    def _validate_json_content(self, filepath: str, data: dict, result: ValidationResult):
        if filepath.endswith("dataset_description.json"):
            required_keys = ["Name", "BIDSVersion"]
            for key in required_keys:
                if key not in data:
                    result.add_issue(ValidationIssue(
                        code="MISSING_JSON_FIELD",
                        message=f"Missing required field '{key}' in dataset_description.json",
                        severity=ValidationSeverity.ERROR,
                        location=filepath,
                        suggestion=f"Add '{key}' field to dataset_description.json",
                    ))

    def _validate_modality_specific(self, result: ValidationResult):
        modality_files: dict[str, list[str]] = {}

        for filepath in self._dataset_files.keys():
            parts = Path(filepath).parts
            for part in parts:
                if part in MODALITY_REQUIRED_ENTITIES:
                    modality_files.setdefault(part, []).append(filepath)
                    break

        for modality, files in modality_files.items():
            required_entities = MODALITY_REQUIRED_ENTITIES.get(modality, [])
            valid_extensions = MODALITY_FILE_EXTENSIONS.get(modality, set())

            for filepath in files:
                filename = Path(filepath).name

                for entity in required_entities:
                    if f"_{entity}-" not in filename:
                        result.add_issue(ValidationIssue(
                            code="MISSING_REQUIRED_ENTITY",
                            message=f"Missing required entity '{entity}' for {modality} file",
                            severity=ValidationSeverity.ERROR,
                            location=filepath,
                            suggestion=f"Add {entity}-<label> to filename",
                        ))

                ext = "".join(Path(filename).suffixes)
                if ext and valid_extensions and ext not in valid_extensions:
                    result.add_issue(ValidationIssue(
                        code="INVALID_EXTENSION",
                        message=f"Unexpected extension '{ext}' for {modality} file",
                        severity=ValidationSeverity.WARNING,
                        location=filepath,
                        suggestion=f"Expected one of: {', '.join(valid_extensions)}",
                    ))

    def _validate_single_file(self, filepath: str, content: bytes | None, result: ValidationResult):
        filename = Path(filepath).name

        if not self._is_valid_bids_filename(filename):
            if not filename.startswith(".") and filename not in BIDS_REQUIRED_FILES:
                result.add_issue(ValidationIssue(
                    code="INVALID_FILENAME",
                    message=f"Invalid BIDS filename: {filename}",
                    severity=ValidationSeverity.ERROR if self.strict_mode else ValidationSeverity.WARNING,
                    location=filepath,
                ))

        if filepath.endswith(".json") and content:
            try:
                json.loads(content)
            except json.JSONDecodeError as e:
                result.add_issue(ValidationIssue(
                    code="INVALID_JSON",
                    message=f"Invalid JSON: {e}",
                    severity=ValidationSeverity.ERROR,
                    location=filepath,
                ))

    def _is_valid_bids_filename(self, filename: str) -> bool:
        if filename.startswith("."):
            return True

        if filename in BIDS_REQUIRED_FILES or filename in BIDS_RECOMMENDED_FILES:
            return True

        if not filename.startswith("sub-"):
            return False

        parts = filename.split("_")
        if len(parts) < 2:
            return False

        if not parts[0].startswith("sub-"):
            return False

        for part in parts[:-1]:
            if "-" not in part:
                return False
            entity, value = part.split("-", 1)
            if not entity or not value:
                return False

        last_part = parts[-1]
        if "." in last_part:
            name_part = last_part.rsplit(".", 1)[0]
        else:
            name_part = last_part

        if "-" in name_part and not name_part.split("-")[0] in VALID_ENTITIES:
            return False

        return True


def validate_bids_dataset(files: dict[str, bytes], strict: bool = False) -> dict[str, Any]:
    validator = AdvancedBIDSValidator(strict_mode=strict)
    result = validator.validate_dataset(files)

    return {
        "is_valid": result.is_valid,
        "errors": result.errors,
        "warnings": result.warnings,
        "issues": [
            {
                "code": i.code,
                "message": i.message,
                "severity": i.severity.value,
                "location": i.location,
                "suggestion": i.suggestion,
            }
            for i in result.issues
        ],
    }


def validate_bids_file(filepath: str, content: bytes | None = None, strict: bool = False) -> dict[str, Any]:
    validator = AdvancedBIDSValidator(strict_mode=strict)
    result = validator.validate_file(filepath, content)

    return {
        "is_valid": result.is_valid,
        "errors": result.errors,
        "warnings": result.warnings,
        "issues": [
            {
                "code": i.code,
                "message": i.message,
                "severity": i.severity.value,
                "location": i.location,
                "suggestion": i.suggestion,
            }
            for i in result.issues
        ],
    }
