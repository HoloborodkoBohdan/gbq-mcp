# BigQuery MCP Server

Production-ready MCP server for secure, read-only access to Google BigQuery datasets. Features table-level access control, query cost estimation, HTTP transport, and comprehensive security validation.

**📚 Documentation:**
- [Architecture](docs/ARCHITECTURE.md) - System design and architecture
- [WSL Setup Guide](docs/WSL_SETUP.md) - Windows + WSL configuration
- [Ngrok Sharing Guide](docs/NGROK_SETUP.md) - Share server with others

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup Authentication

**For public datasets**: Place your service account JSON file at:
```
/mcp-gbq/service-account.json
```

The server will automatically use this file if it exists.

**Alternative methods** (if not using service-account.json):

```bash
# Option 1: Use your Google account
gcloud auth application-default login

# Option 2: Set environment variable
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

### 3. Run the Server

**HTTP mode (default - recommended for deployment):**
```bash
# Install HTTP dependencies
pip install fastapi uvicorn

# Run on default port 8000
python server.py

# Run on custom port
python server.py 8765
```

**Stdio mode (for Desktop Agent integration):**
```bash
python server.py --stdio
```

**Ngrok mode (share with others):**
```bash
# Install ngrok support
pip install pyngrok

# Start server with ngrok
python server.py --ngrok

# Returns public URL like: https://abc123.ngrok-free.app
# Share this URL with anyone!
```

📖 **See [docs/NGROK_SETUP.md](docs/NGROK_SETUP.md) for complete ngrok guide with authentication, monitoring, and troubleshooting.**

## Connect to Desktop Agent

### macOS/Linux

Add to your Desktop Agent config file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "bigquery": {
      "command": "python",
      "args": ["/absolute/path/to/mcp-gbq/server.py", "--stdio"]
    }
  }
}
```

Restart Desktop Agent. You should see the MCP server connected with 4 tools available.

### Windows + WSL

📖 **See [docs/WSL_SETUP.md](docs/WSL_SETUP.md) for complete Windows + WSL configuration guide.**

Quick configuration:
```json
{
  "mcpServers": {
    "bigquery": {
      "command": "wsl",
      "args": [
        "bash",
        "-c",
        "cd /home/YOUR_USERNAME/mcp-gbq && source venv/bin/activate && python server.py --stdio"
      ]
    }
  }
}
```

Replace `YOUR_USERNAME` with your WSL username.

## Local HTTP Server

The server runs in HTTP mode by default for local testing and development.

### Start Local HTTP Server

```bash
# Start HTTP server
python server.py 8000

# Test health endpoint
curl http://localhost:8000/health

# Access in browser
open http://localhost:8000
```

## Testing with MCP Inspector

```bash
npx @modelcontextprotocol/inspector python server.py --stdio
```

## Available Tools

The server provides 4 tools:

1. **list_tables** - See all available datasets and tables
2. **get_table_schema** - View table structure and field types
3. **estimate_query_cost** - Estimate query cost without executing (dry-run)
4. **bq_query** - Run SELECT queries on allowed tables

## Security Features

**Read-Only Enforcement:**
- Only SELECT queries allowed
- Blocks: DELETE, UPDATE, INSERT, CREATE, DROP, ALTER, MERGE, TRUNCATE, REPLACE, GRANT, REVOKE
- Prevents SQL injection and multi-statement attacks
- Removes comments and string literals before validation
- Validates against allowed table whitelist

**Query Limits:**
- Maximum 10,000 rows per query
- 100 MB billing limit per query
- Table access controlled by whitelist

**Validation Examples:**
```sql
✓ SELECT * FROM table WHERE name = 'DELETE'  -- String literals OK
✓ SELECT * FROM table /* comment */          -- Comments removed safely
✗ SELECT * FROM table; DROP TABLE users;     -- Multi-statement blocked
✗ DELETE FROM table                          -- Non-SELECT blocked
```

## Current Datasets

