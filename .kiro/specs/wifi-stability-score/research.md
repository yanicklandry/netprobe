# Research & Design Decisions

---

## Summary
- **Feature**: `wifi-stability-score`
- **Discovery Scope**: Extension (existing single-file Python tool)
- **Key Findings**:
  - macOS exposes RSSI and noise floor via `system_profiler SPAirPortDataType` — no `airport` binary or pip dependencies needed; confirmed working on macOS 15.x (Signal: -70 dBm / Noise: -97 dBm)
  - `netprobe.py` already uses `threading.Thread` for parallel bandwidth tests — same pattern directly applicable for the background sampler
  - All existing scoring logic is in `StatisticsCalculator` as static methods — adding a new static method for wifi stability score is architecturally consistent and keeps `quality_score` untouched

---

## Research Log

### macOS WiFi Signal Data Access
- **Context**: Needed a reliable way to read RSSI and noise floor without root privileges or deprecated tools
- **Sources Consulted**: `system_profiler SPAirPortDataType` on macOS 15.x; `networksetup -getinfo Wi-Fi`; confirmed `airport` binary absent at `/usr/sbin/airport`
- **Findings**:
  - `system_profiler SPAirPortDataType` returns text with `Signal / Noise: -70 dBm / -97 dBm` for the connected network
  - Available without root; takes ~1–2 seconds per call
  - Output is human-readable text, not JSON — regex parse required
  - `networksetup -getinfo Wi-Fi` confirms connected IP but does not expose RSSI/noise
- **Implications**: Use subprocess call to `system_profiler` with regex `Signal / Noise: (-?\d+) dBm / (-?\d+) dBm`; call at 5s intervals to stay within timing budget

### Threading Pattern in Existing Codebase
- **Context**: Needed to confirm whether background threading was acceptable and what pattern to follow
- **Findings**:
  - `_test_bandwidth_parallel()` (lines 410–493) uses `threading.Thread` with `queue.Queue`; threads join with 15s timeout
  - Pattern is straightforward; `threading.Event` for stop signaling is idiomatic Python and not present yet — clean addition
- **Implications**: Use `threading.Event` for clean stop; join with 2s timeout (sampler calls are short); daemon=True so process exit is not blocked

### Dependency Evaluation
- **Context**: Checked whether any Python WiFi libraries would simplify implementation
- **Findings**:
  - `wifi` PyPI package — reads SSID only, not RSSI
  - `scapy` — heavyweight, requires root for raw socket access
  - `CoreWLAN` via PyObjC — macOS-only, requires additional pip dependency
  - `subprocess + system_profiler` — zero dependencies, already used in codebase (`VpnManager` uses subprocess)
- **Implications**: Build with subprocess; no new pip dependencies

---

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks | Decision |
|--------|-------------|-----------|-------|----------|
| Background thread (chosen) | Thread samples every 5s; joined at test end | Non-blocking, consistent with existing pattern, simple start/stop interface | system_profiler latency could exceed 5s on slow systems | Chosen — 5s interval accommodates 1–2s call time |
| Synchronous sampling | Sample at fixed points in existing test loop | Simpler code | Blocks test loop; adds latency to each iteration | Rejected |
| Timer-based (`threading.Timer`) | Recursive Timer instead of thread loop | Clean API | Harder to stop cleanly; recursive calls stack | Rejected |

---

## Design Decisions

### Decision: Single Static Method vs. New Class for Score Calculation
- **Context**: Choosing where to place stability score computation
- **Alternatives Considered**:
  1. New `WiFiScoreCalculator` class — parallel to `StatisticsCalculator`
  2. Static method on existing `StatisticsCalculator`
- **Selected Approach**: Static method `calculate_wifi_stability_score()` on `StatisticsCalculator`
- **Rationale**: All existing score logic is in `StatisticsCalculator`; adding a new class for a single function would be speculative abstraction (synthesis rule: simplification)
- **Trade-offs**: Slightly larger `StatisticsCalculator` class; no new indirection layer; easier to test alongside existing stat tests

### Decision: Generalized Score Interface (hardware + behavior-only via same function)
- **Context**: Two code paths exist (hardware samples available vs. not); choosing between one function vs. two
- **Selected Approach**: One function with branch on `len(samples) == 0`; returns `wifi_score_type` discriminator
- **Rationale**: Callers (Reporter, export) handle a single `WiFiStabilityResult` regardless of path; no special-casing in caller code
- **Trade-offs**: Slightly more complex function body; cleaner caller interface

### Decision: SNR Variance Penalty Thresholds
- **Context**: No prior art in this codebase for SNR-based scoring
- **Approach**: Thresholds derived from WiFi engineering conventions:
  - SNR < 10 dB: unusable (VoIP drops, video stalls)
  - SNR < 20 dB: marginal (frequent retransmits)
  - SNR < 30 dB: acceptable (some degradation possible)
  - Variance > 10 dB std_dev: highly unstable signal (roaming or interference events)
- **Follow-up**: Thresholds may need tuning after real-world testing at locations with known WiFi quality

---

## Risks & Mitigations
- `system_profiler` output format may change on future macOS versions — mitigated by regex with optional whitespace; `_parse_output` returns `None` gracefully on mismatch
- sampler thread taking > 2s to join on stop — mitigated by 2s timeout + daemon=True; partial sample list accepted
- SNR penalty thresholds not validated against real ISP-quality WiFi data — note in implementation: these are engineering estimates, log actual SNR values in JSON for future calibration
