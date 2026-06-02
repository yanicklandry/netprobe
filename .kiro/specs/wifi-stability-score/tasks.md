# Implementation Plan

- [x] 1. Define shared data types
- [x] 1.1 Add `WiFiSample` and `WiFiStabilityResult` typed dictionaries to `netprobe.py`
  - Add `WiFiSample` TypedDict with fields: `timestamp` (float), `rssi_dbm` (int), `noise_dbm` (int), `snr_db` (int)
  - Add `WiFiStabilityResult` TypedDict with fields: `wifi_stability_score` (Optional[int]), `wifi_score_type` (str: "hardware" | "behavior-only" | "unavailable"), `wifi_samples` (List[WiFiSample]), `avg_snr_db` (Optional[float])
  - Place type definitions after existing imports, before `ConnectionTester` class
  - Observable: both TypedDicts can be instantiated and passed between `WiFiSampler`, `StatisticsCalculator`, and `Reporter` without runtime errors
  - _Requirements: 1.2, 2.2, 4.1_

- [x] 2. Build WiFi hardware sampler
- [x] 2.1 (P) Implement `WiFiSampler` class with platform guard and connection detection
  - Add `WiFiSampler.__init__(interval_seconds: int = 5)` storing interval and initializing empty sample list and stop event
  - Implement `_is_wifi_connected() -> bool` using `networksetup -getinfo Wi-Fi` subprocess call; return `False` if output lacks an IP address or if the subprocess call fails
  - Implement `start()`: check `platform.system() == "Darwin"` first (no-op if not macOS, requirement 1.6); then call `_is_wifi_connected()` (no-op if not WiFi, requirement 1.4); otherwise start background daemon thread
  - Implement `stop()`: set stop event, join thread with 2-second timeout, log warning if timeout exceeded
  - Implement `get_samples() -> List[WiFiSample]`: return collected samples list (safe to call only after `stop()`)
  - Observable: `WiFiSampler.start()` on macOS WiFi launches exactly one thread; `stop()` joins it; `get_samples()` returns a list (possibly empty) without error; `start()` is a no-op on Linux without raising
  - _Requirements: 1.1, 1.3, 1.4, 1.6_
  - _Boundary: WiFiSampler_

- [x] 2.2 (P) Implement `WiFiSampler` signal parsing and sample loop
  - Implement `_parse_output(output: str) -> Optional[WiFiSample]`: use regex `Signal / Noise: (-?\d+) dBm / (-?\d+) dBm` to extract RSSI and noise; compute `snr_db = rssi_dbm - noise_dbm`; return `None` on no match
  - Implement `_sample_loop()`: loop while stop event not set; call `subprocess.run(["system_profiler", "SPAirPortDataType"])` with 10s timeout; on success pass output to `_parse_output()`; if result is not None append `WiFiSample`; on failure or parse error log warning and continue; sleep `interval_seconds` between calls
  - Observable: given mocked `system_profiler` output `"Signal / Noise: -68 dBm / -97 dBm"`, `_parse_output()` returns `WiFiSample` with `rssi_dbm=-68`, `noise_dbm=-97`, `snr_db=29`; given malformed output, returns `None` without raising
  - _Requirements: 1.2, 1.5_
  - _Boundary: WiFiSampler_

- [ ] 3. Build WiFi stability score calculator
- [ ] 3.1 (P) Implement hardware-backed score path
  - Add static method `calculate_wifi_stability_score(samples, latency_stats, jitter_stats, packet_loss_stats) -> WiFiStabilityResult` to `StatisticsCalculator`
  - Hardware path (len(samples) >= 1): start from 100; apply SNR level penalties (-40 if avg SNR < 10 dB, -20 if < 20 dB, -10 if < 30 dB); apply SNR variance penalty only when len(samples) >= 2 (-20 if std_dev > 10, -10 if > 5, -5 if > 2); apply latency CoV penalty (CoV = std_dev/mean, guard for mean=0; -15 if CoV > 0.5, -7 if > 0.2); apply jitter std_dev penalty (-10 if > 10ms, -5 if > 5ms); clamp to [0, 100]
  - Compute `avg_snr_db` as mean of all snr_db values in samples
  - Return `WiFiStabilityResult` with `wifi_score_type="hardware"` and `avg_snr_db` populated
  - Observable: with 3 samples having SNR of 25/27/26 dB and stable latency/jitter, method returns integer score between 85–100 with type "hardware" and avg_snr_db ≈ 26.0
  - _Requirements: 2.1, 2.2, 2.4, 2.5_
  - _Boundary: StatisticsCalculator_

