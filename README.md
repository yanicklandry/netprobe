# NetProbe - Internet Connection Reliability Tool

A comprehensive Python tool for testing internet connection quality over extended periods. Goes beyond simple speed tests to provide detailed analysis of connection reliability including latency, packet loss, jitter, DNS resolution, and bandwidth testing.

## Features

- **Extended Testing**: Run tests for 30s-5min to get reliable connection quality metrics
- **Comprehensive Metrics**: Latency, packet loss, jitter, DNS resolution, and bandwidth
- **Local Router Testing**: Test connectivity to your gateway/router for network diagnostics
- **VPN Comparison**: Test with and without VPN to compare connection quality
- **Network Isolation Analysis**: Detect interference from background applications
- **Router Congestion Detection**: Estimate connected devices and network load
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

# Force ICMP ping (requires sudo on macOS/Linux)
sudo ./netprobe.py --icmp --duration 30

# Enable debug mode for verbose output
./netprobe.py --debug --duration 30

# Auto-detect current location
./netprobe.py --detect-location --duration 30

# Test at a specific location (hotel, restaurant, etc.)
./netprobe.py --location "Hilton Hotel NYC" --duration 30

# Check network isolation before testing
./netprobe.py --check-isolation --duration 30

# Alternative: use pipenv run
pipenv run python netprobe.py
```

### VPN Testing

```bash
# Compare connection with and without VPN (interactive prompts for GUI VPNs)
./netprobe.py --compare-vpn

# Test only with VPN enabled
./netprobe.py --vpn-only

# Test only without VPN
./netprobe.py --no-vpn

# Skip interactive prompts (for automation/CI)
./netprobe.py --compare-vpn --no-interactive
```

### Interactive VPN Usage

For GUI VPN clients (like NordVPN app), the tool will:
1. **Detect current VPN status** automatically
2. **Prompt you** when VPN changes are needed
3. **Wait for you** to manually connect/disconnect
4. **Verify the change** before continuing with tests
5. **Restore original state** when done

### Export Results

```bash
# Export to JSON (saved to results/ directory)
./netprobe.py --json results.json

# Export latency data to CSV (saved to results/ directory)
./netprobe.py --csv latency.csv

# Export both with VPN comparison
./netprobe.py --compare-vpn --json comparison.json --csv comparison.csv

# Use absolute paths to save elsewhere
./netprobe.py --json /tmp/results.json --csv /tmp/data.csv
```

**Note**: All result files are automatically saved to the `results/` directory (which is git-ignored) unless you specify an absolute path.

### Network Analysis Tools

```bash
# Analyze network isolation and interference
./network_isolation_detector.py

# Analyze router congestion and connected devices
./router_analyzer.py

# Combined analysis with debug output
./router_analyzer.py --debug
```

### Testing

```bash
# Run the test suite using the main test script
./test.py

# Or run tests directly with pytest
pipenv run pytest test/ -v

# Install coverage for detailed analysis
pipenv install pytest-cov
./test.py  # Automatically includes coverage when pytest-cov is installed
```

The test suite includes:
- **Unit Tests**: Individual component testing (VPN, networking, statistics)
- **Integration Tests**: End-to-end functionality testing  
- **Coverage Analysis**: Code coverage reporting (requires pytest-cov)
- **Organized Structure**: All tests in `test/` directory with main runner script

## Supported VPN Clients

- **NordVPN CLI** - `nordvpn` command line tool (full automation)
- **NordVPN GUI** - NordVPN.app on macOS (detection only, manual connect/disconnect)  
- **ProtonVPN** - `protonvpn-cli`
- **ExpressVPN** - `expressvpn` CLI
- **SurfShark** - `surfshark-vpn` CLI

### VPN Automation Notes

- **CLI Tools**: Full automation (connect/disconnect)
- **GUI Apps**: Detection only, requires manual VPN control
- **Location Detection**: Always detects without VPN for accurate physical location
- **VPN Comparison**: For GUI VPNs, manually toggle connection between tests

## Location Services Notes

The tool uses multiple geocoding services for location detection:
- **IP Geolocation**: Primary method for current location
- **ArcGIS**: Fallback for place searches
- **OpenStreetMap**: Last resort (rate limited)

If you encounter location errors (403 Forbidden), try:
- Using simpler location names (e.g., "Starbucks NYC" instead of "Starbucks Times Square")
- Waiting a few minutes between tests
- Using `--detect-location` instead of `--location` for simpler detection

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

- **Ping Method**: Uses TCP connection test by default (port 80). Use `--icmp` with sudo for true ICMP ping
- **Test Intervals**: Tests run every 5 seconds or divided evenly over the test duration
- **Bandwidth Test**: Downloads a 5-10MB file to measure download speed
- **DNS Test**: Measures resolution time for google.com
- **VPN State Management**: Automatically saves and restores original VPN state
- **Cross-Platform**: Works on macOS, Linux, Windows with appropriate permissions

## Exit Codes

- `0`: Connection quality is good (score ≥70)
- `1`: Connection quality is poor (score <70) or error occurred