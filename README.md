# NetProbe - Internet Connection Reliability Tool

A comprehensive Python tool for testing internet connection quality over extended periods. Goes beyond simple speed tests to provide detailed analysis of connection reliability including latency, packet loss, jitter, DNS resolution, and bandwidth testing.

## Features

- **Extended Testing**: Run tests for 30s-5min to get reliable connection quality metrics
- **Comprehensive Metrics**: Latency, packet loss, jitter, DNS resolution, and bandwidth
- **VPN Comparison**: Test with and without VPN to compare connection quality
- **Multiple Endpoints**: Test against Google DNS, Cloudflare DNS, and OpenDNS by default
- **Smart Fallback**: Uses TCP connection test when ICMP ping is not permitted
- **Export Options**: JSON and CSV export for further analysis
- **Quality Scoring**: 0-100 connection quality score based on industry standards

## Installation

Requirements: Python 3.7+, pipenv

```bash
git clone <repository>
cd netprobe
pipenv install
chmod +x netprobe.py
```

## Usage

### Basic Usage

```bash
# Run a 60-second test (default)
./netprobe.py

# Run a 30-second test
./netprobe.py --duration 30

# Add custom endpoints
./netprobe.py -e 4.4.4.4 -e 9.9.9.9

# Alternative: use pipenv run
pipenv run python netprobe.py
```

### VPN Testing

```bash
# Compare connection with and without VPN
./netprobe.py --compare-vpn

# Test only with VPN enabled
./netprobe.py --vpn-only

# Test only without VPN
./netprobe.py --no-vpn
```

### Export Results

```bash
# Export to JSON
./netprobe.py --json results.json

# Export latency data to CSV
./netprobe.py --csv latency.csv

# Export both with VPN comparison
./netprobe.py --compare-vpn --json comparison.json --csv comparison.csv
```

### Testing

```bash
# Run the test suite
pipenv run pytest test_netprobe.py -v

# Run tests with coverage
pipenv install pytest-cov
pipenv run pytest test_netprobe.py --cov=netprobe --cov-report=html
```

## Supported VPN Clients

- **NordVPN** - `nordvpn` CLI
- **ProtonVPN** - `protonvpn-cli`
- **ExpressVPN** - `expressvpn` CLI
- **SurfShark** - `surfshark-vpn` CLI

The tool automatically detects which VPN client is installed and uses the appropriate commands.

## Metrics Explained

### Latency
- **Good**: <25ms
- **Acceptable**: <100ms
- **Poor**: >100ms

### Packet Loss
- **Excellent**: 0%
- **Poor**: >1%

### Jitter
- **Good**: <15ms
- **Acceptable**: <25ms
- **Poor**: >25ms

### Quality Score
- **Excellent**: 90-100
- **Good**: 70-89
- **Fair**: 50-69
- **Poor**: <50

## Example Output

```
NetProbe - Internet Connection Reliability Tool
==================================================

============================================================
RUNNING TEST: WITHOUT VPN
============================================================
Starting 60-second connection reliability test...
==================================================

Test iteration 1...
Testing latency and packet loss to 8.8.8.8...
Testing latency and packet loss to 1.1.1.1...
Testing latency and packet loss to 208.67.222.222...
Testing DNS resolution for google.com...

...

============================================================
CONNECTION RELIABILITY TEST RESULTS
============================================================

Test Duration: 2025-01-01T10:00:00 to 2025-01-01T10:01:00
Overall Quality Score: 85/100

Latency Statistics:
  Average: 22.45 ms
  Minimum: 18.23 ms
  Maximum: 28.67 ms
  95th Percentile: 27.12 ms

Packet Loss Statistics:
  Average: 0.00%
  Maximum: 0.00%

Jitter Statistics:
  Average: 3.21 ms
  Maximum: 8.45 ms

DNS Resolution Statistics:
  Average: 15.67 ms
  Minimum: 12.34 ms
  Maximum: 19.87 ms

Bandwidth Test:
  Download Speed: 95.43 Mbps

============================================================

Connection quality is good.
```

## Technical Details

- **Ping Method**: Attempts ICMP ping first, falls back to TCP connection test on port 80
- **Test Intervals**: Tests run every 5 seconds or divided evenly over the test duration
- **Bandwidth Test**: Downloads a 5-10MB file to measure download speed
- **DNS Test**: Measures resolution time for google.com
- **VPN State Management**: Automatically saves and restores original VPN state

## Exit Codes

- `0`: Connection quality is good (score ≥70)
- `1`: Connection quality is poor (score <70) or error occurred