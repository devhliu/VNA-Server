"""VNA Main Server CLI."""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Optional

import click

from vna_main_sdk.client import VnaClient, VnaClientError

logger = logging.getLogger(__name__)


def get_client(ctx: click.Context) -> VnaClient:
    """Get the VNA client from context."""
    return ctx.obj["client"]


def output_json(ctx: click.Context, data: Any) -> None:
    """Output data as JSON if --json flag is set."""
    if isinstance(data, list):
        out = [d.model_dump(mode="json") if hasattr(d, "model_dump") else d for d in data]
    elif hasattr(data, "model_dump"):
        out = data.model_dump(mode="json")
    else:
        out = data
    click.echo(json.dumps(out, indent=2, default=str))


def output_verbose(ctx: click.Context, msg: str) -> None:
    """Output verbose message if --verbose flag is set."""
    if ctx.obj.get("verbose"):
        click.echo(f"[verbose] {msg}", err=True)


@click.group()
@click.option(
    "--base-url",
    envvar="VNA_BASE_URL",
    default="http://localhost:8000",
    help="VNA server base URL.",
)
@click.option(
    "--api-key",
    envvar="VNA_API_KEY",
    default=None,
    help="API key for authentication.",
)
@click.option("--json", "output_json_flag", is_flag=True, help="Output as JSON.")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output.")
@click.pass_context
def cli(
    ctx: click.Context,
    base_url: str,
    api_key: Optional[str],
    output_json_flag: bool,
    verbose: bool,
) -> None:
    """VNA Main Server CLI."""
    ctx.ensure_object(dict)
    ctx.obj["client"] = VnaClient(base_url=base_url, api_key=api_key)
    ctx.obj["json"] = output_json_flag
    ctx.obj["verbose"] = verbose


def _handle_error(ctx: click.Context, e: VnaClientError) -> None:
    """Handle client errors."""
    click.echo(f"Error: {e}", err=True)
    if e.detail:
        click.echo(f"Detail: {json.dumps(e.detail, indent=2) if isinstance(e.detail, (dict, list)) else e.detail}", err=True)
    sys.exit(1)


# ─── Resources ─────────────────────────────────────────────────────────────────

@cli.group()
def resources() -> None:
    """Manage resources."""
    logger.debug("resources command group invoked")


@resources.command("list")
@click.option("--patient", "patient_ref", default=None, help="Filter by patient reference.")
@click.option("--type", "data_type", default=None, help="Filter by data type.")
@click.option("--source", "source_type", default=None, help="Filter by source type.")
@click.option("--labels", default=None, help="Filter by labels (JSON).")
@click.option("--limit", default=50, type=int, help="Max results.")
@click.option("--offset", default=0, type=int, help="Pagination offset.")
@click.pass_context
def resources_list(
    ctx: click.Context,
    patient_ref: Optional[str],
    data_type: Optional[str],
    source_type: Optional[str],
    labels: Optional[str],
    limit: int,
    offset: int,
) -> None:
    """List resources."""
    labels_dict = json.loads(labels) if labels else None
    try:
        result = get_client(ctx).list_resources(
            patient_ref=patient_ref,
            data_type=data_type,
            source_type=source_type,
            labels=labels_dict,
            limit=limit,
            offset=offset,
        )
        if ctx.obj["json"]:
            output_json(ctx, result)
        else:
            click.echo(f"Total: {result.total}, showing {len(result.resources)} resources")
            for r in result.resources:
                click.echo(f"  {r.resource_id} [{r.source_type}] {r.patient_ref}")
    except VnaClientError as e:
        _handle_error(ctx, e)


@resources.command("get")
@click.argument("resource_id")
@click.pass_context
def resources_get(ctx: click.Context, resource_id: str) -> None:
    """Get a resource by ID."""
    try:
        result = get_client(ctx).get_resource(resource_id)
        if ctx.obj["json"]:
            output_json(ctx, result)
        else:
            click.echo(f"Resource: {result.resource_id}")
            click.echo(f"  Patient: {result.patient_ref}")
            click.echo(f"  Source: {result.source_type}")
            click.echo(f"  Data Type: {result.data_type}")
    except VnaClientError as e:
        _handle_error(ctx, e)