- [ ] 3.2 (P) Implement behavior-only and unavailable score paths
  - Behavior-only path (len(samples) == 0, latency/jitter/packet_loss stats available): start from 100; apply packet loss penalties (-30 if avg > 1%, -15 if > 0.1%); apply latency CoV penalties (-20 if CoV > 0.5, -10 if > 0.2); apply jitter std_dev penalties (-20 if > 15ms, -10 if > 8ms); clamp to [0, 100]; return with `wifi_score_type="behavior-only"`, `avg_snr_db=None`, `wifi_samples=[]`
  - Unavailable path (len(samples) == 0 and no usable behavior stats): return `WiFiStabilityResult` with `wifi_stability_score=None`, `wifi_score_type="unavailable"`, `avg_snr_db=None`, `wifi_samples=[]`
  - Observable: with empty samples and jitter std_dev of 20ms, method returns behavior-only score below 80; with empty samples and empty stats, returns score=None and type="unavailable"
  - _Requirements: 2.3, 2.4_
  - _Boundary: StatisticsCalculator_

- [ ] 4. Wire sampler into test run
- [ ] 4.1 Integrate `WiFiSampler` into `ConnectionTester.run_extended_test()`
  - Instantiate `WiFiSampler(interval_seconds=5)` before the test loop begins; call `sampler.start()`
  - After the test loop completes (before `calculate_statistics()`), call `sampler.stop()` and store the result of `sampler.get_samples()` in `self.results['wifi_samples']`
  - After `StatisticsCalculator.calculate_statistics()` runs, call `StatisticsCalculator.calculate_wifi_stability_score()` with the wifi_samples and the returned latency/jitter/packet_loss stats; store the resulting `WiFiStabilityResult` in `self.results['wifi_stability']`
  - Ensure `sampler.stop()` is called even if the test loop raises (use try/finally if needed)
  - Observable: after a test run with mocked network calls, `results['wifi_stability']` is present and is a dict with keys `wifi_stability_score`, `wifi_score_type`, `wifi_samples`, `avg_snr_db`
  - _Depends: 2.1, 2.2, 3.1, 3.2_
  - _Requirements: 1.1, 1.3, 2.1_
  - _Boundary: ConnectionTester_

- [ ] 5. Extend Reporter with wifi stability output and exports
- [ ] 5.1 Display `wifi_stability_score` in terminal summary
  - In `Reporter.print_summary()`, after the existing `quality_score` display block, read `results.get('wifi_stability')`
  - If `wifi_score_type == "unavailable"` or wifi_stability is absent: print `WiFi Stability Score: N/A`
  - If `wifi_score_type == "hardware"`: print `WiFi Stability Score: {score}/100 ({rating}) | Avg SNR: {snr:.1f} dB` using same rating band logic as quality_score (≥90 Excellent, ≥80 Good, ≥70 Fair, <70 Poor)
  - If `wifi_score_type == "behavior-only"`: print `Connection Stability Score (behavior only): {score}/100 ({rating})`
  - Observable: terminal output after a mocked test run includes exactly one wifi stability score line with the correct label and rating word; score=None case prints "N/A" without crashing
  - _Depends: 1.1, 4.1_
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  - _Boundary: Reporter_

- [ ] 5.2 (P) Add wifi fields to JSON export
  - In `Reporter.export_json()`, merge four fields from `results.get('wifi_stability', {})` into the JSON output dict: `wifi_stability_score` (int or null), `wifi_score_type` (string), `wifi_samples` (list, default `[]`), `avg_snr_db` (float or null)
  - When wifi_stability is absent from results, write all four fields with their null/empty defaults
  - Observable: exported JSON file contains all four wifi keys; `wifi_samples` is a JSON array (empty or with sample objects each having `timestamp`, `rssi_dbm`, `noise_dbm`, `snr_db`)
  - _Requirements: 4.1, 4.3_
  - _Boundary: Reporter_

- [ ] 5.3 (P) Add wifi data to CSV export
  - In `Reporter.export_csv()`, add `wifi_stability_score` as a column in the summary row header and value
  - After the existing latency sample rows, write a WiFi samples section with header `wifi_timestamp,rssi_dbm,noise_dbm,snr_db` followed by one row per entry in `wifi_samples`; write no rows (but still write the header) when `wifi_samples` is empty
  - Observable: exported CSV file includes `wifi_stability_score` in the summary header; CSV contains a WiFi samples section (even if empty) with four columns; sample rows match the `WiFiSample` typed structure
  - _Requirements: 4.2_
  - _Boundary: Reporter_