- `bigquery-public-data.iowa_liquor_sales.sales` - Iowa liquor retail sales
- `bigquery-public-data.austin_bikeshare.bikeshare_stations` - Austin bike stations
- `bigquery-public-data.austin_bikeshare.bikeshare_trips` - Austin bike trip history

## How to Use

Once connected to Desktop Agent, you can interact with BigQuery through natural language. Claude will automatically use the MCP tools.

### Example Queries

**List available tables:**
```
You: What tables are available in BigQuery?
You: Show me what datasets I can query
```

**Explore table schemas:**
```
You: What's the schema for the Iowa liquor sales table?
You: Show me the fields in austin bikeshare trips
You: What columns are available in the bikeshare stations table?
```

**Estimate query costs:**
```
You: How much will this query cost to run? SELECT * FROM `bigquery-public-data.iowa_liquor_sales.sales`
You: Estimate the cost of querying all Austin bike trips
You: What's the data size for this query?
```

**Query data:**
```
You: Show me the top 10 liquor sales from Iowa
You: Which cities in Iowa have the highest liquor sales?
You: Get 5 recent bike trips from Austin
You: How many bike stations are there in each council district?
You: What's the average trip duration in the Austin bikeshare system?
```

**Complex analysis:**
```
You: Analyze Iowa liquor sales by category and show trends
You: Compare bike usage patterns between different Austin neighborhoods
You: Find the busiest bike stations in Austin
```

### Example Conversation

```
You: What datasets do I have access to?
Claude: [Uses list_tables and shows 3 available tables with descriptions]

You: Show me the schema for austin bikeshare trips
Claude: [Uses get_table_schema and displays field names, types, and metadata]

You: Get the top 5 most popular start stations
Claude: [Uses bq_query with SQL and presents results]

You: Now show me the average trip duration for each subscriber type
Claude: [Executes another query and analyzes the data]
```

### Direct SQL Queries

You can also write SQL directly:
```
You: Run this query:
SELECT store_name, SUM(sale_dollars) as total
FROM `bigquery-public-data.iowa_liquor_sales.sales`
GROUP BY store_name
ORDER BY total DESC
LIMIT 10
```

## Advanced Features

### Automatic Cost Protection

**All queries automatically perform dry-run cost estimation first!**

The server protects against expensive queries by:
1. Running a dry-run to estimate cost before execution
2. Comparing estimated bytes against billing limits (100 MB default)
3. Requiring user confirmation for queries that exceed limits

**Example workflow:**

```
You: Query all Iowa liquor sales for the entire year
Claude: [Runs dry-run first]
Claude: ⚠️ This query will process 2.5 GB and cost approximately $0.0125.
       This exceeds the 100 MB limit. Do you want to proceed?

You: Yes, proceed
Claude: [Executes query with confirmed=True]
Claude: [Returns results with actual cost information]
```

**Cost estimate includes:**
- Bytes to be processed
- Data size in MB/GB
- Estimated cost in USD ($5 per TB)
- Comparison to configured limits

**Benefits:**
- Prevents accidental expensive queries
- User always knows the cost before execution
- No surprises on your BigQuery bill
- Can still run large queries after confirmation

### Async Lifecycle Management

The server uses proper async context management for BigQuery client lifecycle:
- Automatic connection setup on startup
- Graceful cleanup on shutdown
- Resource pooling for better performance

### HTTP Transport

Run the server with HTTP transport for local access or sharing via ngrok:

```bash
# Start HTTP server (local access)
python server.py 8000

# Share publicly via ngrok
python server.py --ngrok

# Access via HTTP endpoint
curl http://localhost:8000
```

**Use cases:**
- Local testing and development
- Share with others via ngrok
- Access from web applications

### Cost Estimation (Dry-run)

Estimate query costs before execution:

```python
# Via Desktop Agent
You: "Estimate cost for: SELECT * FROM bigquery-public-data.iowa_liquor_sales.sales WHERE date > '2020-01-01'"

# Response includes:
# - Bytes to be processed
# - Estimated cost in USD
# - Data size in MB/GB
```

**Benefits:**
- Avoid expensive queries
- Budget planning
- Query optimization

