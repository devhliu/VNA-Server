#!/usr/bin/env python3
"""Test script to verify PostgreSQL integration with Orthanc DICOM server."""

import httpx
import os
import sys
import time

ORTHANC_URL = os.environ.get("ORTHANC_URL", "http://localhost:8042")
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "orthanc")


def wait_for_orthanc(timeout: float = 60.0) -> bool:
    """Wait for Orthanc to be ready."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{ORTHANC_URL}/system", timeout=5.0)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def test_orthanc_system():
    """Test Orthanc system endpoint."""
    resp = httpx.get(f"{ORTHANC_URL}/system", timeout=10.0)
    assert resp.status_code == 200, f"System endpoint failed: {resp.status_code}"
    data = resp.json()
    print(f"✓ Orthanc version: {data.get('Version')}")
    print(f"✓ Database: {data.get('Database')}")
    return data


def test_orthanc_statistics():
    """Test Orthanc statistics endpoint."""
    resp = httpx.get(f"{ORTHANC_URL}/statistics", timeout=10.0)
    assert resp.status_code == 200, f"Statistics endpoint failed: {resp.status_code}"
    data = resp.json()
    print(f"✓ Studies: {data.get('CountStudies', 0)}")
    print(f"✓ Series: {data.get('CountSeries', 0)}")
    print(f"✓ Instances: {data.get('CountInstances', 0)}")
    return data


def test_orthanc_patients():
    """Test Orthanc patients endpoint."""
    resp = httpx.get(f"{ORTHANC_URL}/patients", timeout=10.0)
    assert resp.status_code == 200, f"Patients endpoint failed: {resp.status_code}"
    patients = resp.json()
    print(f"✓ Patients count: {len(patients)}")
    return patients


def test_orthanc_studies():
    """Test Orthanc studies endpoint."""
    resp = httpx.get(f"{ORTHANC_URL}/studies", timeout=10.0)
    assert resp.status_code == 200, f"Studies endpoint failed: {resp.status_code}"
    studies = resp.json()
    print(f"✓ Studies count: {len(studies)}")
    return studies


def test_dicom_web():
    """Test DICOMweb endpoint."""
    resp = httpx.get(f"{ORTHANC_URL}/dicom-web/studies", timeout=10.0)
    assert resp.status_code == 200, f"DICOMweb endpoint failed: {resp.status_code}"
    print("✓ DICOMweb enabled and accessible")
    return True


def test_postgres_connection():
    """Test PostgreSQL connection directly."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB,
        )
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM pg_tables WHERE schemaname = 'public';")
        table_count = cur.fetchone()[0]
        print(f"✓ PostgreSQL connected, tables in 'public': {table_count}")
        cur.close()
        conn.close()
        return True
    except ImportError:
        print("⚠ psycopg2 not installed, skipping direct PostgreSQL test")
        return True
    except Exception as e:
        print(f"✗ PostgreSQL connection failed: {e}")
        return False


def main():
    print("=" * 60)
    print("VNA DICOM Server PostgreSQL Integration Test")
    print("=" * 60)
    print()

    print("Waiting for Orthanc to be ready...")
    if not wait_for_orthanc():
        print("✗ Orthanc not available after timeout")
        sys.exit(1)
    print("✓ Orthanc is ready")
    print()

    all_passed = True

    try:
        print("Testing Orthanc system...")
        system = test_orthanc_system()
        if system.get("Database") != "PostgreSQL":
            print(f"⚠ Database is not PostgreSQL: {system.get('Database')}")
        else:
            print("✓ Database backend: PostgreSQL")
    except Exception as e:
        print(f"✗ System test failed: {e}")
        all_passed = False

    print()

    try:
        print("Testing Orthanc statistics...")
        test_orthanc_statistics()
    except Exception as e:
        print(f"✗ Statistics test failed: {e}")
        all_passed = False

    print()

    try:
        print("Testing Orthanc patients...")
        test_orthanc_patients()
    except Exception as e:
        print(f"✗ Patients test failed: {e}")
        all_passed = False

    print()

    try:
        print("Testing Orthanc studies...")
        test_orthanc_studies()
    except Exception as e:
        print(f"✗ Studies test failed: {e}")
        all_passed = False

    print()

    try:
        print("Testing DICOMweb...")
        test_dicom_web()
    except Exception as e:
        print(f"✗ DICOMweb test failed: {e}")
        all_passed = False

    print()

    try:
        print("Testing PostgreSQL connection...")
        if not test_postgres_connection():
            all_passed = False
    except Exception as e:
        print(f"✗ PostgreSQL test failed: {e}")
        all_passed = False

    print()
    print("=" * 60)
    if all_passed:
        print("✓ All tests passed!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("✗ Some tests failed")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
