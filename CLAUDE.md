# NetProbe - Internet Connection Reliability Tool

## Project Overview
Create a comprehensive internet connection reliability testing tool that goes beyond simple speed tests to provide a holistic view of connection quality over extended periods (30s-1min).

## Research Summary

### Best Practices for Connection Testing
- **Key Metrics**: Latency (<25ms ideal, <100ms acceptable), Packet Loss (0% ideal), Jitter (<15% stable, <25ms acceptable)
- **Testing Duration**: Extended testing periods (30s-1min) provide more reliable results than quick snapshots
- **Multiple Endpoints**: Test against multiple servers/endpoints for comprehensive coverage
- **Continuous Monitoring**: Regular testing provides better insights than one-time measurements

### Existing Solutions Analysis

#### Free/Open Source Tools:
1. **LibreSpeed** - Most popular open source alternative to Ookla
   - Self-hosted HTML5 speedtest
   - No external dependencies
   - Mobile responsive

2. **NetProbe Lite** (GitHub: plaintextpackets/netprobe_lite)
   - Python-based ISP performance tester
   - Measures packet loss, latency, jitter, DNS performance
   - Docker deployment
   - Free for non-commercial use

3. **OpenSpeedTest**
   - HTML5 speed test, no apps needed
   - Works on any device

#### Commercial Solutions:
1. **Ookla Speedtest** - Industry standard with 16,000+ servers
2. **NetProbe 2000 Series** - Professional hardware testers (enterprise pricing)
3. **Various online tools** - packetlosstest.com, packetstats.com, etc.

## Implementation Plan

### Phase 1: Core Testing Engine
- [ ] Latency/Ping testing to multiple endpoints
- [ ] Packet loss measurement
- [ ] Jitter calculation
- [ ] Basic bandwidth testing
- [ ] DNS resolution time testing

### Phase 2: Extended Testing Features
- [ ] Multi-endpoint testing (Google, Cloudflare, custom)
- [ ] Configurable test duration (30s-5min)
- [ ] Real-time progress reporting
- [ ] Statistical analysis (min, max, avg, percentiles)

### Phase 3: Reporting & Analysis
- [ ] JSON/CSV export functionality
- [ ] Visual graphs/charts
- [ ] Historical data tracking
- [ ] Connection quality scoring system

### Phase 4: Advanced Features
- [ ] Continuous monitoring mode
- [ ] Email/webhook alerts for connection issues
- [ ] Comparison with ISP advertised speeds
- [ ] Network interface selection

## Technical Architecture

### Core Components:
1. **Connection Tester** - Main testing engine
2. **Statistics Calculator** - Data analysis and scoring
3. **Reporter** - Output formatting and export
4. **Configuration Manager** - Test parameters and endpoints

### Dependencies:
- `requests` - HTTP testing
- `ping3` or `pythonping` - ICMP ping
- `dnspython` - DNS testing
- `matplotlib` or `plotly` - Visualization
- `click` - CLI interface
- `pydantic` - Configuration management

### Test Endpoints:
- Primary: 8.8.8.8 (Google DNS)
- Secondary: 1.1.1.1 (Cloudflare DNS)  
- HTTP: speed.cloudflare.com, fast.com API
- Custom configurable endpoints

## Success Metrics
- Accurate measurement of all key connection quality metrics
- Consistent results across multiple test runs
- Easy-to-understand reporting format
- Performance impact <5% of available bandwidth during testing
- Cross-platform compatibility (Windows, macOS, Linux)

## Project Structure

```
netprobe/
├── netprobe.py           # Main application
├── test_netprobe.py      # Test suite
├── CLAUDE.md            # Project documentation
├── README.md            # User documentation
├── Pipfile              # Dependencies
├── .gitignore           # Git ignore rules
└── results/             # Test results (git-ignored)
    ├── *.json           # JSON exports
    └── *.csv            # CSV exports
```

## New Features Added

### Debug Mode & Progress Bar
- `--debug`: Enables verbose logging (original behavior)  
- Normal mode: Shows clean progress bar with minimal output
- Simplified final report with emoji indicators

### Location Tracking
- `--detect-location`: Auto-detects current location via IP geolocation
- `--location "Place Name"`: Specify test location (e.g., hotel, café)
- Location info included in results and exports
- Perfect for testing "Hotel ABC has 85% connection quality"

### Example Usage:
```bash
# Test at Starbucks with location tracking
./netprobe.py --location "Starbucks Times Square NYC" --json cafe_test.json

# Auto-detect location and compare VPN performance  
./netprobe.py --detect-location --compare-vpn --duration 60
```

## Development Guidelines

### Testing Requirements
- **ALWAYS run tests before completing any task** - Use `./test.py` to run the full test suite
- **Test suite must complete in under 1 second** - Use mocking to avoid network calls and slow operations
- **Single test runner** - Use `test/test_netprobe.py` for all tests, no multiple test files
- **Comprehensive mocking** - Mock all network operations, VPN calls, and external dependencies

### Test Command
```bash
./test.py  # Should complete in <1s with full mocking
```

## Future Enhancements
- Web interface for easier use
- Mobile app version
- Integration with monitoring systems (Prometheus, etc.)
- ISP comparison database
- Network troubleshooting suggestions
- Location-based performance database