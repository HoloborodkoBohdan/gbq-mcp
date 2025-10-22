# Architecture Overview

## System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Client (LLM)                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastMCP Server (server.py)                  │
│                                                                 │
│  ┌─────────────── MCP Tools (5) ────────────────┐               │
│  │ • get_query_limits  • list_tables            │               │
│  │ • get_table_schema  • estimate_query_cost    │               │
│  │ • bq_query                                   │               │
│  └──────────────────────┬───────────────────────┘               │
│                         │                                       │
│  ┌─────────────── MCP Resources (4) ────────────┐               │
│  │ • bigquery://tables                          │               │
│  │ • bigquery://table/{id}/schema               │               │
│  │ • bigquery://datasets                        │               │
│  │ • bigquery://limits                          │               │
│  └──────────────────────┬───────────────────────┘               │
│                         │                                       │
│                         ▼                                       │
│                  ┌─────────────────┐                            │
│                  │  AppContext     │                            │
│                  │  (Dependency    │                            │
│                  │   Container)    │                            │
│                  └────────┬────────┘                            │
└───────────────────────────┼─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐  ┌─────────────────┐  ┌─────────────────┐
│Configuration  │  │ BigQueryClient  │  │ QueryValidator  │
│   Service     │  │    Service      │  │    Service      │
├───────────────┤  ├─────────────────┤  ├─────────────────┤
│ • .env loader │  │ • Initialize    │  │ • Composite     │
│ • access-ctrl │  │ • Get Client    │  │   Validators    │
│   .json       │  │ • Close         │  │ • SELECT Only   │
│ • QueryLimits │  │ • Project ID    │  │ • Forbidden KW  │
│ • Service Acc │  │                 │  │ • Multi-Stmt    │
└───────┬───────┘  └─────────────────┘  └─────────────────┘
        │
        ▼
┌─────────────────┐
│ AccessControl   │
│    Service      │
├─────────────────┤
│ • Composite     │
│   Strategies    │
│ • Table List    │
│ • Dataset List  │
│ • Patterns      │
└────────┬────────┘
         │
         ▼
┌──────────────────────────────┐
│     Google BigQuery API      │
│                              │
└──────────────────────────────┘
```

## Service Layer Architecture

### 1. Configuration Service (DIP)

```
┌──────────────────────────────────────┐
│   IConfigurationProvider (Interface) │
├──────────────────────────────────────┤
│ + get_access_config(): AccessConfig  │
│ + get_query_limits(): QueryLimits    │
│ + get_service_account_path(): str    │
└──────────────┬───────────────────────┘
               │
               │
               │                             
               ▼
┌──────────────────────────────────────────┐
│ ConfigurationService                     │
│ (File-based + Environment Variables)     │
├──────────────────────────────────────────┤
│ • Loads .env file with dotenv            │
│ • access-control.json for tables         │
│ • service-account.json for auth          │
│ • Environment variables:                 │
│   - ACCESS_CONTROL_FILE                  │
│   - MAX_QUERY_RESULTS                    │
│   - MAX_BYTES_BILLED_MB                  │
│   - GOOGLE_APPLICATION_CREDENTIALS       │
│ • Falls back to defaults if missing      │
└──────────────────────────────────────────┘
```

**Benefits:**
- Easy to swap config sources (file, env, database)
- Dependency Inversion: depend on interface, not implementation
- Single Responsibility: only manages configuration

### 2. Query Validator Service (OCP)

```
┌────────────────────────────────┐
│   IQueryValidator (Interface)  │
├────────────────────────────────┤
│ + validate(query): Result      │
└────────────┬───────────────────┘
             │
             ├──────────────┬──────────────┬──────────────┐
             │              │              │              │
             ▼              ▼              ▼              ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ SelectOnly      │ │ ForbiddenKW  │ │ MultiStmt    │ │   Custom     │
│  Validator      │ │  Validator   │ │  Validator   │ │  Validator   │
├─────────────────┤ ├──────────────┤ ├──────────────┤ ├──────────────┤
│ • Checks SELECT │ │ • Block      │ │ • No multi-  │ │ • To be      │
│   keyword       │ │   DELETE     │ │   statement  │ │   added      │
│ • Normalizes    │ │   UPDATE     │ │ • No SQL     │ │              │
│   query         │ │   DROP etc.  │ │   injection  │ │              │
└─────────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
             │              │              │              │
             └──────────────┴──────────────┴──────────────┘
                            │
                            ▼
             ┌──────────────────────────────┐
             │  CompositeQueryValidator     │
             ├──────────────────────────────┤
             │ • Runs all validators        │
             │ • Returns first failure      │
             │ • Extensible (add_validator) │
             └──────────────────────────────┘
```

**Benefits:**
- Open/Closed: Add new validators without modifying existing
- Single Responsibility: Each validator has one job
- Composite Pattern: Combine validators easily

### 3. Access Control Service (Strategy Pattern)

```
┌────────────────────────────────┐
│   IAccessStrategy (Interface)  │
├────────────────────────────────┤
│ + is_allowed(table): bool      │
└────────────┬───────────────────┘
             │
             ├──────────────┬──────────────┬──────────────┐
             │              │              │              │
             ▼              ▼              ▼              ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ ExplicitTable   │ │   Dataset    │ │   Pattern    │ │   Custom     │
