# Implementation Plan

- [ ] 1. Install Notion dependency
- [x] 1.1 Add notion-client to Pipfile and verify it resolves cleanly
  - Add `notion-client = ">=3.0"` under `[packages]` in `Pipfile`
  - Run `pipenv install` to regenerate `Pipfile.lock` without conflicts
  - `pipenv run python -c "import notion_client; print(notion_client.__version__)"` exits with version printed
  - _Requirements: 4.1_

- [ ] 2. Create data_capture.py with leaf components
- [x] 2.1 Create data_capture.py and implement device info, user identity, and Notion config
  - Create `data_capture.py` at the project root with all stdlib imports and type annotations matching design.md contracts
  - Implement `DeviceInfo.collect()` returning `{'hostname', 'os', 'platform', 'python_version'}` using `socket`, `platform`, `sys`; fall back to empty strings on any collection error without raising
  - Implement `resolve_user(cli_user)`: return `cli_user` if non-empty, else `os.environ.get('NETPROBE_USER', '')`, empty string when neither is set
  - Implement `NotionConfig` dataclass with `token: str` and `database_id: str`, plus `from_env()` returning `None` when either `NOTION_TOKEN` or `NOTION_DATABASE_ID` is absent
  - `python -c "from data_capture import DeviceInfo, resolve_user, NotionConfig; print(DeviceInfo.collect())"` prints all four device keys without error
  - _Requirements: 2.3, 3.1, 3.2, 3.3, 3.4, 4.2_

- [ ] 3. Canonical run record builder
- [x] 3.1 Implement RunRecord.build() with all measurement fields and per-key location emission
  - Build a flat `dict` with: `timestamp` (ISO 8601 UTC via `datetime.now(timezone.utc).isoformat()`), `user`, device fields from `DeviceInfo.collect()`, `test_scenario`, and all measurements using chained defensive `.get()` per the source map in design.md (including the nested `results['bandwidth']` and `results['wifi_stability']` paths)
  - Emit location fields only when `results.get('location')` is a dict without an `error` key and with a non-`None` `latitude`; emit each of `location_name`, `latitude`, `longitude`, `city`, `country` only when that specific key is present and non-`None`
  - A `--detect-location` location dict (has `city`/`country`, no `name`) emits `latitude/longitude/city/country` but not `location_name`; a `--location` dict (has `name`, no `city/country`) emits `location_name/latitude/longitude` but not `city/country`; absent, error, or no-`latitude` dicts produce zero location keys in the record
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [ ] 4. Local JSONL log writer
- [x] 4.1 Implement LocalLogWriter with append-only JSONL semantics
  - `LocalLogWriter(path: str)` stores the target path; `append(record: dict) -> bool` opens the file in append mode (`'a'`), writes `json.dumps(record) + '\n'`, and returns `True`
  - Creates the file when it does not exist; does not truncate or rewrite existing lines
  - Catches `OSError`/`IOError` and returns `False` without raising so the caller can warn and continue
  - Writing two records sequentially to a fresh temp file produces exactly two lines, each parseable as independent JSON objects with no prior content modified
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [ ] 5. Notion publisher
- [x] 5.1 Implement NotionPublisher with lazy import and graceful failure
  - `NotionPublisher(config: NotionConfig)` stores config; `publish(record: dict) -> PublishOutcome` lazily imports `notion_client`, constructs `Client(auth=config.token)`, and calls `client.pages.create(parent={"database_id": config.database_id}, properties={...})` with the full property mapping from design.md (title, date, rich_text, number types)
  - Define `PublishOutcome` as a dataclass with `ok: bool` and `error: str | None`
  - Map optional location fields (`location_name`, `city`, `country`) only when present in the record; omit those Notion properties entirely when absent
  - Catches `notion_client.APIResponseError`, transport/timeout errors, and `ImportError`; returns `PublishOutcome(ok=False, error=<message>)` without raising in any error path
  - With a mocked `notion_client.Client`, `publish({...complete record...})` returns `PublishOutcome(ok=True)` and `client.pages.create` was called once with the correct `database_id`
  - _Requirements: 4.1, 4.3, 4.4, 4.5, 5.2, 5.3_