@resources.command("register")
@click.option("--patient", "patient_ref", required=True, help="Patient reference.")
@click.option("--source", "source_type", required=True, help="Source type (dicom/bids).")
@click.option("--dicom-study-uid", default=None, help="DICOM Study Instance UID.")
@click.option("--dicom-series-uid", default=None, help="DICOM Series Instance UID.")
@click.option("--bids-path", default=None, help="BIDS file path.")
@click.option("--bids-subject", default=None, help="BIDS subject ID.")
@click.option("--bids-session", default=None, help="BIDS session ID.")
@click.option("--bids-datatype", default=None, help="BIDS datatype.")
@click.option("--data-type", default=None, help="Data type classification.")
@click.option("--labels", default=None, help="Labels (JSON).")
@click.option("--metadata", default=None, help="Metadata (JSON).")
@click.pass_context
def resources_register(
    ctx: click.Context,
    patient_ref: str,
    source_type: str,
    dicom_study_uid: Optional[str],
    dicom_series_uid: Optional[str],
    bids_path: Optional[str],
    bids_subject: Optional[str],
    bids_session: Optional[str],
    bids_datatype: Optional[str],
    data_type: Optional[str],
    labels: Optional[str],
    metadata: Optional[str],
) -> None:
    """Register a new resource."""
    labels_dict = json.loads(labels) if labels else None
    metadata_dict = json.loads(metadata) if metadata else None
    try:
        result = get_client(ctx).register_resource(
            patient_ref=patient_ref,
            source_type=source_type,
            dicom_study_uid=dicom_study_uid,
            dicom_series_uid=dicom_series_uid,
            bids_path=bids_path,
            bids_subject=bids_subject,
            bids_session=bids_session,
            bids_datatype=bids_datatype,
            data_type=data_type,
            labels=labels_dict,
            metadata=metadata_dict,
        )
        if ctx.obj["json"]:
            output_json(ctx, result)
        else:
            click.echo(f"Registered: {result.resource_id}")
    except VnaClientError as e:
        _handle_error(ctx, e)


@resources.command("delete")
@click.argument("resource_id")
@click.pass_context
def resources_delete(ctx: click.Context, resource_id: str) -> None:
    """Delete a resource from the index."""
    try:
        result = get_client(ctx).delete_resource(resource_id)
        if ctx.obj["json"]:
            output_json(ctx, result)
        else:
            click.echo(f"Deleted: {resource_id}")
    except VnaClientError as e:
        _handle_error(ctx, e)


# ─── Patients ──────────────────────────────────────────────────────────────────

@cli.group()
def patients() -> None:
    """Manage patients."""
    logger.debug("patients command group invoked")


@patients.command("list")
@click.option("--limit", default=50, type=int, help="Max results.")
@click.option("--offset", default=0, type=int, help="Pagination offset.")
@click.pass_context
def patients_list(ctx: click.Context, limit: int, offset: int) -> None:
    """List patients."""
    try:
        result = get_client(ctx).list_patients(limit=limit, offset=offset)
        if ctx.obj["json"]:
            output_json(ctx, result)
        else:
            total = result.get("total", 0)
            pts = result.get("patients", [])
            click.echo(f"Total: {total}, showing {len(pts)} patients")
            for p in pts:
                click.echo(f"  {p.get('patient_ref', '?')}")
    except VnaClientError as e:
        _handle_error(ctx, e)


@patients.command("get")
@click.argument("patient_ref")
@click.pass_context
def patients_get(ctx: click.Context, patient_ref: str) -> None:
    """Get a patient with all resources."""
    try:
        result = get_client(ctx).get_patient(patient_ref)
        if ctx.obj["json"]:
            output_json(ctx, result)
        else:
            click.echo(f"Patient: {result.patient_ref}")
            click.echo(f"  Hospital ID: {result.hospital_id}")
            click.echo(f"  Resources: {result.resource_count}")
    except VnaClientError as e:
        _handle_error(ctx, e)


@patients.command("create")
@click.argument("patient_ref")
@click.option("--hospital-id", default=None, help="Hospital patient ID.")
@click.option("--source", default=None, help="Hospital/source identifier.")
@click.pass_context
def patients_create(
    ctx: click.Context,
    patient_ref: str,
    hospital_id: Optional[str],
    source: Optional[str],
) -> None:
    """Create a patient ID mapping."""
    try:
        result = get_client(ctx).create_patient(
            patient_ref=patient_ref,
            hospital_id=hospital_id,
            source=source,
        )
        if ctx.obj["json"]:
            output_json(ctx, result)
        else:
            click.echo(f"Created: {result.patient_ref}")
    except VnaClientError as e:
        _handle_error(ctx, e)


# ─── Labels ────────────────────────────────────────────────────────────────────

@cli.group()
def labels() -> None:
    """Manage labels."""
    logger.debug("labels command group invoked")


@labels.command("get")
@click.argument("resource_id")
@click.pass_context
def labels_get(ctx: click.Context, resource_id: str) -> None:
    """Get labels for a resource."""
    try:
        result = get_client(ctx).get_labels(resource_id)
        if ctx.obj["json"]:
            output_json(ctx, result)
        else:
            if not result:
                click.echo("No labels")
            for label in result:
                val = f"={label.value}" if label.value else ""
                click.echo(f"  {label.key}{val}")
    except VnaClientError as e:
        _handle_error(ctx, e)


