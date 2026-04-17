"""Command-line interface for the BIDS Server SDK."""

import json
import logging
import sys
from typing import Any, Optional

import click

from bids_sdk.client import BidsClient
from bids_sdk.exceptions import BidsError

logger = logging.getLogger(__name__)


def _get_client(server: str, api_key: Optional[str] = None, timeout: float = 30.0) -> BidsClient:
    """Create a BidsClient from CLI arguments."""
    return BidsClient(base_url=server, api_key=api_key, timeout=timeout)


def _output(data: Any, json_output: bool, verbose: bool) -> None:
    """Output data as JSON or human-readable."""
    if json_output:
        if hasattr(data, "model_dump"):
            click.echo(json.dumps(data.model_dump(exclude_none=True, by_alias=True), indent=2, default=str))
        elif isinstance(data, list):
            result = []
            for item in data:
                if hasattr(item, "model_dump"):
                    result.append(item.model_dump(exclude_none=True, by_alias=True))
                else:
                    result.append(item)
            click.echo(json.dumps(result, indent=2, default=str))
        else:
            click.echo(json.dumps(data, indent=2, default=str))
    else:
        if hasattr(data, "model_dump"):
            d = data.model_dump(exclude_none=True, by_alias=True)
            for k, v in d.items():
                click.echo(f"  {k}: {v}")
        elif isinstance(data, list):
            if not data:
                click.echo("  (no results)")
            for item in data:
                if hasattr(item, "model_dump"):
                    d = item.model_dump(exclude_none=True, by_alias=True)
                    items = " | ".join(f"{k}={v}" for k, v in d.items())
                    click.echo(f"  - {items}")
                else:
                    click.echo(f"  - {item}")
        else:
            click.echo(str(data))


@click.group()
@click.version_option("0.1.0", prog_name="bids-cli")
def cli() -> None:
    """BIDS Server CLI - Manage BIDSweb resources from the command line."""
    logger.debug("bids-cli command group invoked")


# ------------------------------------------------------------------
# Upload
# ------------------------------------------------------------------
@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--subject", "subject_id", required=True, help="Subject ID")
@click.option("--session", "session_id", default=None, help="Session ID")
@click.option("--modality", required=True, help="Modality (e.g., anat, func, dwi)")
@click.option("--server", required=True, help="BIDS server URL")
@click.option("--api-key", default=None, help="API key for authentication")
@click.option("--labels", default=None, help="Comma-separated labels")
@click.option("--metadata", default=None, help="JSON metadata string")
@click.option("--chunked", is_flag=True, help="Use chunked upload")
@click.option("--chunk-size", default=5 * 1024 * 1024, help="Chunk size in bytes")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def upload(
    file: str,
    subject_id: str,
    session_id: Optional[str],
    modality: str,
    server: str,
    api_key: Optional[str],
    labels: Optional[str],
    metadata: Optional[str],
    chunked: bool,
    chunk_size: int,
    json_output: bool,
    verbose: bool,
) -> None:
    """Upload a file to the BIDS server."""
    label_list = labels.split(",") if labels else None
    meta_dict = json.loads(metadata) if metadata else None

    with _get_client(server, api_key) as client:
        try:
            if chunked:
                result = client.upload_chunked(
                    file, subject_id, session_id, modality,
                    chunk_size=chunk_size, labels=label_list, metadata=meta_dict,
                )
            else:
                result = client.upload(
                    file, subject_id, session_id, modality,
                    labels=label_list, metadata=meta_dict,
                )
            if verbose:
                click.echo("Upload successful!")
            _output(result, json_output, verbose)
        except BidsError as e:
            click.echo(f"Error: {e.message}", err=True)
            sys.exit(1)


# ------------------------------------------------------------------
# Download
# ------------------------------------------------------------------
@cli.command()
@click.argument("resource_id")
@click.option("--output", "output_path", required=True, help="Output file path")
@click.option("--server", required=True, help="BIDS server URL")
@click.option("--api-key", default=None, help="API key")
@click.option("--range-start", type=int, default=None, help="Range start byte")
@click.option("--range-end", type=int, default=None, help="Range end byte")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def download(
    resource_id: str,
    output_path: str,
    server: str,
    api_key: Optional[str],
    range_start: Optional[int],
    range_end: Optional[int],
    json_output: bool,
    verbose: bool,
) -> None:
    """Download a file from the BIDS server."""
    with _get_client(server, api_key) as client:
        try:
            if range_start is not None or range_end is not None:
                result = client.download_stream(resource_id, output_path, range_start, range_end)
            else:
                result = client.download(resource_id, output_path)
            if verbose:
                click.echo(f"Downloaded to: {result}")
            if json_output:
                click.echo(json.dumps({"path": str(result)}, indent=2))
        except BidsError as e:
            click.echo(f"Error: {e.message}", err=True)
            sys.exit(1)


