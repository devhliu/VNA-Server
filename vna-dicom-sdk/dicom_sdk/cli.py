"""Command-line interface for the DICOM SDK."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import click

from dicom_sdk import DicomClient, __version__
from dicom_sdk.exceptions import DicomError

logger = logging.getLogger(__name__)


def _get_client(server: str, username: str | None, password: str | None) -> DicomClient:
    """Create a DicomClient from CLI options."""
    return DicomClient(base_url=server, username=username, password=password)


def _output(data: Any, json_output: bool, verbose: bool) -> None:
    """Print output in the requested format."""
    if json_output:
        if hasattr(data, "model_dump"):
            click.echo(json.dumps(data.model_dump(exclude_none=True), indent=2))
        elif isinstance(data, list):
            items = [item.model_dump(exclude_none=True) if hasattr(item, "model_dump") else item for item in data]
            click.echo(json.dumps(items, indent=2))
        else:
            click.echo(json.dumps(data, indent=2))
    elif hasattr(data, "model_dump"):
        d = data.model_dump(exclude_none=True)
        for key, value in d.items():
            click.echo(f"  {key}: {value}")
    elif isinstance(data, list):
        for item in data:
            if hasattr(item, "model_dump"):
                d = item.model_dump(exclude_none=True)
                click.echo("  ---")
                for key, value in d.items():
                    click.echo(f"    {key}: {value}")
            else:
                click.echo(f"  {item}")
    else:
        click.echo(str(data))


@click.group()
@click.version_option(version=__version__, prog_name="dicom-cli")
def cli() -> None:
    """DICOM Server CLI - Interact with Orthanc-compatible DICOMweb servers."""
    logger.debug("dicom-cli command group invoked")


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--server", "-s", required=True, help="DICOM server URL")
@click.option("--username", "-u", default=None, help="Username for authentication")
@click.option("--password", "-p", default=None, help="Password for authentication")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def store(
    file_path: str,
    server: str,
    username: str | None,
    password: str | None,
    json_output: bool,
    verbose: bool,
) -> None:
    """Store a DICOM file on the server."""
    try:
        with _get_client(server, username, password) as client:
            result = client.store(file_path)
            _output(result, json_output, verbose)
    except DicomError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--server", "-s", required=True, help="DICOM server URL")
@click.option("--username", "-u", default=None, help="Username for authentication")
@click.option("--password", "-p", default=None, help="Password for authentication")
@click.option("--patient-id", default=None, help="Filter by Patient ID")
@click.option("--patient-name", default=None, help="Filter by Patient Name")
@click.option("--study-uid", default=None, help="Filter by Study Instance UID")
@click.option("--study-date", default=None, help="Filter by Study Date (YYYYMMDD)")
@click.option("--modality", "-m", default=None, help="Filter by Modality")
@click.option("--accession", default=None, help="Filter by Accession Number")
@click.option("--limit", default=100, help="Maximum results")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def query(
    server: str,
    username: str | None,
    password: str | None,
    patient_id: str | None,
    patient_name: str | None,
    study_uid: str | None,
    study_date: str | None,
    modality: str | None,
    accession: str | None,
    limit: int,
    json_output: bool,
    verbose: bool,
) -> None:
    """Query studies on the server."""
    try:
        with _get_client(server, username, password) as client:
            results = client.query(
                study_uid=study_uid,
                patient_id=patient_id,
                patient_name=patient_name,
                study_date=study_date,
                modality=modality,
                accession_number=accession,
                limit=limit,
            )
            if json_output:
                items = [r.model_dump(exclude_none=True) for r in results]
                click.echo(json.dumps(items, indent=2))
            elif results:
                for r in results:
                    click.echo("  ---")
                    for key, value in r.model_dump(exclude_none=True).items():
                        click.echo(f"    {key}: {value}")
            else:
                click.echo("No results found.")
    except DicomError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("study_uid")
@click.option("--server", "-s", required=True, help="DICOM server URL")
@click.option("--username", "-u", default=None, help="Username for authentication")
@click.option("--password", "-p", default=None, help="Password for authentication")
@click.option("--series-uid", default=None, help="Series Instance UID")
@click.option("--instance-uid", default=None, help="SOP Instance UID")
@click.option("--output", "-o", default="./downloaded_dicom", help="Output directory")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def retrieve(
    study_uid: str,
    server: str,
    username: str | None,
    password: str | None,
    series_uid: str | None,
    instance_uid: str | None,
    output: str,
    verbose: bool,
) -> None:
    """Retrieve DICOM files from the server."""
    try:
        with _get_client(server, username, password) as client:
            files = client.retrieve(
                study_uid,
                series_uid=series_uid,
                instance_uid=instance_uid,
                output_dir=output,
            )
            click.echo(f"Retrieved {len(files)} file(s) to {output}")
            if verbose:
                for i, f in enumerate(files):
                    click.echo(f"  dicom_{i:04d}.dcm: {len(f)} bytes")
    except DicomError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("study_uid")
@click.option("--server", "-s", required=True, help="DICOM server URL")
@click.option("--username", "-u", default=None, help="Username for authentication")
@click.option("--password", "-p", default=None, help="Password for authentication")
@click.option("--series-uid", default=None, help="Series Instance UID to delete")
@click.option("--instance-uid", default=None, help="SOP Instance UID to delete")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def delete(
    study_uid: str,
    server: str,
    username: str | None,
    password: str | None,
    series_uid: str | None,
    instance_uid: str | None,
    yes: bool,
) -> None:
    """Delete a study, series, or instance from the server."""
    target = instance_uid or series_uid or study_uid
    label = "instance" if instance_uid else ("series" if series_uid else "study")
    if not yes:
        click.confirm(f"Delete {label} {target}?", abort=True)
    try:
        with _get_client(server, username, password) as client:
            client.delete(study_uid, series_uid=series_uid, instance_uid=instance_uid)
            click.echo(f"Deleted {label} successfully.")
    except DicomError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command("info")
@click.argument("study_uid")
@click.option("--server", "-s", required=True, help="DICOM server URL")
@click.option("--username", "-u", default=None, help="Username for authentication")
@click.option("--password", "-p", default=None, help="Password for authentication")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def info(
    study_uid: str,
    server: str,
    username: str | None,
    password: str | None,
    json_output: bool,
    verbose: bool,
) -> None:
    """Get detailed information about a study."""
    try:
        with _get_client(server, username, password) as client:
            metadata = client.get_study(study_uid)
            _output(metadata, json_output, verbose)
    except DicomError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command("stats")
@click.option("--server", "-s", required=True, help="DICOM server URL")
@click.option("--username", "-u", default=None, help="Username for authentication")
@click.option("--password", "-p", default=None, help="Password for authentication")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def stats(
    server: str,
    username: str | None,
    password: str | None,
    json_output: bool,
    verbose: bool,
) -> None:
    """Get server statistics."""
    try:
        with _get_client(server, username, password) as client:
            statistics = client.get_statistics()
            _output(statistics, json_output, verbose)
    except DicomError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("study_uid")
@click.argument("series_uid")
@click.argument("instance_uid")
@click.option("--server", "-s", required=True, help="DICOM server URL")
@click.option("--username", "-u", default=None, help="Username for authentication")
@click.option("--password", "-p", default=None, help="Password for authentication")
@click.option("--output", "-o", required=True, help="Output file path")
@click.option("--format", "fmt", default="png", type=click.Choice(["png", "jpeg"]), help="Image format")
def render(
    study_uid: str,
    series_uid: str,
    instance_uid: str,
    server: str,
    username: str | None,
    password: str | None,
    output: str,
    fmt: str,
) -> None:
    """Render a DICOM instance as an image."""
    try:
        with _get_client(server, username, password) as client:
            client.render(study_uid, series_uid, instance_uid, output_format=fmt, output_path=output)
            click.echo(f"Rendered image saved to {output}")
    except DicomError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command("modalities")
@click.option("--server", "-s", required=True, help="DICOM server URL")
@click.option("--username", "-u", default=None, help="Username for authentication")
@click.option("--password", "-p", default=None, help="Password for authentication")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def modalities(
    server: str,
    username: str | None,
    password: str | None,
    json_output: bool,
    verbose: bool,
) -> None:
    """List configured DICOM modalities."""
    try:
        with _get_client(server, username, password) as client:
            mods = client.list_modalities()
            _output(mods, json_output, verbose)
    except DicomError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