- [ ] 6. Integration: orchestration and CLI wiring
- [x] 6.1 Implement record_run orchestration function in data_capture.py
  - `record_run(results, stats, user, log_path, publish, notion_config)` sequences: build record via `RunRecord.build()` → append locally via `LocalLogWriter(log_path).append(record)` → optionally publish
  - Always writes local log first; on success print `f"Log saved: {log_path}"`; on `False` return print an error line and continue to the publish step (1.5, 1.6)
  - When `publish=True` and `notion_config is None`: print a credentials-missing warning and skip; when `publish=False`: make no Notion calls (4.2, 4.4, 5.3)
  - When `publish=True` and publish succeeds: print a Notion confirmation line (5.2); when publish fails: print an API-error warning distinct from the credentials message (5.3)
  - Never raises to the caller; `record_run(...)` with `publish=False` and a writable temp path completes without error and the JSONL file contains exactly one valid JSON line
  - _Requirements: 1.5, 1.6, 4.2, 4.4, 5.1, 5.2, 5.3_

- [ ] 6.2 Wire CLI options and record_run call into netprobe.py
  - Add `--user` (string, default `None`), `--publish` (is_flag, default False), and `--log-file` (string, default `'netprobe-results.jsonl'`) Click options to `main()` and its parameter list
  - Resolve `user = resolve_user(user_flag)` and `notion_config = NotionConfig.from_env() if publish else None` once before the scenario loop
  - Call `record_run(results, stats, user=user, log_path=log_file, publish=publish, notion_config=notion_config)` inside the scenario loop after `stats = StatisticsCalculator.calculate_statistics(results)` and after location attachment (after line that sets `results['location']`)
  - `./netprobe.py --help` shows `--user`, `--publish`, and `--log-file` in the output; a short run with `--publish` disabled creates `netprobe-results.jsonl` in the working directory containing one JSON line
  - _Requirements: 1.1, 1.4, 3.1, 3.2, 4.4_

- [ ] 7. Tests
- [ ] 7.1 Unit tests for all data_capture components
  - `TestDeviceInfo`: `collect()` returns exactly the four keys (`hostname`, `os`, `platform`, `python_version`) as non-None strings
  - `TestResolveUser`: four precedence cases — flag only, env only (`NETPROBE_USER`), both (flag wins), neither (empty string) — patch `os.environ`
  - `TestNotionConfig`: `from_env()` returns `None` when either credential missing, returns a populated config when both present — patch `os.environ`
  - `TestRunRecord`: required keys present, `timestamp` is ISO 8601 UTC; three location shapes: `--detect-location` (city/country present, no location_name), `--location` (location_name present, no city/country), and absent/error/no-latitude (zero location keys)
  - `TestLocalLogWriter`: creates file when absent, two-call test produces two independent JSON lines without modifying the first, returns `False` on simulated `OSError` — use `tmp_path`
  - All new test classes pass; `./test.py` completes in under 1 second
  - _Requirements: 1.2, 1.3, 1.5, 2.1, 2.2, 2.3, 2.5, 2.6, 3.1, 3.2, 3.3, 3.4, 4.2_

- [ ] 7.2 Integration tests for record_run flows and NotionPublisher
  - `TestDataCaptureIntegration`: (a) `publish=False` writes one JSONL line and `NotionPublisher` is never constructed; (b) `publish=True` with mocked publisher returning `ok=True` appends locally and prints Notion confirmation; (c) `notion_config=None` prints credentials warning and no Notion call made; (d) mocked publisher returning `PublishOutcome(ok=False, error='...')` prints an API-error warning and the local log is still written
  - `TestNotionPublisher`: maps a full record to the documented properties and calls `pages.create` with the correct `database_id`; API-error path returns `PublishOutcome(ok=False)` without raising — mock lazily-imported `notion_client.Client`
  - All integration tests pass; no real network calls; `./test.py` still completes in under 1 second
  - _Requirements: 1.1, 1.6, 4.1, 4.3, 4.4, 5.1, 5.2, 5.3_