- [ ] 6. Unit and integration tests
- [ ] 6.1 (P) Implement `TestWiFiSampler` unit tests
  - `test_parse_output_valid`: mock `system_profiler` text with `"Signal / Noise: -68 dBm / -97 dBm"`; assert `rssi_dbm=-68`, `noise_dbm=-97`, `snr_db=29`
  - `test_parse_output_invalid`: pass `"no signal data here"`; assert return is `None`, no exception raised
  - `test_is_wifi_connected_false_on_non_wifi`: mock `networksetup` output without IP address; assert `_is_wifi_connected()` returns `False`
  - `test_start_noop_on_non_macos`: mock `platform.system()` to return `"Linux"`; call `start()`; assert no thread is created (thread list length unchanged)
  - `test_stop_after_start_returns_samples`: mock `subprocess.run` to return valid signal output; call `start()` then immediately `stop()`; assert `get_samples()` returns a list (even if empty) without error
  - Observable: all 5 `TestWiFiSampler` tests pass; no real `system_profiler`, `networksetup`, or thread I/O invoked
  - _Requirements: 5.1, 5.2, 1.4, 1.5, 1.6_
  - _Boundary: WiFiSampler_

- [ ] 6.2 (P) Implement `TestWiFiStabilityScore` unit tests
  - `test_hardware_path_multiple_samples`: pass 3 `WiFiSample` dicts with SNR ~26 dB and stable latency/jitter stats; assert score is int in [0, 100] and `wifi_score_type == "hardware"`
  - `test_hardware_single_sample_no_variance_penalty`: pass 1 sample; assert score is higher than the multi-sample score with high variance (variance penalty absent)
  - `test_behavior_only_path`: pass empty samples list with populated latency/jitter/packet_loss stats; assert `wifi_score_type == "behavior-only"`, score is int
  - `test_unavailable_path`: pass empty samples and empty stat dicts; assert `wifi_stability_score is None`, `wifi_score_type == "unavailable"`
  - `test_independence_from_quality_score`: call both `calculate_statistics()` and `calculate_wifi_stability_score()` on the same inputs; assert `quality_score` value is identical before and after wifi score calculation
  - Observable: all 5 `TestWiFiStabilityScore` tests pass with only stdlib mocking (no subprocess calls)
  - _Requirements: 5.3, 2.4, 2.5_
  - _Boundary: StatisticsCalculator_

- [ ] 6.3 Integration tests connecting sampler, calculator, and reporter
  - `test_full_run_includes_wifi_result`: patch `WiFiSampler.get_samples` to return 2 `WiFiSample` dicts; run full mocked `ConnectionTester` test; assert `results['wifi_stability']` is present, `wifi_stability_score` is an int, `wifi_score_type == "hardware"` (patches at the `WiFiSampler.get_samples` boundary, not at subprocess level)
  - `test_json_export_includes_wifi_fields`: mock a complete test run result with wifi_stability populated; call `Reporter.export_json()`; assert output JSON contains all four keys (`wifi_stability_score`, `wifi_score_type`, `wifi_samples`, `avg_snr_db`)
  - `test_csv_export_includes_wifi_score`: same mock result; call `Reporter.export_csv()`; assert `wifi_stability_score` appears in CSV content and WiFi sample header row is present
  - Observable: all 3 integration tests pass; no real network or system_profiler calls made; `results['wifi_stability']` structure validated end-to-end
  - _Depends: 6.1, 6.2_
  - _Requirements: 5.4, 4.1, 4.2, 4.3_
  - _Boundary: ConnectionTester, Reporter_

- [ ] 6.4 Verify full test suite timing and mock hygiene
  - Run the complete test suite (`./test.py`) and confirm it completes in under 1 second
  - Confirm no test makes a real network call, DNS call, subprocess call to `system_profiler`, or call to `networksetup` (inspect mock patch decorators on all new tests)
  - If suite exceeds 1 second, identify the slow test and add missing mock
  - Observable: `./test.py` output shows all tests passing with total elapsed time < 1.0 seconds; no `PermissionError` or `subprocess.TimeoutExpired` from unmocked calls
  - _Requirements: 5.4_

## Implementation Notes
- Task 2.1/2.2: WiFiSampler thread tests use real 2s join timeouts — task 6.4 must mock threading.Thread or reduce timeout in tests to keep suite under 1s.
