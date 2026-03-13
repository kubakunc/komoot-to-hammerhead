import logging

import click

from . import db
from .sync import sync_all, sync_one


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def cli(verbose: bool) -> None:
    """Komoot → Hammerhead route sync tool."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


@cli.command()
@click.option("--tour-id", default=None, help="Sync a specific tour by ID")
def sync(tour_id: str | None) -> None:
    """Sync planned routes from Komoot to Hammerhead."""
    if tour_id:
        result = sync_one(tour_id)
    else:
        result = sync_all()

    click.echo(f"Synced: {result.synced}  Skipped: {result.skipped}  Failed: {result.failed}")
    if result.errors:
        for err in result.errors:
            click.echo(f"  ERROR: {err}", err=True)


@cli.command()
def status() -> None:
    """Show sync statistics."""
    db.init_db()
    stats = db.get_stats()
    click.echo(f"Total:   {stats['total']}")
    click.echo(f"Success: {stats['success']}")
    click.echo(f"Failed:  {stats['failed']}")


@cli.command()
@click.option("--host", default="0.0.0.0", help="Bind host")
@click.option("--port", default=8000, help="Bind port")
def serve(host: str, port: int) -> None:
    """Start the FastAPI web server."""
    import uvicorn
    from .server import app

    uvicorn.run(app, host=host, port=port)