@labels.command("set")
@click.argument("resource_id")
@click.option("--labels", "labels_json", required=True, help="Labels (JSON dict).")
@click.pass_context
def labels_set(ctx: click.Context, resource_id: str, labels_json: str) -> None:
    """Set labels for a resource (replaces existing)."""
    labels_dict = json.loads(labels_json)
    try:
        result = get_client(ctx).set_labels(resource_id, labels_dict)
        if ctx.obj["json"]:
            output_json(ctx, result)
        else:
            click.echo(f"Set {len(result)} labels")
    except VnaClientError as e:
        _handle_error(ctx, e)


@labels.command("patch")
@click.argument("resource_id")
@click.option("--add", "add_json", default=None, help="Labels to add (JSON dict).")
@click.option("--remove", "remove_keys", default=None, help="Label keys to remove (comma-separated).")
@click.pass_context
def labels_patch(
    ctx: click.Context,
    resource_id: str,
    add_json: Optional[str],
    remove_keys: Optional[str],
) -> None:
    """Patch labels for a resource (add/remove)."""
    add_dict = json.loads(add_json) if add_json else None
    remove_list = remove_keys.split(",") if remove_keys else None
    try:
        result = get_client(ctx).patch_labels(resource_id, add=add_dict, remove=remove_list)
        if ctx.obj["json"]:
            output_json(ctx, result)
        else:
            click.echo(f"Patched, now {len(result)} labels")
    except VnaClientError as e:
        _handle_error(ctx, e)


@labels.command("tags")
@click.pass_context
def labels_tags(ctx: click.Context) -> None:
    """List all tags with counts."""
    try:
        result = get_client(ctx).list_all_tags()
        if ctx.obj["json"]:
            output_json(ctx, result)
        else:
            for tag in result:
                click.echo(f"  {tag.key}: {tag.count}")
    except VnaClientError as e:
        _handle_error(ctx, e)


# ─── Query ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--patient", "patient_ref", default=None, help="Filter by patient reference.")
@click.option("--type", "data_type", default=None, help="Filter by data type.")
@click.option("--source", "source_type", default=None, help="Filter by source type.")
@click.option("--labels", default=None, help="Filter by labels (JSON).")
@click.option("--search", default=None, help="Full-text search.")
@click.option("--limit", default=50, type=int, help="Max results.")
@click.option("--offset", default=0, type=int, help="Pagination offset.")
@click.pass_context
def query(
    ctx: click.Context,
    patient_ref: Optional[str],
    data_type: Optional[str],
    source_type: Optional[str],
    labels: Optional[str],
    search: Optional[str],
    limit: int,
    offset: int,
) -> None:
    """Unified query across all data sources."""
    labels_dict = json.loads(labels) if labels else None
    try:
        result = get_client(ctx).query(
            patient_ref=patient_ref,
            data_type=data_type,
            source_type=source_type,
            labels=labels_dict,
            search=search,
            limit=limit,
            offset=offset,
        )
        if ctx.obj["json"]:
            output_json(ctx, result)
        else:
            click.echo(f"Total: {result.total}, showing {len(result.resources)} resources")
            for r in result.resources:
                click.echo(f"  {r.resource_id} [{r.source_type}] {r.patient_ref}")
    except VnaClientError as e:
        _handle_error(ctx, e)


# ─── Sync ──────────────────────────────────────────────────────────────────────

@cli.group()
def sync() -> None:
    """Manage sync."""
    logger.debug("sync command group invoked")


@sync.command("status")
@click.pass_context
def sync_status(ctx: click.Context) -> None:
    """Get sync status."""
    try:
        result = get_client(ctx).sync_status()
        if ctx.obj["json"]:
            output_json(ctx, result)
        else:
            click.echo("Sync Status:")
            click.echo(f"  DICOM: {result.dicom}")
            click.echo(f"  BIDS: {result.bids}")
            click.echo(f"  Last Sync: {result.last_sync}")
    except VnaClientError as e:
        _handle_error(ctx, e)


@sync.command("trigger")
@click.option("--source", required=True, type=click.Choice(["dicom", "bids"]), help="Sync source.")
@click.pass_context
def sync_trigger(ctx: click.Context, source: str) -> None:
    """Trigger manual sync."""
    try:
        result = get_client(ctx).trigger_sync(source)
        if ctx.obj["json"]:
            output_json(ctx, result)
        else:
            click.echo(f"Sync triggered for {source}")
    except VnaClientError as e:
        _handle_error(ctx, e)


# ─── Health ────────────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def health(ctx: click.Context) -> None:
    """Health check."""
    try:
        result = get_client(ctx).health()
        if ctx.obj["json"]:
            output_json(ctx, result)
        else:
            click.echo(f"Status: {result.status}")
            click.echo(f"Version: {result.version}")
            click.echo(f"Database: {result.database}")
    except VnaClientError as e:
        _handle_error(ctx, e)


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
