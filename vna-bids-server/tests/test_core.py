"""Tests for core modules."""
import tempfile
from pathlib import Path

import pytest

from bids_server.core.bids_validator import (
    validate_subject_id,
    validate_session_id,
    validate_bids_path,
    guess_modality_from_path,
    guess_file_type,
)
from bids_server.core.stream import parse_range_header


class TestBidsValidator:
    def test_valid_subject_ids(self):
        assert validate_subject_id("sub-001")
        assert validate_subject_id("sub-ABC")
        assert validate_subject_id("sub-patient123")

    def test_invalid_subject_ids(self):
        assert not validate_subject_id("sub001")  # missing dash
        assert not validate_subject_id("subject-001")
        assert not validate_subject_id("")

    def test_valid_session_ids(self):
        assert validate_session_id("ses-001")
        assert validate_session_id("ses-baseline")

    def test_invalid_session_ids(self):
        assert not validate_session_id("session-001")
        assert not validate_session_id("ses001")

    def test_validate_bids_path_valid(self):
        valid, issues = validate_bids_path("sub-001/ses-001/anat/sub-001_ses-001_T1w.nii.gz")
        assert valid
        assert len(issues) == 0

    def test_validate_bids_path_invalid_subject(self):
        valid, issues = validate_bids_path("invalid/ses-001/anat/file.nii.gz")
        assert not valid

    def test_guess_modality(self):
        assert guess_modality_from_path("sub-001/ses-001/anat/T1w.nii.gz") == "anat"
        assert guess_modality_from_path("sub-001/ses-001/func/bold.nii.gz") == "func"
        assert guess_modality_from_path("sub-001/ses-001/dwi/dwi.nii.gz") == "dwi"

    def test_guess_file_type(self):
        assert guess_file_type("T1w.nii.gz") == "nifti"
        assert guess_file_type("data.json") == "json"
        assert guess_file_type("table.csv") == "csv"
        assert guess_file_type("report.pdf") == "pdf"
        assert guess_file_type("model.pth") == "pytorch"
        assert guess_file_type("unknown.xyz") == "unknown"


class TestStreamRangeParsing:
    def test_full_range(self):
        result = parse_range_header("bytes=0-99", 1000)
        assert result == (0, 99)

    def test_open_ended_range(self):
        result = parse_range_header("bytes=500-", 1000)
        assert result == (500, 999)

    def test_suffix_range(self):
        result = parse_range_header("bytes=-200", 1000)
        assert result == (800, 999)

    def test_no_range_header(self):
        assert parse_range_header(None, 1000) is None
        assert parse_range_header("", 1000) is None

    def test_range_clamped_to_file_size(self):
        result = parse_range_header("bytes=0-9999", 1000)
        assert result == (0, 999)
