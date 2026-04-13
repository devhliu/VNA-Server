"""Lightweight BIDS structure validator."""
import re
from pathlib import Path
from typing import Optional

# BIDS naming pattern: sub-{id}[_ses-{id}]_{suffix}[.{ext}]
BIDS_SUBJECT_PATTERN = re.compile(r"^sub-[a-zA-Z0-9]+$")
BIDS_SESSION_PATTERN = re.compile(r"^ses-[a-zA-Z0-9]+$")
BIDS_FILE_PATTERN = re.compile(
    r"^sub-[a-zA-Z0-9]+"
    r"(_ses-[a-zA-Z0-9]+)?"
    r"(_[a-zA-Z0-9]+)*"  # key-value pairs like task-rest
    r"_[a-zA-Z0-9]+"     # suffix like T1w, bold, dwi
    r"(\..+)?$"           # optional extension
)

# Valid top-level BIDS directories
VALID_MODALITIES = {
    "anat", "func", "dwi", "fmap", "eeg", "meg", "ieeg", "nirs",
    "pet", "ct", "microscopy", "beh", "motion",
    "docs", "tables", "code", "models", "raw", "other",
    "sourcedata", "derivatives",
}


def validate_subject_id(subject_id: str) -> bool:
    """Validate subject ID format: sub-xxx"""
    return bool(BIDS_SUBJECT_PATTERN.match(subject_id))


def validate_session_id(session_id: str) -> bool:
    """Validate session ID format: ses-xxx"""
    return bool(BIDS_SESSION_PATTERN.match(session_id))


def validate_bids_filename(filename: str) -> bool:
    """Validate BIDS filename pattern."""
    # Sidecar JSON and metadata files are valid
    if filename.endswith(".json") or filename.endswith(".tsv"):
        return True
    # Check BIDS pattern
    return bool(BIDS_FILE_PATTERN.match(filename))


def validate_bids_path(bids_path: str) -> tuple[bool, list[str]]:
    """
    Validate a full BIDS path structure.
    Returns (is_valid, list_of_issues).
    """
    issues = []
    parts = Path(bids_path).parts

    if len(parts) == 0:
        return False, ["Empty path"]

    # First part must be subject directory
    if not validate_subject_id(parts[0]):
        issues.append(f"Invalid subject directory: {parts[0]}")

    if len(parts) == 1:
        # Just subject dir, could be valid (e.g., sub-001.json at root)
        return len(issues) == 0, issues

    idx = 1
    # Second part could be session directory or JSON at subject level
    if parts[1].endswith(".json"):
        return len(issues) == 0, issues

    if validate_session_id(parts[1]):
        idx = 2
    elif parts[1] not in VALID_MODALITIES and not parts[1].endswith(".json"):
        issues.append(f"Invalid session or modality directory: {parts[1]}")

    if len(parts) > idx:
        # Should be modality directory or file
        modality = parts[idx]
        if modality not in VALID_MODALITIES and not modality.endswith(".json"):
            issues.append(f"Unknown modality directory: {modality}")

    return len(issues) == 0, issues


def guess_modality_from_path(bids_path: str) -> Optional[str]:
    """Guess modality from BIDS path."""
    parts = Path(bids_path).parts
    for part in parts:
        if part in VALID_MODALITIES:
            return part
    return "other"


def guess_file_type(filename: str) -> str:
    """Guess file type from extension."""
    name = filename.lower()
    if name.endswith(".nii.gz"):
        return "nifti"
    elif name.endswith(".nii"):
        return "nifti"
    elif name.endswith(".json"):
        return "json"
    elif name.endswith(".tsv"):
        return "tsv"
    elif name.endswith(".csv"):
        return "csv"
    elif name.endswith(".pdf"):
        return "pdf"
    elif name.endswith(".bval"):
        return "bval"
    elif name.endswith(".bvec"):
        return "bvec"
    elif name.endswith(".edf"):
        return "edf"
    elif name.endswith(".fif"):
        return "fif"
    elif name.endswith(".tiff") or name.endswith(".tif"):
        return "tiff"
    elif name.endswith(".xlsx") or name.endswith(".xls"):
        return "excel"
    elif name.endswith(".docx") or name.endswith(".doc"):
        return "word"
    elif name.endswith(".py"):
        return "python"
    elif name.endswith(".sh"):
        return "shell"
    elif name.endswith(".ipynb"):
        return "notebook"
    elif name.endswith(".pth") or name.endswith(".pt"):
        return "pytorch"
    elif name.endswith(".h5"):
        return "hdf5"
    elif name.endswith(".onnx"):
        return "onnx"
    else:
        return "unknown"
