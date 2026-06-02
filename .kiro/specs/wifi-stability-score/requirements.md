# Requirements Document

## Introduction
netProbe currently produces a single `quality_score` (0–100) derived from latency, packet loss, jitter, and DNS resolution time. This score does not capture WiFi-specific stability: a connection with stable average latency but fluctuating radio signal will score misleadingly high, and users testing public WiFi (hotels, cafés) cannot tell whether poor performance stems from a weak WiFi signal or from network congestion.

This feature adds a dedicated `wifi_stability_score` (0–100) that combines WiFi hardware metrics (RSSI and SNR sampled over time on macOS) with network behavior variance (jitter standard deviation, latency coefficient of variation). The score appears alongside `quality_score` in the terminal summary and in JSON/CSV exports. On non-macOS platforms or non-WiFi connections, the feature degrades gracefully to a behavior-only score or `null`.

## Boundary Context
- **In scope**: WiFi signal sampling (RSSI, noise, SNR) via `system_profiler` on macOS; stability score computation; display in terminal summary; inclusion in JSON and CSV exports; graceful degradation for non-WiFi and non-macOS paths; unit test coverage with mocked system calls.
- **Out of scope**: Scanning neighboring access points or channel interference analysis; per-session historical tracking across runs; GUI/desktop app changes; modifications to the existing `quality_score` logic.
- **Adjacent expectations**: The sampler runs concurrently with the existing test loop without blocking it. The stability calculator consumes both sampler output and existing jitter/latency stats already produced by the current statistics pipeline.

## Requirements

### Requirement 1: WiFi Hardware Sampling

**Objective:** As a user running netProbe, I want the tool to collect WiFi signal metrics (RSSI, noise floor, SNR) at regular intervals during a test run, so that signal quality is captured as part of the stability measurement.

#### Acceptance Criteria
1. When a test run starts and the device is connected via WiFi on macOS, netProbe shall begin sampling RSSI (dBm), noise floor (dBm), and computed SNR (signal minus noise, in dB) at a fixed interval of 5 seconds in a background process that does not block the main test loop.
2. When a WiFi sample is collected, netProbe shall record it as a data point containing timestamp, RSSI (dBm), noise floor (dBm), and SNR (dB).
3. When the test run completes, netProbe shall stop the background sampler and make all collected samples available for score calculation.
4. If the device is not connected via WiFi (e.g., ethernet, VPN-only), netProbe shall skip hardware sampling and record zero WiFi samples without affecting other test results.
5. If the WiFi signal data source fails or returns unparseable output during a sample, netProbe shall log a warning, skip that sample, and continue sampling at the next interval.
6. Where the operating system is not macOS, netProbe shall skip hardware sampling entirely without raising an error or aborting the test.

### Requirement 2: WiFi Stability Score Calculation

**Objective:** As a user, I want a `wifi_stability_score` (0–100) that reflects both signal quality and temporal stability, so that I can quantify how reliable the WiFi connection was during the test.

#### Acceptance Criteria
1. When a test run completes with at least one WiFi hardware sample, netProbe shall compute `wifi_stability_score` using average SNR level, SNR variance across samples, and network behavior variance (jitter standard deviation, latency coefficient of variation).
2. The `wifi_stability_score` shall be an integer in the range 0–100, where higher values represent more stable connections.
3. When a test run completes with no WiFi hardware samples (non-WiFi connection or non-macOS platform), netProbe shall compute `wifi_stability_score` from network behavior variance only (jitter standard deviation, latency coefficient of variation, average packet loss) and mark the score type as behavior-only.
4. If fewer than 2 hardware samples are available, netProbe shall compute the score without applying a variance penalty (treating variance as zero for scoring purposes).
5. The `wifi_stability_score` shall be computed independently of `quality_score`; the addition of this feature shall not alter `quality_score` values.

### Requirement 3: Terminal Report Display

**Objective:** As a user reading the terminal summary, I want to see `wifi_stability_score` alongside `quality_score`, so that I can interpret WiFi stability at a glance without inspecting raw data.

#### Acceptance Criteria
1. When a test run completes, netProbe shall display `wifi_stability_score` in the terminal summary immediately after `quality_score`.
2. When `wifi_stability_score` is hardware-backed (at least one WiFi sample collected), netProbe shall label it "WiFi Stability Score" and include the average SNR value (dB) in the display.
3. When `wifi_stability_score` is behavior-only (no hardware samples), netProbe shall label it "Connection Stability Score (behavior only)" to distinguish it from a hardware-backed score.
4. The score display shall apply the same rating bands as `quality_score`: ≥90 = Excellent, ≥80 = Good, ≥70 = Fair, <70 = Poor.
5. If `wifi_stability_score` is `null` (hardware sampling was attempted but returned no data and behavior variance cannot be computed), netProbe shall display "WiFi Stability Score: N/A" rather than omitting the field.

### Requirement 4: JSON and CSV Export

**Objective:** As a user exporting results, I want `wifi_stability_score` and raw WiFi samples included in exports, so that I can analyze stability data outside of the terminal.

#### Acceptance Criteria
1. When JSON export is requested, netProbe shall include `wifi_stability_score` (integer or null), `wifi_score_type` (string: "hardware", "behavior-only", or "unavailable"), and `wifi_samples` (array of sample objects) in the exported JSON.
2. When CSV export is requested, netProbe shall include `wifi_stability_score` as a column in the summary row and include individual WiFi samples (timestamp, rssi_dbm, noise_dbm, snr_db) in the output.
3. When no WiFi samples were collected, netProbe shall write `wifi_samples` as an empty array and `wifi_score_type` as "behavior-only" or "unavailable" accordingly.

### Requirement 5: Test Coverage

**Objective:** As a developer, I want full unit test coverage for the WiFi sampler and stability calculator that completes within the existing 1-second test budget, so that the test suite remains fast and reliable.

#### Acceptance Criteria
1. The test suite shall mock all system calls used for WiFi signal sampling; no real hardware queries shall execute during tests.
2. When the sampler is tested with mocked signal data output, netProbe tests shall verify that RSSI, noise floor, and SNR are parsed and recorded correctly.
3. When the stability score calculation is tested, the test suite shall cover: the hardware-backed path (multiple samples), the behavior-only path (zero hardware samples), the single-sample path (no variance penalty), and the non-WiFi/non-macOS degradation path.
4. When the full test suite runs with all network and system calls mocked, it shall complete in under 1 second.
