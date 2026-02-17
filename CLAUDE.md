# CLAUDE.md

## Project Overview

**CNPJ Dados Abertos** is a high-performance ETL (Extract, Transform, Load) pipeline that automates downloading, processing, and loading Brazilian CNPJ (business registration) public data from Receita Federal do Brasil into PostgreSQL.

The primary language is **Portuguese (Brazilian)** — variable names, comments, logs, SQL, and docs are all in pt-BR.

## Tech Stack

- **Language:** Python >= 3.10
- **Package Manager:** Poetry (pyproject.toml, poetry.lock)
- **Database:** PostgreSQL 16 (via psycopg2-binary)
- **Configuration:** pydantic-settings (loads from `.env`)
- **Data Processing:** pandas (chunked reading), pandera (validation)
- **Containerization:** Docker + docker-compose

## Project Structure

```
├── main.py                  # Pipeline orchestrator (entry point)
├── pyproject.toml           # Poetry dependencies and project metadata
├── poetry.lock              # Locked dependency versions
├── Dockerfile               # Container definition (python:3.10-slim)
├── docker-compose.yml       # PostgreSQL 16 + app services
├── .env.example             # Environment variable template
├── src/
│   ├── __init__.py
│   ├── settings.py          # Pydantic config, enums, state persistence
│   ├── check_update.py      # WebDAV polling for new data versions
│   ├── downloader.py        # Multi-threaded ZIP file downloader
│   ├── extract_files.py     # Parallel ZIP extraction with security checks
│   ├── consolidate_csv.py   # Merges multi-part CSVs into single files
│   ├── database_loader.py   # PostgreSQL COPY STDIN bulk loader + constraints
│   ├── schema.sql           # DDL: table definitions (UNLOGGED by default)
│   └── constraints.sql      # PKs, FKs, indexes, orphan cleanup, auto-repair
├── tests/
│   └── __init__.py          # Test directory (no tests implemented yet)
└── docs/
    ├── descricao-dados.md   # Data field descriptions
    └── diagrama_er.md       # Entity-relationship diagram
```

### Generated directories (gitignored)

- `data/` — downloaded ZIPs, extracted CSVs, `state.json`
- `logs/` — `cnpj.log` file

## Pipeline Architecture

The pipeline runs sequentially through 6 stages. State is persisted to `data/state.json` so any failed step can be resumed without restarting from scratch.

```
CHECK → DOWNLOAD → EXTRACT → CONSOLIDATE → LOAD → CONSTRAINTS
```

| Stage | Module | Description |
|---|---|---|
| CHECK | `check_update.py` | Polls Receita Federal WebDAV for new data versions |
| DOWNLOAD | `downloader.py` | Multi-threaded download (max 4 workers) of ZIP files |
| EXTRACT | `extract_files.py` | Parallel ZIP extraction (2 processes) with path-traversal protection |
| CONSOLIDATE | `consolidate_csv.py` | Binary concatenation of multi-part CSVs into single files per table |
| LOAD | `database_loader.py` | Chunked pandas reading → PostgreSQL `COPY FROM STDIN` bulk insert |
| CONSTRAINTS | `database_loader.py` | Applies PKs, FKs, indexes; auto-repairs missing domain records; deletes orphans |

## How to Run

### Local

```bash
poetry install
cp .env.example .env  # Edit with your PostgreSQL credentials
poetry run python main.py          # Normal run (resumes from last state)
poetry run python main.py --force  # Ignores state, runs everything
```

### Individual modules

```bash
poetry run python -m src.check_update
poetry run python -m src.downloader
poetry run python -m src.extract_files
poetry run python -m src.consolidate_csv
poetry run python -m src.database_loader
```

### Docker

```bash
docker-compose up
```

## Configuration

All configuration is via environment variables (`.env` file) loaded by pydantic-settings in `src/settings.py`.