## Testing

### Run All Tests

```bash
python tests/run_all_tests.py
```

**Expected output:**
```
Total Tests:     24
Passed:          24 ✓
Failed:          0
Pass Rate:       100.0%

🎉 All tests passed! 🎉
```

### Test Coverage

- ✅ **SQL Validation** (14 tests) - Security and query safety
- ✅ **Feature Tests** (8 tests) - Async lifecycle, HTTP, cost estimation
- ✅ **Import Tests** (2 tests) - Module availability

### Individual Tests

```bash
# SQL security validation
python tests/test_validation.py

# Feature availability
python tests/test_features.py
```

See [tests/README.md](tests/README.md) for detailed testing documentation.

## What's Next

### Add More Datasets

Edit `ALLOWED_TABLES_CONFIG` in `server.py`:

```python
ALLOWED_TABLES_CONFIG = {
    "bigquery-public-data.dataset_name.table_name": {
        "description": "What this table contains",
        "context": "When to use this data",
        "key_fields": ["important_field1", "important_field2"]
    }
}
```

Browse public datasets: https://console.cloud.google.com/marketplace/browse?filter=solution-type:dataset

### Customize Safety Limits

Edit `server.py` to adjust:
- `max_results` limit (currently 10,000 rows)
- `maximum_bytes_billed` (currently 100 MB)

### Add Features

Potential enhancements:
- Query result caching
- Rate limiting per user
- Query history logging
- Custom prompt templates for common queries
- Support for parameterized queries

## Troubleshooting

### Permission Denied Errors

If you see "Permission denied" or "403" errors:

**1. Check your service account has the right roles:**

Your service account needs at minimum:
- `BigQuery User` role (to run queries)
- `BigQuery Data Viewer` role (to read data)

In Google Cloud Console:
1. Go to IAM & Admin > Service Accounts
2. Find your service account
3. Click "Permissions" tab
4. Grant roles: `BigQuery User` and `BigQuery Data Viewer`

**2. Enable billing on your project:**

Public datasets are free to query, but you still need billing enabled:
1. Go to Billing in Google Cloud Console
2. Link a billing account to your project

**3. For public datasets:**

If querying public datasets (like `bigquery-public-data.*`), your service account needs:
- BigQuery User role on YOUR project (where queries run)
- Billing enabled on YOUR project

You don't need special permissions on the `bigquery-public-data` project.

**4. Verify service account file:**

```bash
# Check service account file exists
ls -la /mcp-gbq/service-account.json

# Verify it's valid JSON
cat service-account.json | jq .project_id
```

### Table Not Found Errors

**"Table not found" or "404"**:
- Verify table ID is correct: `project.dataset.table`
- Check table exists in BigQuery console
- Ensure table is in allowed list (use `list_tables` to verify)

### Query Errors

**"Exceeded budget"**:
- Queries are limited to 100 MB billing
- Add `LIMIT` clause to reduce data scanned
- Use `WHERE` to filter data before scanning

**Connection errors**:
- Restart Desktop Agent
- Check WSL is running: `wsl --status` in Windows
- Verify Python and venv work: `wsl bash -c "cd /mcp-gbq && source venv/bin/activate && python --version"`

### Test Your Setup

Run this in WSL to test authentication:

```bash
cd ~/mcp-gbq
source venv/bin/activate
python -c "
from google.cloud import bigquery
import json

with open('service-account.json') as f:
    info = json.load(f)
    project = info['project_id']

client = bigquery.Client.from_service_account_json('service-account.json', project=project)
query = 'SELECT 1 as test'
result = list(client.query(query).result())
print(f'✓ Authentication works! Project: {project}')
print(f'✓ Test query result: {result}')
"
```

If this works, the MCP server should work too.

## References

- [MCP Specification](https://github.com/modelcontextprotocol/specification)
- [BigQuery Public Datasets](https://cloud.google.com/bigquery/public-data)
- [FastMCP Documentation](https://github.com/modelcontextprotocol/python-sdk)
