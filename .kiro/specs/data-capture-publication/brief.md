# Brief: data-capture-publication

## Problem
After a test run, measurement results exist only in the terminal or a local file. There's no way to accumulate data over time, across locations and devices, or share results with others. The tool is useful as a one-shot diagnostic but can't be used for trend analysis or fleet monitoring.

## Current State
- `--json` flag saves results to a local file
- `--location` / `--detect-location` adds IP-based geolocation to results
- No user or device identity fields in any output
- No remote publication — data stays on the machine that ran the test

## Desired Outcome
Every test run:
1. Always saves a structured JSON record locally (offline-safe backup)
2. Optionally publishes that record as a new row in a Notion database
3. Each record contains: timestamp, GPS/location (lat, lng, city, country), user identity, device info (hostname, OS, platform), and all measurements (latency, packet loss, jitter, WiFi stability score, etc.)

Users can then browse, filter, and analyse all their historical runs directly in Notion.

## Approach
**A + C: Notion database rows + local JSON backup**

- Use `notion-client` (v3.1.0, MIT, actively maintained) to POST one page per run to a user-configured Notion database
- Always write a local JSON file first (resilience — Notion failure never aborts the test or loses data)
- Configuration via env vars: `NOTION_TOKEN` + `NOTION_DATABASE_ID`; optional `--publish` flag to enable/disable push
- Notion database schema is documented; user creates it once (or we provide a template page)

## Scope
- **In**:
  - Structured telemetry record schema (all fields defined, versioned)
  - Local JSON output always written (replaces/extends current `--json` behaviour)
  - Notion database row creation via `notion-client`
  - User identity field (`--user` CLI flag or `NETPROBE_USER` env var)
  - Device metadata collection (hostname, OS, platform, Python version)
  - Timestamp (ISO 8601, UTC) added to every record
  - GPS = IP-based geolocation (lat/lng, city, country) — already partially exists
  - Notion error handling: failure logged, test result still saved locally
  - Setup documentation: how to create the Notion integration + database schema
- **Out**:
  - True hardware GPS (not available on standard laptops/desktops)
  - Notion page creation (pages per run) — rows in a database only
  - Other publication targets (InfluxDB, webhooks, S3, etc.) — out of scope for this spec
  - Historical data migration of past runs
  - Real-time streaming (one publish per completed run, not per sample)

## Boundary Candidates
- **Telemetry record schema**: defines all fields and their types — independent of transport
- **Local persistence**: write JSON to disk (always-on)
- **Notion transport**: read config, build Notion properties dict, call API, handle errors

## Out of Boundary
- Visualisation or dashboards within the CLI tool itself
- Other cloud databases or integrations
- Authentication beyond a static integration token

## Upstream / Downstream
- **Upstream**: existing test runner in `netprobe.py`, `LocationManager`, `WiFiStabilityResult` — this spec consumes their outputs
- **Downstream**: future specs could add more publication targets (InfluxDB, webhook) or a dashboard view, reusing the same telemetry record schema

## Existing Spec Touchpoints
- **Adjacent**: `wifi-stability-score` (implemented) — its `WiFiStabilityResult` fields are included in the telemetry record; no changes needed to that spec

## Constraints
- `notion-client >= 3.0` (MIT, pip-installable, no transitive conflicts)
- Notion API rate limit: 3 req/s — irrelevant at one row per run
- Must not break existing `--json` flag behaviour (backwards-compatible or clearly documented change)
- Test suite must stay under 1 second (mock all Notion API calls)