**Required:**
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_DATABASE`

**Key optional settings:**
- `RFB_BASE_URL` — Receita Federal WebDAV base URL
- `RFB_TOKEN` — authentication token for WebDAV
- `CHUNK_SIZE` (default: 200,000) — pandas chunk size for memory control
- `MAX_WORKERS` (default: 4) — concurrent download threads
- `EXTRACT_WORKERS` (default: 2) — parallel extraction processes
- `USE_UNLOGGED` (default: true) — create tables without WAL for fast writes
- `SET_LOGGED_AFTER_COPY` (default: true) — convert to LOGGED tables after load
- `SKIP_CONSTRAINTS` (default: false) — skip PK/FK/index creation
- `FILE_ENCODING` (default: latin1) — source CSV encoding
- `LOG_LEVEL` (default: INFO)

## Database Schema

9 tables across two groups:

**Domain tables** (reference/lookup):
- `paises`, `municipios`, `qualificacoes_socios`, `naturezas_juridicas`, `cnaes`

**Main tables:**
- `empresas` — business entities (PK: `cnpj_basico`)
- `estabelecimentos` — branches/locations (PK: `cnpj_basico, cnpj_ordem, cnpj_dv`)
- `socios` — partners/shareholders (FK to empresas, no PK)
- `simples` — small business tax regime (PK: `cnpj_basico`)

Tables are created as `UNLOGGED` (no WAL) during loading for performance, then converted to `LOGGED` after the load completes.

## Key Design Decisions

1. **UNLOGGED tables** — Skip WAL during bulk load for speed; convert back after.
2. **Constraints deferred** — All PKs, FKs, and indexes are applied AFTER data loading to maximize COPY throughput.
3. **Auto-repair of missing domain codes** — Source data has referential integrity issues. The `constraints.sql` inserts placeholder records ("NÃO INFORMADO NA ORIGEM") for missing parent codes before applying FKs.
4. **Orphan deletion** — Child records referencing nonexistent `cnpj_basico` in `empresas` are deleted before FK application.
5. **`cnae_fiscal_secundaria` as `TEXT[]`** — Stored as a PostgreSQL native array rather than a normalized junction table, for performance.
6. **State persistence** — `data/state.json` tracks the current pipeline stage and status, enabling resume-from-failure.
7. **Idempotent constraints** — All constraint DDL uses `IF NOT EXISTS` checks for safe re-execution.

## Code Conventions

- **Language:** All code comments, variable names, log messages, and SQL are in Portuguese (pt-BR).
- **Configuration:** All settings go through `src/settings.py` using pydantic-settings. Never hardcode config values.
- **Global singletons:** `settings` and `state` are instantiated once at module level in `settings.py` and imported throughout.
- **Logging:** Use Python's `logging` module. Get loggers via `logging.getLogger("module_name")`. Log messages use emoji prefixes for visibility.
- **SQL files:** Schema DDL lives in `src/schema.sql`, constraints in `src/constraints.sql`. Keep SQL separate from Python.
- **Error handling:** Pipeline steps catch exceptions, update state to FAILED, and exit. The orchestrator in `main.py` handles the control flow.
- **Commit style:** Conventional commits (`fix:`, `feat:`, `refactor:`, `chore:`).

## Testing

The `tests/` directory exists but has no tests yet. No test framework is configured in `pyproject.toml`.

## Common Tasks for AI Assistants

### Adding a new pipeline step
1. Add the step to the `PipelineStep` enum in `src/settings.py`
2. Create the module in `src/` with a `run_<name>()` entry function
3. Register it in `PIPELINE_MAP` in `main.py`
4. The state system (`should_skip`) uses enum ordering — place the new step in the correct position

### Adding a new database table
1. Add the DDL to `src/schema.sql` (follow existing UNLOGGED pattern)
2. Add constraints/indexes to `src/constraints.sql` (use `IF NOT EXISTS` pattern)
3. Add the loader logic in `src/database_loader.py` following existing table patterns

### Modifying configuration
1. Add the field to the `Settings` class in `src/settings.py` with a `Field()` descriptor
2. Update `.env.example` with the new variable
3. Access via the global `settings` instance

### Data integrity issues
- Source data from Receita Federal frequently has referential integrity problems
- The `constraints.sql` auto-repair section handles this — extend it for new tables
- Never assume source data is clean; always account for missing/malformed records
