#!/usr/bin/env python3
"""BigQuery MCP Server - Read-only access to BigQuery datasets."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Dict, Any

from google.cloud import bigquery
from mcp.server.fastmcp import FastMCP

from services.configuration import ConfigurationService
from services.bigquery_client import BigQueryClientService
from services.query_validator import QueryValidatorService
from services.access_control import AccessControlService


@dataclass
class AppContext:
    """Application context with all services."""
    bq_client_service: BigQueryClientService
    query_validator: QueryValidatorService
    access_control: AccessControlService
    config: ConfigurationService


@asynccontextmanager
async def lifespan(application: FastMCP) -> AsyncIterator[AppContext]:
    """Async context manager for application lifecycle."""
    config = ConfigurationService()

    bq_client_service = BigQueryClientService(config)
    bq_client_service.initialize()

    query_validator = QueryValidatorService()
    access_control = AccessControlService(config.get_access_config())

    try:
        yield AppContext(
            bq_client_service=bq_client_service,
            query_validator=query_validator,
            access_control=access_control,
            config=config
        )
    finally:
        bq_client_service.close()


app = FastMCP("bigquery-mcp", lifespan=lifespan)


def get_context() -> AppContext:
    """Get application context with all services."""
    return app.get_context(AppContext)


@app.tool()
def list_tables() -> Dict[str, Any]:
    """List all available BigQuery tables that can be queried."""
    ctx = get_context()
    allowed_tables = ctx.access_control.get_all_allowed_tables()

    return {
        "total_tables": len(allowed_tables),
        "tables": allowed_tables,
        "note": "Use get_table_schema(table_id) to see detailed schema and description for any table"
    }


@app.tool()
def get_table_schema(table_id: str) -> Dict[str, Any]:
    """Get the schema of a specific BigQuery table."""
    ctx = get_context()

    if not ctx.access_control.is_table_allowed(table_id):
        raise ValueError(
            f"Table '{table_id}' is not allowed. Use list_tables to see available tables."
        )

    try:
        client = ctx.bq_client_service.get_client()
        table = client.get_table(table_id)

        fields = [
            {
                "name": field.name,
                "type": field.field_type,
                "mode": field.mode,
                "description": field.description or ""
            }
            for field in table.schema
        ]

        return {
            "table_id": table_id,
            "num_rows": table.num_rows,
            "num_bytes": table.num_bytes,
            "created": table.created.isoformat() if table.created else None,
            "modified": table.modified.isoformat() if table.modified else None,
            "description": table.description or "",
            "schema": fields
        }
    except Exception as e:
        raise ValueError(f"Error fetching schema for table '{table_id}': {str(e)}")


@app.tool()
def estimate_query_cost(query: str) -> Dict[str, Any]:
    """Estimate the cost of a query without executing it (dry-run)."""
    ctx = get_context()

    ctx.query_validator.validate_or_raise(query)
    ctx.access_control.validate_query_tables(query)

    try:
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        client = ctx.bq_client_service.get_client()
        job = client.query(query, job_config=job_config)

        bytes_processed = job.total_bytes_processed
        bytes_in_mb = bytes_processed / (1024 * 1024)
        bytes_in_gb = bytes_processed / (1024 * 1024 * 1024)

        # Rough cost estimation (as of 2024: $5 per TB in US)
        estimated_cost_usd = (bytes_processed / (1024 ** 4)) * 5

        return {
            "query": query,
            "bytes_processed": bytes_processed,
            "megabytes_processed": round(bytes_in_mb, 2),
            "gigabytes_processed": round(bytes_in_gb, 4),
            "estimated_cost_usd": round(estimated_cost_usd, 6),
            "note": "Cost estimate based on $5 per TB (US region). Actual costs may vary."
        }
    except Exception as e:
        raise ValueError(f"Error estimating query cost: {str(e)}")


@app.tool()
def bq_query(query: str, max_results: int = 1000, confirmed: bool = False) -> Dict[str, Any]:
    """Run read-only SELECT queries on allowed BigQuery tables.

    Automatically performs dry-run cost estimation first. If query exceeds limits,
    user confirmation is required before execution.

    Args:
        query: SQL SELECT query to execute
        max_results: Maximum number of results to return
        confirmed: Set to True to confirm execution of expensive queries
    """
    ctx = get_context()
    query_limits = ctx.config.get_query_limits()

    if max_results > query_limits.max_results:
        raise ValueError(f"max_results cannot exceed {query_limits.max_results}")

    ctx.query_validator.validate_or_raise(query)
    ctx.access_control.validate_query_tables(query)

    # Step 1: Always do dry-run first to check cost
    try:
        client = ctx.bq_client_service.get_client()
        dry_run_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        dry_run_job = client.query(query, job_config=dry_run_config)

        bytes_to_process = dry_run_job.total_bytes_processed
        bytes_in_mb = bytes_to_process / (1024 * 1024)
        bytes_in_gb = bytes_to_process / (1024 * 1024 * 1024)
        estimated_cost_usd = (bytes_to_process / (1024 ** 4)) * 5

        # Step 2: Check if query exceeds limits
        exceeds_limit = bytes_to_process > query_limits.maximum_bytes_billed

        if exceeds_limit and not confirmed:
            # Query exceeds limits - require user confirmation
            return {
                "requires_confirmation": True,
                "message": "Query exceeds billing limits. Review cost and confirm to proceed.",
                "cost_estimate": {
                    "bytes_to_process": bytes_to_process,
                    "megabytes": round(bytes_in_mb, 2),
                    "gigabytes": round(bytes_in_gb, 4),
                    "estimated_cost_usd": round(estimated_cost_usd, 6),
                    "limit_mb": query_limits.maximum_bytes_billed / (1024 * 1024),
                },
                "instructions": f"To proceed, call bq_query again with confirmed=True parameter. This will process {round(bytes_in_gb, 2)} GB and cost approximately ${round(estimated_cost_usd, 4)}.",
                "query": query
            }

        # Step 3: Execute query (either within limits or user confirmed)
        job_config = bigquery.QueryJobConfig(
            maximum_bytes_billed=bytes_to_process if exceeds_limit else query_limits.maximum_bytes_billed
        )
        job = client.query(query, job_config=job_config)

        results = [dict(row) for i, row in enumerate(job.result()) if i < max_results]

        return {
            "total_rows": job.result().total_rows,
            "returned_rows": len(results),
            "rows": results,
            "bytes_processed": job.total_bytes_processed,
            "bytes_billed": job.total_bytes_billed,
            "cost_estimate": {
                "megabytes": round(bytes_in_mb, 2),
                "gigabytes": round(bytes_in_gb, 4),
                "estimated_cost_usd": round(estimated_cost_usd, 6)
            }
        }
    except Exception as e:
        raise _handle_query_error(e)


def _handle_query_error(error: Exception) -> ValueError:
    """Handle query execution errors with helpful messages."""
    error_msg = str(error)

    if "403" in error_msg or "Permission denied" in error_msg or "Access Denied" in error_msg:
        return ValueError(
            f"Permission denied. Please check:\n"
            f"1. Service account has BigQuery User role\n"
            f"2. Service account has access to the dataset\n"
            f"3. Billing is enabled on the project\n"
            f"Original error: {error_msg}"
        )
    elif "404" in error_msg or "Not found" in error_msg:
        return ValueError(
            f"Table or dataset not found. Please verify:\n"
            f"1. Table name is correct\n"
            f"2. Dataset exists in the project\n"
            f"Original error: {error_msg}"
        )
    else:
        return ValueError(f"Query execution error: {error_msg}")


def create_http_app():
    """Create HTTP transport app with CORS middleware for local access and ngrok sharing."""
    try:
        from fastapi.middleware.cors import CORSMiddleware

        http_app = app.streamable_http_app()
        http_app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
            expose_headers=["Mcp-Session-Id"]
        )
        return http_app
    except ImportError:
        raise ImportError(
            "FastAPI is required for HTTP transport. "
            "Install with: pip install fastapi uvicorn"
        )


if __name__ == "__main__":
    import sys

    # Default to HTTP mode for local access
    # Use --stdio flag for Desktop Agent integration
    # Use --ngrok flag to share publicly
    if len(sys.argv) > 1 and sys.argv[1] == "--stdio":
        print("Starting in stdio mode...")
        app.run()
    elif len(sys.argv) > 1 and sys.argv[1] == "--ngrok":
        # Ngrok mode - expose local server to internet
        try:
            import uvicorn
            from pyngrok import ngrok

            port = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 8000

            print(f"Starting HTTP server on port {port}...")
            http_app = create_http_app()

            # Start ngrok tunnel
            public_url = ngrok.connect(port)
            print(f"\n{'='*60}")
            print(f"🌐 Server exposed via ngrok!")
            print(f"{'='*60}")
            print(f"Local:  http://localhost:{port}")
            print(f"Public: {public_url}")
            print(f"{'='*60}")
            print(f"\nShare this URL with others:")
            print(f"  {public_url}")
            print(f"\nNgrok Dashboard: http://localhost:4040")
            print(f"{'='*60}\n")

            uvicorn.run(http_app, host="0.0.0.0", port=port)
        except ImportError:
            print("Error: pyngrok is required for ngrok mode.")
            print("Install with: pip install pyngrok")
            print("\nAlternatively, run ngrok manually:")
            print("  Terminal 1: python server.py 8000")
            print("  Terminal 2: ngrok http 8000")
            sys.exit(1)
    else:
        # HTTP mode (default for local access)
        try:
            import uvicorn
            http_app = create_http_app()
            port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8000
            print(f"Starting HTTP server on port {port}...")
            print(f"Server running at: http://localhost:{port}")
            print(f"Health check: http://localhost:{port}/health")
            print(f"\nTip: Use 'python server.py --ngrok' to share publicly")
            uvicorn.run(http_app, host="0.0.0.0", port=port)
        except ImportError:
            print("Error: uvicorn is required for HTTP mode.")
            print("Install with: pip install fastapi uvicorn")
            sys.exit(1)