│ AccessStrategy  │ │AccessStrategy│ │AccessStrategy│ │  Strategy    │
├─────────────────┤ ├──────────────┤ ├──────────────┤ ├──────────────┤
│ • Whitelist     │ │ • Dataset    │ │ • Wildcard   │ │ • Time-based │
│   specific      │ │   level      │ │   matching   │ │ • User-based │
│   tables        │ │ • Blacklist  │ │ • fnmatch    │ │ • Custom     │
│ • Exact match   │ │   tables     │ │   patterns   │ │   logic      │
└─────────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
             │              │              │              │
             └──────────────┴──────────────┴──────────────┘
                            │
                            ▼
             ┌──────────────────────────────┐
             │  CompositeAccessStrategy     │
             ├──────────────────────────────┤
             │ • OR logic across strategies │
             │ • Extensible (add_strategy)  │
             │ • Flexible access control    │
             └──────────────────────────────┘
```

**Benefits:**
- Strategy Pattern: Different access control modes
- Open/Closed: Add new strategies without modification
- Single Responsibility: Each strategy has one access rule

### 4. BigQuery Client Service (SRP)

```
┌────────────────────────────────┐
│   IBigQueryClient (Interface)  │
├────────────────────────────────┤
│ + get_client(): Client         │
│ + close(): void                │
└────────────┬───────────────────┘
             │
             ▼
┌────────────────────────────────┐
│  BigQueryClientService         │
├────────────────────────────────┤
│ • initialize()                 │
│ • get_client()                 │
│ • get_project_id()             │
│ • close()                      │
├────────────────────────────────┤
│ Dependencies:                  │
│  • IConfigurationProvider      │
│                                │
│ Manages:                       │
│  • Client lifecycle            │
│  • Credentials                 │
│  • Project ID                  │
│  • Resource cleanup            │
└────────────────────────────────┘
```

**Benefits:**
- Single Responsibility: Only manages client lifecycle
- Dependency Inversion: Depends on config interface
- Resource management: Proper cleanup

## Data Flow

### Query Execution Flow

```
User Request
    │
    ▼
┌────────────────────────┐
│ bq_query(query, limit) │  ← MCP Tool
└───────┬────────────────┘
        │
        │  1. Get Context
        ▼
┌────────────────────────┐
│   AppContext           │
│   (Services Container) │
└───────┬────────────────┘
        │
        │  2. Validate Query
        ▼
┌─────────────────────────────┐
│ QueryValidatorService       │
│  • SELECT only?             │
│  • No forbidden keywords?   │
│  • Single statement?        │
└───────┬─────────────────────┘
        │
        │  3. Check Access
        ▼
┌─────────────────────────────┐
│ AccessControlService        │
│  • Extract tables           │
│  • Check each table         │
│    - Whitelist?             │
│    - Dataset allowed?       │
│    - Pattern match?         │
└───────┬─────────────────────┘
        │
        │  4. Get Client
        ▼
┌─────────────────────────────┐
│ BigQueryClientService       │
│  • Return initialized       │
│    BigQuery client          │
└───────┬─────────────────────┘
        │
        │  5. Execute Query
        ▼
┌─────────────────────────────┐
│ Google BigQuery API         │
│  • Run query                │
│  • Return results           │
└───────┬─────────────────────┘
        │
        │  6. Format Response
        ▼
┌─────────────────────────────┐
│ Return to MCP Client        │
│  • total_rows               │
│  • returned_rows            │
│  • rows[]                   │
│  • bytes_processed          │
└─────────────────────────────┘
```

## Testing Strategy

```
Unit Tests
    │
    ├─► ConfigurationService
    │   └─ Test config loading
    │
    ├─► QueryValidatorService
    │   ├─ Test SELECT only
    │   ├─ Test forbidden keywords
    │   └─ Test multi-statement
    │
    ├─► AccessControlService
    │   ├─ Test whitelist
    │   ├─ Test dataset access
    │   └─ Test patterns
    │
    └─► BigQueryClientService
        └─ Test initialization

Integration Tests
    │
    └─► server_refactored.py
        ├─ Test tool execution
        ├─ Test error handling
        └─ Test end-to-end flow
```

## Extension Points

Want to extend the system? Here's where to add new features:

### 1. Add New Validator

```python
# services/query_validator.py
class RateLimitValidator(IQueryValidator):
    def validate(self, query: str) -> ValidationResult:
        # Your rate limiting logic
        pass

# Add to composite
validator.add_validator(RateLimitValidator())
```

### 2. Add New Access Strategy

```python
# services/access_control.py
class UserBasedAccessStrategy(IAccessStrategy):
    def is_allowed(self, table_ref: TableReference) -> bool:
        # Check user permissions
        pass

# Add to access control
access_control._strategy.add_strategy(UserBasedAccessStrategy())
```

### 3. Add New Configuration Source

```python
# services/configuration.py
class DatabaseConfigurationService(IConfigurationProvider):
    def get_access_config(self) -> AccessConfig:
        # Load from database
        pass

# Use in server
config = DatabaseConfigurationService()
```

## Performance Considerations

- **Lazy Initialization**: BigQuery client initialized only when needed
- **Validation First**: Quick validation before expensive API calls
- **Composite Pattern**: Early exit on first validation failure
- **Strategy Pattern**: Efficient OR logic across access strategies

## Security Layers

```
Request
  │
  ▼
[1] Query Validation
  │  • SELECT only
  │  • No forbidden keywords
  │  • Single statement
  ▼
[2] Access Control
  │  • Table whitelist
  │  • Dataset rules
  │  • Pattern matching
  ▼
[3] BigQuery Limits
  │  • Max 10,000 rows
  │  • 100 MB billing limit
  ▼
[4] BigQuery Permissions
  │  • Service account IAM
  │  • Project permissions
  ▼
Execute Query
```