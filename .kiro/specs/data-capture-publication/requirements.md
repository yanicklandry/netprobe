# Requirements Document

## Project Description (Input)
After a test run, NetProbe measurement results exist only in the terminal or a local file — there is no way to accumulate data over time, across locations and devices, or share results with others. The tool is useful as a one-shot diagnostic but can't be used for trend analysis or fleet monitoring.

Every test run should: (1) always save a structured JSON record locally as an offline-safe backup, and (2) optionally publish that record as a new row in a Notion database. Each record must contain timestamp (ISO 8601 UTC), GPS/location (lat, lng, city, country via IP geolocation), user identity (--user flag or NETPROBE_USER env var), device info (hostname, OS, platform, Python version), and all measurements (latency, packet loss, jitter, WiFi stability score, SSID, etc.).

Users can then browse, filter, and analyse all their historical runs directly in Notion.

**Approach chosen**: Notion database rows + local JSON backup (notion-client >= 3.0, MIT licensed). Configuration via NOTION_TOKEN + NOTION_DATABASE_ID env vars; --publish flag to enable remote push. Notion failures are logged but never abort the test or lose local data.

**Out of scope**: true hardware GPS, Notion pages (rows only), other publication targets (InfluxDB/webhooks/S3), historical data migration, real-time streaming.

## Requirements
<!-- Will be generated in /kiro-spec-requirements phase -->
