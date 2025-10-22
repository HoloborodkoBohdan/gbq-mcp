#!/usr/bin/env python3
"""BigQuery MCP Server - Read-only access to BigQuery datasets."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any

from fastapi.middleware.cors import CORSMiddleware
from google.cloud import bigquery
from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse
from starlette.routing import Route

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
    ctx = app.get_context()
    return ctx.request_context.lifespan_context


@app.tool()
def get_query_limits() -> Dict[str, Any]:
    """Get current BigQuery query limits and configuration."""
    ctx = get_context()
    query_limits = ctx.config.get_query_limits()

    return {
        "limits": {
            "max_results": query_limits.max_results,
            "maximum_bytes_billed": query_limits.maximum_bytes_billed,
            "maximum_bytes_billed_mb": round(query_limits.maximum_bytes_billed / (1024 * 1024), 2),
            "maximum_bytes_billed_gb": round(query_limits.maximum_bytes_billed / (1024 * 1024 * 1024), 2)
        },
        "cost_info": {
            "rate": "$5.00 per TB (US region)",
            "note": "Queries are automatically checked against billing limits before execution"
        }
    }


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
    """
    ctx = get_context()
    query_limits = ctx.config.get_query_limits()

    if max_results > query_limits.max_results:
        raise ValueError(f"max_results cannot exceed {query_limits.max_results}")

    ctx.query_validator.validate_or_raise(query)
    ctx.access_control.validate_query_tables(query)

    try:
        client = ctx.bq_client_service.get_client()
        dry_run_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        dry_run_job = client.query(query, job_config=dry_run_config)

        bytes_to_process = dry_run_job.total_bytes_processed
        bytes_in_mb = bytes_to_process / (1024 * 1024)
        bytes_in_gb = bytes_to_process / (1024 * 1024 * 1024)
        estimated_cost_usd = (bytes_to_process / (1024 ** 4)) * 5

        exceeds_limit = bytes_to_process > query_limits.maximum_bytes_billed

        if exceeds_limit and not confirmed:
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


@app.resource("bigquery://tables")
def list_tables_resource() -> str:
    """List all available BigQuery tables as a resource."""
    ctx = get_context()
    allowed_tables = ctx.access_control.get_all_allowed_tables()

    output = "# Available BigQuery Tables\n\n"
    output += f"Total accessible tables/patterns: {len(allowed_tables)}\n\n"

    for table in allowed_tables:
        output += f"- `{table}`\n"

    output += "\n## Usage\n"
    output += "Use `get_table_schema(table_id)` tool to see detailed schema.\n"
    output += "Use `bq_query(query)` tool to query the data.\n"

    return output


@app.resource("bigquery://table/{table_id}/schema")
def table_schema_resource(table_id: str) -> str:
    """Get table schema as a readable resource."""
    ctx = get_context()

    if not ctx.access_control.is_table_allowed(table_id):
        return f"# Access Denied\n\nTable '{table_id}' is not in the allowed list."

    try:
        client = ctx.bq_client_service.get_client()
        table = client.get_table(table_id)

        output = f"# Schema: {table_id}\n\n"
        output += f"**Rows:** {table.num_rows:,}\n"
        output += f"**Size:** {table.num_bytes / (1024**3):.2f} GB\n"
        output += f"**Created:** {table.created.isoformat() if table.created else 'Unknown'}\n"
        output += f"**Modified:** {table.modified.isoformat() if table.modified else 'Unknown'}\n\n"

        if table.description:
            output += f"**Description:** {table.description}\n\n"

        output += "## Fields\n\n"
        output += "| Field | Type | Mode | Description |\n"
        output += "|-------|------|------|-------------|\n"

        for field in table.schema:
            desc = field.description or ""
            output += f"| {field.name} | {field.field_type} | {field.mode} | {desc} |\n"

        return output
    except Exception as e:
        return f"# Error\n\nFailed to fetch schema: {str(e)}"


@app.resource("bigquery://limits")
def query_limits_resource() -> str:
    """Get current query limits as a resource."""
    ctx = get_context()
    query_limits = ctx.config.get_query_limits()
    project_id = ctx.bq_client_service.get_project_id()

    output = "# BigQuery Query Limits\n\n"
    output += f"**Project:** {project_id}\n\n"
    output += "## Current Limits\n\n"
    output += f"- **Max Results per Query:** {query_limits.max_results:,} rows\n"
    output += f"- **Max Bytes Billed:** {query_limits.maximum_bytes_billed / (1024**2):.0f} MB "
    output += f"({query_limits.maximum_bytes_billed / (1024**3):.2f} GB)\n\n"
    output += "## Cost Information\n\n"
    output += "- **Rate:** $5.00 per TB (US region)\n"
    output += "- **Protection:** Queries are automatically checked against billing limits before execution\n"
    output += "- **Confirmation:** Large queries require explicit confirmation\n\n"
    output += "## Configuration\n\n"
    output += "Adjust limits in `.env` file:\n"
    output += "```bash\n"
    output += "MAX_QUERY_RESULTS=10000\n"
    output += "MAX_BYTES_BILLED_MB=100\n"
    output += "```\n"

    return output


@app.resource("bigquery://datasets")
def list_datasets_resource() -> str:
    """List all accessible datasets."""
    ctx = get_context()
    access_config = ctx.config.get_access_config()

    output = "# Accessible BigQuery Datasets\n\n"

    if access_config.allowed_datasets:
        output += "## Datasets with Full Access\n\n"
        for dataset_id, config in access_config.allowed_datasets.items():
            output += f"### {dataset_id}\n\n"
            if config.get("description"):
                output += f"{config['description']}\n\n"

            if config.get("allow_all_tables"):
                output += "- ✅ All tables accessible\n"

            if config.get("blacklisted_tables"):
                output += f"- ⛔ Blacklisted: {', '.join(config['blacklisted_tables'])}\n"

            output += "\n"

    if access_config.allowed_tables:
        output += "## Individual Tables\n\n"
        for table_id in access_config.allowed_tables:
            output += f"- `{table_id}`\n"
        output += "\n"

    if access_config.allowed_patterns:
        output += "## Wildcard Patterns\n\n"
        for pattern in access_config.allowed_patterns:
            output += f"- `{pattern}`\n"
        output += "\n"

    return output


def create_http_app():
    """Create HTTP transport app with CORS middleware for local access and ngrok sharing."""
    try:
        async def health_check(request):
            return JSONResponse({
                "status": "healthy",
                "service": "bigquery-mcp",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            })

        async def root(request):
            return JSONResponse({
                "service": "BigQuery MCP Server",
                "status": "running",
                "endpoints": {
                    "health": "/health",
                    "mcp": "/mcp"
                }
            })

        http_app = app.streamable_http_app()

        http_app.routes.insert(0, Route("/health", health_check, methods=["GET"]))
        http_app.routes.insert(0, Route("/", root, methods=["GET"]))

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

    if len(sys.argv) > 1 and sys.argv[1] == "--stdio":
        print("Starting in stdio mode...")
        app.run()
    elif len(sys.argv) > 1 and sys.argv[1] == "--ngrok":
        try:
            import uvicorn
            from pyngrok import ngrok

            port = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 8000

            print(f"Starting HTTP server on port {port}...")
            http_app = create_http_app()

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
