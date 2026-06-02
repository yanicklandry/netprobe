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

**See [TODO.md](TODO.md) for comprehensive roadmap and implementation plan.**

Key upcoming improvements:
- Default 10s tests with auto-location and JSON logging
- Simplified VPN testing and location management
- Speed test accuracy improvements to match Google/Ookla results  
- Location-based historical tracking with cute emoji displays
- Comparison benchmarking against other speed test tools

# Agentic SDLC and Spec-Driven Development

Kiro-style Spec-Driven Development on an agentic SDLC

## Project Context

### Paths
- Steering: `.kiro/steering/`
- Specs: `.kiro/specs/`

### Steering vs Specification

**Steering** (`.kiro/steering/`) - Guide AI with project-wide rules and context
**Specs** (`.kiro/specs/`) - Formalize development process for individual features

### Active Specifications
- Check `.kiro/specs/` for active specifications
- Use `/kiro-spec-status [feature-name]` to check progress

## Development Guidelines
- Think in English, generate responses in English. All Markdown content written to project files (e.g., requirements.md, design.md, tasks.md, research.md, validation reports) MUST be written in the target language configured for this specification (see spec.json.language).

## Minimal Workflow
- Phase 0 (optional): `/kiro-steering`, `/kiro-steering-custom`
- Discovery: `/kiro-discovery "idea"` — determines action path, writes brief.md + roadmap.md for multi-spec projects
- Phase 1 (Specification):
  - Single spec: `/kiro-spec-quick {feature} [--auto]` or step by step:
    - `/kiro-spec-init "description"`
    - `/kiro-spec-requirements {feature}`
    - `/kiro-validate-gap {feature}` (optional: for existing codebase)
    - `/kiro-spec-design {feature} [-y]`
    - `/kiro-validate-design {feature}` (optional: design review)
    - `/kiro-spec-tasks {feature} [-y]`
  - Multi-spec: `/kiro-spec-batch` — creates all specs from roadmap.md in parallel by dependency wave
- Phase 2 (Implementation): `/kiro-impl {feature} [tasks]`
  - Without task numbers: autonomous mode (subagent per task + independent review + final validation)
  - With task numbers: manual mode (selected tasks in main context, still reviewer-gated before completion)
  - `/kiro-validate-impl {feature}` (standalone re-validation)
- Progress check: `/kiro-spec-status {feature}` (use anytime)

## Skills Structure
Skills are located in `.claude/skills/kiro-*/SKILL.md`
- Each skill is a directory with a `SKILL.md` file
- Skills run inline with access to conversation context
- Skills may delegate parallel research to subagents for efficiency
- Additional files (templates, examples) can be added to skill directories
- `kiro-review` — task-local adversarial review protocol used by reviewer subagents
- `kiro-debug` — root-cause-first debug protocol used by debugger subagents
- `kiro-verify-completion` — fresh-evidence gate before success or completion claims
- **If there is even a 1% chance a skill applies to the current task, invoke it.** Do not skip skills because the task seems simple.

## Development Rules
- 3-phase approval workflow: Requirements → Design → Tasks → Implementation
- Human review required each phase; use `-y` only for intentional fast-track
- Keep steering current and verify alignment with `/kiro-spec-status`
- Follow the user's instructions precisely, and within that scope act autonomously: gather the necessary context and complete the requested work end-to-end in this run, asking questions only when essential information is missing or the instructions are critically ambiguous.

## Steering Configuration
- Load entire `.kiro/steering/` as project memory
- Default files: `product.md`, `tech.md`, `structure.md`
- Custom files are supported (managed via `/kiro-steering-custom`)
