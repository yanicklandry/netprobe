# Interactive VPN Testing Demo

This document shows how the interactive VPN testing works when run in a real terminal.

## Example Session

```bash
$ ./netprobe.py --compare-vpn --duration 30

NetProbe - Internet Connection Reliability Tool
==================================================
Detected VPN client: nordvpn-macos
Current VPN status: Connected
Connected to server: 155.133.15.32
📝 NordVPN GUI detected. Interactive VPN comparison enabled:
   • Tool will prompt when VPN changes are needed
   • Simply connect/disconnect manually when prompted
   • VPN status detection works automatically

🔍 Testing Without Vpn

🔌 Please DISCONNECT your VPN manually now
   1. Open NordVPN app
   2. Click disconnect
   3. Wait for disconnection to complete
Press Enter when VPN is disconnected and ready...

✅ VPN disconnection detected!

[Progress bar shows test running without VPN]

📊 Connection Quality Score: 85/100
   🏓 Latency: 22.1ms | 🌐 DNS: 15.2ms | ⬇️ Speed: 95.3Mbps
   Connection Status: 🟡 Good

🔍 Testing With Vpn

🔌 Please CONNECT your VPN manually now
   1. Open NordVPN app  
   2. Click connect to any server
   3. Wait for connection to establish
Press Enter when VPN is connected and ready...

✅ VPN connection detected! Server: 185.243.218.27

[Progress bar shows test running with VPN]

📊 Connection Quality Score: 78/100
   🏓 Latency: 45.8ms | 🌐 DNS: 32.1ms | ⬇️ Speed: 87.2Mbps
   Connection Status: 🟡 Good

============================================================
VPN COMPARISON SUMMARY
============================================================

Without Vpn:
  Quality Score: 85/100
  Average Latency: 22.10 ms
  Average Packet Loss: 0.00%
  Download Speed: 95.30 Mbps

With Vpn (185.243.218.27):
  Quality Score: 78/100
  Average Latency: 45.80 ms
  Average Packet Loss: 0.00%
  Download Speed: 87.20 Mbps

Differences (VPN impact):
  Latency change: +23.70 ms
  Packet loss change: +0.00%
  Quality score change: -7 points

Connection quality is good (best score: 85).

Restoring original VPN state...
```

## Features

- **🔍 Automatic VPN Detection**: Works with NordVPN GUI and CLI tools
- **🔌 Interactive Prompts**: Clear step-by-step instructions  
- **✅ Status Verification**: Confirms VPN changes before proceeding
- **📊 Side-by-Side Comparison**: Shows impact of VPN on connection quality
- **🔄 State Restoration**: Returns VPN to original state when done

## Use Cases

- Test hotel/café WiFi quality with and without VPN
- Compare VPN server performance
- Verify if VPN affects connection reliability
- Generate reports for different network environments