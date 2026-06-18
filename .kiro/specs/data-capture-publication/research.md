# Research & Design Decisions

## Summary
- **Feature**: `data-capture-publication`
- **Discovery Scope**: Extension (one new external dependency: Notion)
- **Key Findings**:
  - NetProbe has no always-on persistence today; exports are opt-in (`--json`/`--csv`), overwrite-mode, and bypass `Reporter` in the multi-scenario `main()` path.
  - The natural integration seam is the per-scenario loop in `main()` (after `StatisticsCalculator.calculate_statistics`), where a complete `results` + `stats` pair exists for each run.
  - `notion-client` 3.1.0 (MIT, Python >=3.8) is current and matches the brief; the official SDK exposes `client.pages.create(parent={"database_id": ...}, properties={...})` for creating a database row.
  - No `--user` flag, env-var handling, or device-info collection exists in the Python engine yet — all must be added.

## Research Log

### Notion Python SDK
- **Context**: Brief selects `notion-client >= 3.0` for publishing each run as a Notion database row.
- **Sources Consulted**: PyPI `notion-client` metadata (v3.1.0, MIT, `>=3.8,<4`); Notion API reference for page creation.
- **Findings**:
  - Create a row with `client.pages.create(parent={"database_id": DB_ID}, properties={...})`.
  - Property values are typed objects: `title`, `date`, `number`, `select`, `rich_text`.
  - SDK raises `notion_client.APIResponseError` (auth, validation, rate limit) and `notion_client.errors.HTTPResponseError` / `RequestTimeoutError` for transport failures.
  - The SDK does not require reading the database schema to write a row; property names in the payload must match the target database's existing properties or the API returns a validation error.
- **Implications**: We map a fixed, documented set of record fields to Notion property names. We never read or mutate the schema (satisfies 4.5). A schema mismatch surfaces as an API error handled by 4.3.

### Existing persistence and integration seam
- **Context**: Determine where the always-on log write and optional publish should hook in.
- **Sources Consulted**: `netprobe.py` (`main()` L1516-1543, `Reporter.export_json` L1219-1243, `ConnectionTester.results` L171-180).
- **Findings**:
  - Each scenario iteration produces `results` (with `wifi_stability`, `location`, `test_scenario`, `vpn_status`) and `stats` (with `quality_score`, `latency_stats`, etc.).
  - `--compare-vpn` produces two scenarios = two completed runs in one invocation.
  - `results['location']` is present only when `--location`/`--detect-location` was used.
- **Implications**: One record is written per completed scenario run. The hook sits inside the loop after stats are computed, independent of the post-loop `--json`/`--csv` export.

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| New `data_capture.py` module | Self-contained domain (record build, local write, Notion publish, orchestration) | Mirrors `vpn_manager.py` / `network_isolation_detector.py`; clean boundary; testable in isolation | One new file | Selected |
| Inline in `netprobe.py` | Add classes/functions directly to the main file | No new file | Bloats a 1700-line file; weak boundary; harder to test | Rejected |
| Generic publisher registry | Pluggable backends (Notion, webhook, S3) | Future-proof | Speculative; out of scope (brief excludes other targets) | Rejected (simplification) |

## Design Decisions

### Decision: Local log format is JSONL (newline-delimited JSON)
- **Context**: 1.1-1.3 require appending one record per run without modifying or deleting prior records.
- **Alternatives Considered**:
  1. JSON array file — requires read-parse-append-rewrite of the entire file on every run.
  2. JSONL — append one serialized object per line.
- **Selected Approach**: JSONL. Each run appends a single line via file open in append mode.
- **Rationale**: True append (no rewrite) satisfies 1.3 directly, is crash-safe per line, and scales to many runs. Standard format for structured logs and trivially parseable for later analysis.
- **Trade-offs**: Not a single valid JSON document; consumers read line-by-line. Acceptable for a log/backup file.
- **Follow-up**: Default path `netprobe-results.jsonl` in the current working directory; overridable via `--log-file`.

### Decision: One canonical flat record consumed by both sinks
- **Context**: 1.x (local) and 4.1 (Notion) must contain the same fields.
- **Selected Approach**: `RunRecord.build(...)` produces one flat `dict`. `LocalLogWriter` serializes it as-is; `NotionPublisher` maps it to Notion properties. (Generalization lens.)
- **Rationale**: Single source of truth for the record schema; avoids drift between local and remote payloads.
- **Trade-offs**: Notion mapping must tolerate `None`/absent location fields.

### Decision: Lazy import of `notion-client`
- **Context**: Test suite must run without network and ideally without requiring the package; publish is optional.
- **Selected Approach**: Import `notion_client` inside `NotionPublisher` (function/constructor scope), not at module top.
- **Rationale**: `data_capture.py` imports cleanly even if the package is absent; only `--publish` paths need it; tests mock the client.
- **Trade-offs**: Import error surfaces at publish time → handled as a credentials/availability warning.

### Decision: Config via CLI flags + environment variables, no config file
- **Context**: 3.x (user identity) and 4.2 (Notion credentials).
- **Selected Approach**: `--user` flag with `NETPROBE_USER` fallback (flag wins); `NOTION_TOKEN` + `NOTION_DATABASE_ID` read from env; `--publish` flag gates remote calls.
- **Rationale**: Matches the brief; no new config-file machinery (simplification); secrets stay out of source.

## Risks & Mitigations
- **Notion schema mismatch** (property names/types differ from payload) — Mitigation: document the required database schema in README; treat mismatch as an API error (4.3) that warns and skips without aborting.
- **Local log write failure** (permissions, disk full) — Mitigation: catch and warn, never abort the run or block other exports (1.5).
- **Test suite slowdown / accidental network calls** — Mitigation: lazy import, mock the Notion client and filesystem (tmp paths); keep suite <1s per project rule.
- **Double records under `--compare-vpn`** — Intentional: one record per scenario run; `test_scenario` field disambiguates.

## References
- [notion-client on PyPI](https://pypi.org/project/notion-client/) — v3.1.0, MIT, Python `>=3.8,<4`.
- [Notion API: create a page](https://developers.notion.com/reference/post-page) — `parent.database_id` + typed `properties`.