# ------------------------------------------------------------------
# Query
# ------------------------------------------------------------------
@cli.command()
@click.option("--server", required=True, help="BIDS server URL")
@click.option("--api-key", default=None, help="API key")
@click.option("--subject", "subject_id", default=None, help="Filter by subject ID")
@click.option("--session", "session_id", default=None, help="Filter by session ID")
@click.option("--modality", default=None, help="Filter by modality")
@click.option("--labels", default=None, help="Comma-separated labels to filter")
@click.option("--search", default=None, help="Search query")
@click.option("--limit", type=int, default=None, help="Max results")
@click.option("--offset", type=int, default=None, help="Pagination offset")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def query(
    server: str,
    api_key: Optional[str],
    subject_id: Optional[str],
    session_id: Optional[str],
    modality: Optional[str],
    labels: Optional[str],
    search: Optional[str],
    limit: Optional[int],
    offset: Optional[int],
    json_output: bool,
    verbose: bool,
) -> None:
    """Query resources on the BIDS server."""
    label_list = labels.split(",") if labels else None

    with _get_client(server, api_key) as client:
        try:
            result = client.query(
                subject_id=subject_id,
                session_id=session_id,
                modality=modality,
                labels=label_list,
                search=search,
                limit=limit,
                offset=offset,
            )
            if verbose:
                click.echo(f"Found {result.total} results")
            _output(result.resources, json_output, verbose)
        except BidsError as e:
            click.echo(f"Error: {e.message}", err=True)
            sys.exit(1)


# ------------------------------------------------------------------
# Labels
# ------------------------------------------------------------------
@cli.command()
@click.argument("resource_id")
@click.option("--server", required=True, help="BIDS server URL")
@click.option("--api-key", default=None, help="API key")
@click.option("--set", "set_labels", default=None, help="JSON array of labels to set")
@click.option("--add", default=None, help="JSON array of labels to add")
@click.option("--remove", default=None, help="Comma-separated label keys to remove")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def label(
    resource_id: str,
    server: str,
    api_key: Optional[str],
    set_labels: Optional[str],
    add: Optional[str],
    remove: Optional[str],
    json_output: bool,
    verbose: bool,
) -> None:
    """Manage labels on a resource."""
    with _get_client(server, api_key) as client:
        try:
            if set_labels:
                labels = json.loads(set_labels)
                result = client.set_labels(resource_id, labels)
            elif add or remove:
                add_list = json.loads(add) if add else None
                remove_list = remove.split(",") if remove else None
                result = client.patch_labels(resource_id, add=add_list, remove=remove_list)
            else:
                result = client.get_labels(resource_id)
            if verbose:
                click.echo("Labels:")
            _output(result, json_output, verbose)
        except BidsError as e:
            click.echo(f"Error: {e.message}", err=True)
            sys.exit(1)


# ------------------------------------------------------------------
# Subjects
# ------------------------------------------------------------------
@cli.command("subjects")
@click.option("--server", required=True, help="BIDS server URL")
@click.option("--api-key", default=None, help="API key")
@click.option("--list", "list_subjects", is_flag=True, help="List all subjects")
@click.option("--create", "create_id", default=None, help="Create subject with ID")
@click.option("--get", "get_id", default=None, help="Get subject by ID")
@click.option("--patient-ref", default=None, help="Patient reference (for create)")
@click.option("--hospital-ids", default=None, help="Comma-separated hospital IDs")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def subjects(
    server: str,
    api_key: Optional[str],
    list_subjects: bool,
    create_id: Optional[str],
    get_id: Optional[str],
    patient_ref: Optional[str],
    hospital_ids: Optional[str],
    json_output: bool,
    verbose: bool,
) -> None:
    """Manage subjects on the BIDS server."""
    with _get_client(server, api_key) as client:
        try:
            if create_id:
                hid_list = hospital_ids.split(",") if hospital_ids else None
                result = client.create_subject(create_id, patient_ref, hid_list)
                if verbose:
                    click.echo("Subject created:")
                _output(result, json_output, verbose)
            elif get_id:
                result = client.get_subject(get_id)
                _output(result, json_output, verbose)
            else:
                result = client.list_subjects()
                if verbose:
                    click.echo(f"Found {len(result)} subjects:")
                _output(result, json_output, verbose)
        except BidsError as e:
            click.echo(f"Error: {e.message}", err=True)
            sys.exit(1)


