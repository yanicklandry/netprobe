# NetProbe - Future Improvements Roadmap

## **Phase 1: Core UX Improvements** ⭐ (High Priority)

### Default Behavior Changes
- [ ] **Default to 10s test duration** instead of 60s for faster results
- [ ] **Always enable --check-isolation** by default (it's fast and informative)
- [ ] **Always query GPS location** automatically without requiring flags
- [ ] **Always log to single JSON results file** (`netprobe-results.json`) with append mode

### VPN Testing Simplification  
- [ ] **Simplify VPN options** - keep only one flag `--test-vpn` to compare with/without VPN
- [ ] Remove complex `--compare-vpn` scenarios, make it binary: test with current state, then toggle VPN and test again

### Location Management
- [ ] **Auto-detect unnamed locations** and add to pending list (`locations-to-name.json`)
- [ ] **Prepare cute display by locations** - emoji flags, city names, connection quality history
- [ ] Allow user to name locations later: `./netprobe.py --name-location "Starbucks 5th Ave"`

## **Phase 2: Speed Test Accuracy** 🚀 (High Priority)

### Immediate Technical Fixes
- [ ] **Update test mocks** for new parallel bandwidth testing
- [ ] **Add HTTP/2 support** with httpx library for better performance  
- [ ] **Implement upload speed testing** (not just download)

### Best Practice Research & Implementation
- [ ] **Research online best practices** for network speed testing
  - Study Ookla, fast.com, Google Speed Test methodologies
  - Analyze optimal test file sizes, duration, server selection
  - Document findings in `RESEARCH.md`

### Comparison Testing Framework
- [ ] **Add test scenario to compare with other tools**
  - `./netprobe.py --benchmark` mode
  - Test against: fast.com, Google Speed Test, speedtest.net  
  - Show side-by-side results comparison
  - Analyze discrepancies and adjust algorithms

## **Phase 3: Advanced Performance Features** ⚡ (Medium Priority)

### Smart Testing
- [ ] **Add automatic server selection** based on ping/geography
- [ ] **Implement adaptive test duration** based on connection speed
- [ ] **Add CDN-aware testing** (test multiple CDN providers)
- [ ] **Add ISP throttling detection** algorithms

### Analytics & Monitoring
- [ ] **Create bandwidth history tracking** and trending
- [ ] **Add network congestion time-of-day analysis**
- [ ] **Implement real-time bandwidth monitoring mode**
- [ ] **Add comparison with advertised ISP speeds**
- [ ] **Create improved network quality scoring** system

## **Phase 4: Data Management & Visualization** 📊 (Medium Priority)

### Results Management
- [ ] **Single JSON log file** with structured data
  ```json
  {
    "tests": [
      {
        "timestamp": "2025-01-09T14:30:00Z",
        "location": {"name": "Starbucks 5th Ave", "lat": 40.7, "lng": -74.0},
        "vpn_status": {"connected": true, "server": "us1234.nordvpn.com"},
        "results": {...},
        "quality_score": 85
      }
    ]
  }
  ```

### Location-Based Display
- [ ] **Cute location display** with emojis and history
  ```
  🏠 Home WiFi           │ 🔒 VPN: ✅ │ Quality: 95/100 ⭐⭐⭐⭐⭐
  ☕ Starbucks 5th Ave  │ 🔒 VPN: ❌ │ Quality: 73/100 ⭐⭐⭐⭐
  🏨 Hotel Marriott     │ 🔒 VPN: ✅ │ Quality: 45/100 ⭐⭐
  📍 Unknown Location   │ 🔒 VPN: ❌ │ Quality: 82/100 ⭐⭐⭐⭐
  ```

### Visualization
- [ ] **Create web dashboard** for results visualization
- [ ] **Add trend graphs** (speed over time, quality by location)
- [ ] **Location map view** with quality heat map

## **Phase 5: User Experience & Automation** 🎯 (Lower Priority)

### Convenience Features
- [ ] **Implement scheduled testing** with notifications
- [ ] **Add mobile app companion** for testing
- [ ] **Smart location naming** suggestions based on nearby businesses/WiFi names

### Advanced Monitoring
- [ ] **Network troubleshooting suggestions** based on test results  
- [ ] **ISP performance database** for regional comparisons
- [ ] **Integration with monitoring systems** (Prometheus, etc.)

## **Implementation Guidelines**

### Development Principles
1. **Always run tests first** - use `./test.py` before any changes
2. **Maintain <1s test runtime** with comprehensive mocking
3. **Follow existing code patterns** and conventions
4. **Update CLAUDE.md** with any architectural changes

### User Experience Focus
1. **Default to sensible behavior** (10s tests, auto-location, JSON logging)
2. **Make complex features opt-in** (benchmarking, real-time monitoring)  
3. **Beautiful, informative output** with emojis and clear metrics
4. **Progressive disclosure** - simple by default, powerful when needed

### Data Structure Evolution
1. **Maintain backward compatibility** with existing JSON exports
2. **Use structured logging** for easy parsing and analysis
3. **Location-centric data model** for historical tracking
4. **Privacy-first approach** (no personal data collection)

---

## **Quick Wins for Next Session** 🎯

1. Change default duration to 10s
2. Enable auto-location and isolation check by default  
3. Implement single JSON results logging
4. Simplify VPN testing to single `--test-vpn` flag
5. Add location naming queue for unnamed locations

These changes will immediately improve the user experience while maintaining all existing functionality.