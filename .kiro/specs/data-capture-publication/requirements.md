# Requirements Document

## Project Description (Input)
After a test run, NetProbe measurement results exist only in the terminal or a local file — there is no way to accumulate data over time, across locations and devices, or share results with others. The tool is useful as a one-shot diagnostic but can't be used for trend analysis or fleet monitoring.

Every test run should: (1) always save a structured JSON record locally as an offline-safe backup, and (2) optionally publish that record as a new row in a Notion database. Each record must contain timestamp (ISO 8601 UTC), GPS/location (lat, lng, city, country via IP geolocation), user identity (--user flag or NETPROBE_USER env var), device info (hostname, OS, platform, Python version), and all measurements (latency, packet loss, jitter, WiFi stability score, SSID, etc.).

Users can then browse, filter, and analyse all their historical runs directly in Notion.

**Approach chosen**: Notion database rows + local JSON backup (notion-client >= 3.0, MIT licensed). Configuration via NOTION_TOKEN + NOTION_DATABASE_ID env vars; --publish flag to enable remote push. Notion failures are logged but never abort the test or lose local data.

**Out of scope**: true hardware GPS, Notion pages (rows only), other publication targets (InfluxDB/webhooks/S3), historical data migration, real-time streaming.

## Requirements

### Requirement 1: Automatic Local Log

#### Acceptance Criteria
1. When a test run completes, NetProbe shall append one record to the local JSON log file without requiring any additional flags.
2. When the local JSON log file does not exist, NetProbe shall create it automatically.
3. When the local JSON log file already exists, NetProbe shall append the new record without modifying or deleting prior records.
4. The NetProbe shall use a default log file path in the current working directory when no log path is explicitly configured.
5. If writing the local log record fails (e.g., permission error, disk full), NetProbe shall display an error message and continue without aborting the process or affecting terminal output or other exports.
6. The NetProbe shall write the local log record before attempting any remote publication step.

### Requirement 2: Record Structure

#### Acceptance Criteria
1. The NetProbe shall include a `timestamp` field in each log record containing the run completion time in ISO 8601 UTC format.
2. The NetProbe shall include a `user` field in each log record containing the user-supplied identity value, or an empty string when no user identity is provided.
3. The NetProbe shall include device metadata in each log record: `hostname`, `os`, `platform`, and `python_version`.
4. The NetProbe shall include all measurement results in each log record: latency statistics, packet loss, jitter, DNS resolution time, bandwidth, WiFi stability score, WiFi SSID, and test scenario.
5. Where location data was collected during the run, NetProbe shall include `latitude`, `longitude`, `city`, and `country` fields in the log record.
6. If location data was not collected during the run, NetProbe shall omit location fields from the log record without treating it as an error.

### Requirement 3: User Identity

#### Acceptance Criteria
1. When the `--user` flag is provided, NetProbe shall use that value as the `user` field in the log record.
2. When `--user` is not provided and the `NETPROBE_USER` environment variable is set, NetProbe shall use the environment variable value as the `user` field.
3. When both `--user` and `NETPROBE_USER` are set, NetProbe shall use the `--user` value and ignore the environment variable.
4. When neither `--user` nor `NETPROBE_USER` is set, NetProbe shall write an empty string as the `user` field without displaying an error.

### Requirement 4: Notion Publication

#### Acceptance Criteria
1. Where `--publish` is enabled, when a test run completes, NetProbe shall create one new row in the configured Notion database containing the same fields as the local log record.
2. Where `--publish` is enabled and `NOTION_TOKEN` or `NOTION_DATABASE_ID` is absent, NetProbe shall display a warning message and skip the Notion publication step without aborting the process or affecting local log writing.
3. Where `--publish` is enabled and the Notion API call fails (network error, authentication error, rate limit, or other API error), NetProbe shall log the error details, skip the publication, and continue without aborting or retrying.
4. Where `--publish` is not enabled, NetProbe shall make no Notion API calls.
5. The NetProbe shall not create, modify, or validate the Notion database schema; the database must be pre-configured by the user before use.

### Requirement 5: User-Facing Feedback

#### Acceptance Criteria
1. When the local log record is successfully written, NetProbe shall display a brief confirmation line showing the log file path.
2. Where `--publish` is enabled and the Notion row is successfully created, NetProbe shall display a brief confirmation line indicating the Notion database.
3. Where `--publish` is enabled and publication is skipped or fails, NetProbe shall display a warning message that distinguishes between missing credentials and an API error.