# ------------------------------------------------------------------
# Sessions
# ------------------------------------------------------------------
@cli.command("sessions")
@click.option("--server", required=True, help="BIDS server URL")
@click.option("--api-key", default=None, help="API key")
@click.option("--list", "list_sessions", is_flag=True, help="List sessions")
@click.option("--create", "create_id", default=None, help="Create session with ID")
@click.option("--subject", "subject_id", required=True, help="Subject ID")
@click.option("--session-label", default=None, help="Session label")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def sessions(
    server: str,
    api_key: Optional[str],
    list_sessions: bool,
    create_id: Optional[str],
    subject_id: str,
    session_label: Optional[str],
    json_output: bool,
    verbose: bool,
) -> None:
    """Manage sessions on the BIDS server."""
    with _get_client(server, api_key) as client:
        try:
            if create_id:
                result = client.create_session(create_id, subject_id, session_label)
                if verbose:
                    click.echo("Session created:")
                _output(result, json_output, verbose)
            else:
                result = client.list_sessions(subject_id)
                if verbose:
                    click.echo(f"Found {len(result)} sessions:")
                _output(result, json_output, verbose)
        except BidsError as e:
            click.echo(f"Error: {e.message}", err=True)
            sys.exit(1)


# ------------------------------------------------------------------
# Tasks
# ------------------------------------------------------------------
@cli.command("tasks")
@click.option("--server", required=True, help="BIDS server URL")
@click.option("--api-key", default=None, help="API key")
@click.option("--submit", "action", default=None, help="Submit task with action")
@click.option("--resource-ids", default=None, help="Comma-separated resource IDs")
@click.option("--params", default=None, help="JSON parameters for the task")
@click.option("--status", "task_id", default=None, help="Get task status by ID")
@click.option("--cancel", "cancel_id", default=None, help="Cancel task by ID")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def tasks(
    server: str,
    api_key: Optional[str],
    action: Optional[str],
    resource_ids: Optional[str],
    params: Optional[str],
    task_id: Optional[str],
    cancel_id: Optional[str],
    json_output: bool,
    verbose: bool,
) -> None:
    """Manage async tasks."""
    with _get_client(server, api_key) as client:
        try:
            if action:
                rid_list = resource_ids.split(",") if resource_ids else []
                param_dict = json.loads(params) if params else None
                result = client.submit_task(action, rid_list, param_dict)
                if verbose:
                    click.echo("Task submitted:")
                _output(result, json_output, verbose)
            elif cancel_id:
                result = client.cancel_task(cancel_id)
                if verbose:
                    click.echo("Task cancelled:")
                _output(result, json_output, verbose)
            elif task_id:
                result = client.get_task(task_id)
                _output(result, json_output, verbose)
            else:
                click.echo("Specify --submit, --status, or --cancel", err=True)
                sys.exit(1)
        except BidsError as e:
            click.echo(f"Error: {e.message}", err=True)
            sys.exit(1)


# ------------------------------------------------------------------
# Verify
# ------------------------------------------------------------------
@cli.command()
@click.option("--server", required=True, help="BIDS server URL")
@click.option("--api-key", default=None, help="API key")
@click.option("--target", default=None, help="Target to verify")
@click.option("--check-hash/--no-check-hash", default=True, help="Verify file hashes")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def verify(
    server: str,
    api_key: Optional[str],
    target: Optional[str],
    check_hash: bool,
    json_output: bool,
    verbose: bool,
) -> None:
    """Verify data integrity on the BIDS server."""
    with _get_client(server, api_key) as client:
        try:
            result = client.verify(target=target, check_hash=check_hash)
            if verbose:
                click.echo("Verification result:")
            _output(result, json_output, verbose)
        except BidsError as e:
            click.echo(f"Error: {e.message}", err=True)
            sys.exit(1)


# ------------------------------------------------------------------
# Rebuild
# ------------------------------------------------------------------
@cli.command()
@click.option("--server", required=True, help="BIDS server URL")
@click.option("--api-key", default=None, help="API key")
@click.option("--target", default=None, help="Target to rebuild")
@click.option("--clear-existing", is_flag=True, help="Clear existing data")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def rebuild(
    server: str,
    api_key: Optional[str],
    target: Optional[str],
    clear_existing: bool,
    json_output: bool,
    verbose: bool,
) -> None:
    """Rebuild the BIDS server database."""
    with _get_client(server, api_key) as client:
        try:
            result = client.rebuild(target=target, clear_existing=clear_existing)
            if verbose:
                click.echo("Rebuild result:")
            _output(result, json_output, verbose)
        except BidsError as e:
            click.echo(f"Error: {e.message}", err=True)
            sys.exit(1)


if __name__ == "__main__":
    cli()
