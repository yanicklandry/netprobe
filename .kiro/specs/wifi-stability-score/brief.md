# Brief: wifi-stability-score

## Problem
Users testing WiFi at hotels, cafés, or remote locations get a single `quality_score` that blends latency, packet loss, jitter, and DNS — but has no WiFi-specific stability dimension. A connection with great average latency but fluctuating signal (RSSI variance) will score misleadingly high. Users can't distinguish "bad WiFi signal" from "congested network."

## Current State
- `netprobe.py` computes a `quality_score` (0–100) from latency, packet loss, jitter, DNS
- No RSSI/SNR collection exists
- macOS exposes signal/noise per-interface via `system_profiler SPAirPortDataType` (Signal: -70 dBm / Noise: -97 dBm confirmed working)
- No temporal sampling of hardware metrics during a test run

## Desired Outcome
- A `wifi_stability_score` (0–100) appears alongside `quality_score` in reports and JSON exports
- The score reflects both signal quality (SNR) and temporal stability (how much SNR and network metrics vary over the test duration)
- Gracefully skips WiFi hardware sampling when not on WiFi (ethernet/VPN), marking the score as `null` or `N/A`
- Works on macOS; degrades to behavior-only on Linux/Windows (no platform crash)

## Approach
**Dedicated `wifi_stability_score` with temporal sampling** — sample RSSI/SNR at regular intervals (every 5s) during the existing test run, compute average SNR and its variance, then combine with network behavior variance (jitter std dev, latency CoV) into a single 0–100 score. Sampling runs in a background thread so it doesn't block or slow the existing test loop.

## Scope
- **In**:
  - WiFi hardware sampler (RSSI, SNR) via `system_profiler` on macOS
  - Background thread that samples at configurable interval during test run
  - `wifi_stability_score` calculation: SNR level + SNR variance + behavior variance
  - Display in summary report (alongside existing `quality_score`)
  - Inclusion in JSON/CSV exports
  - Graceful degradation: not-on-WiFi → score is `null`, non-macOS → behavior-only score
- **Out**:
  - Channel interference analysis (no scanning neighboring APs)
  - 6 GHz / Wi-Fi 6E specific reporting
  - Historical WiFi score tracking across sessions
  - GUI / desktop app changes

## Boundary Candidates
- **WiFi sampler**: isolated class/function that collects RSSI/SNR samples; returns list of `{timestamp, rssi_dbm, noise_dbm, snr_db}`
- **Stability calculator**: pure function consuming sampler output + existing jitter/latency stats → `wifi_stability_score`
- **Reporter integration**: display + export changes, consumes the score without knowing how it's computed

## Out of Boundary
- This spec does not own changes to `quality_score` logic
- Does not own location tracking, VPN comparison, or desktop app UI
- Does not own cross-session data persistence

## Upstream / Downstream
- **Upstream**: existing `ConnectionTester` run loop (sampling hooks in), `StatisticsCalculator` (behavior stats consumed), `Reporter` (display target)
- **Downstream**: likely: historical location scoring, per-location WiFi stability trends (future)

## Constraints
- Must not add measurable latency to the existing test run (background thread)
- `system_profiler SPAirPortDataType` confirmed available on macOS (no `airport` binary needed)
- Test suite must stay under 1s (mock `system_profiler` calls)
- Python 3.x only; no new pip dependencies for the WiFi sampler (subprocess is sufficient)
