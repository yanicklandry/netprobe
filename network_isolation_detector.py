#!/usr/bin/env pipenv run python
"""
Network Isolation Detector for NetProbe
Detects potential network interference during testing.
"""

import psutil
import subprocess
import time
from typing import Dict, List, Any
import platform

class NetworkIsolationDetector:
    """Detect potential network interference during testing."""
    
    def __init__(self):
        self.baseline_processes = []
        self.high_bandwidth_apps = [
            'chrome', 'firefox', 'safari', 'edge',  # Browsers
            'zoom', 'skype', 'teams', 'slack',      # Video calls
            'spotify', 'itunes', 'vlc',             # Media
            'steam', 'epic', 'origin',              # Gaming
            'dropbox', 'googledrive', 'onedrive',   # Cloud sync
            'bittorrent', 'utorrent', 'qbittorrent' # P2P
        ]
    
    def check_network_processes(self) -> Dict[str, Any]:
        """Check for processes that might interfere with network testing."""
        interfering_processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                try:
                    proc_name = proc.info['name'].lower()
                    
                    # Check if it's a high-bandwidth application
                    if any(app in proc_name for app in self.high_bandwidth_apps):
                        # Get network IO for this process
                        try:
                            io_counters = proc.io_counters()
                            interfering_processes.append({
                                'name': proc.info['name'],
                                'pid': proc.info['pid'],
                                'type': 'high_bandwidth_app'
                            })
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            return {'error': f'Failed to check processes: {str(e)}'}
        
        return {
            'interfering_processes': interfering_processes,
            'count': len(interfering_processes)
        }
    
    def check_network_activity(self) -> Dict[str, Any]:
        """Monitor current network activity levels."""
        try:
            # Get initial network stats
            net_io_start = psutil.net_io_counters()
            time.sleep(1)  # Sample for 1 second
            net_io_end = psutil.net_io_counters()
            
            # Calculate bytes per second
            bytes_sent_per_sec = net_io_end.bytes_sent - net_io_start.bytes_sent
            bytes_recv_per_sec = net_io_end.bytes_recv - net_io_start.bytes_recv
            
            # Convert to Mbps
            mbps_sent = (bytes_sent_per_sec * 8) / (1024 * 1024)
            mbps_recv = (bytes_recv_per_sec * 8) / (1024 * 1024)
            total_mbps = mbps_sent + mbps_recv
            
            # Classify activity levels
            activity_level = 'low'
            if total_mbps > 50:
                activity_level = 'very_high'
            elif total_mbps > 10:
                activity_level = 'high' 
            elif total_mbps > 1:
                activity_level = 'moderate'
            
            return {
                'mbps_sent': round(mbps_sent, 2),
                'mbps_received': round(mbps_recv, 2),
                'total_mbps': round(total_mbps, 2),
                'activity_level': activity_level,
                'packets_sent': net_io_end.packets_sent - net_io_start.packets_sent,
                'packets_recv': net_io_end.packets_recv - net_io_start.packets_recv
            }
            
        except Exception as e:
            return {'error': f'Failed to check network activity: {str(e)}'}
    
    def check_wifi_interference(self) -> Dict[str, Any]:
        """Check for WiFi interference (macOS/Linux)."""
        try:
            if platform.system() == 'Darwin':  # macOS
                # Use airport utility to scan for networks
                try:
                    result = subprocess.run([
                        '/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport',
                        '-s'
                    ], capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        networks = result.stdout.strip().split('\\n')[1:]  # Skip header
                        
                        # Count networks per channel
                        channel_usage = {}
                        for line in networks:
                            parts = line.split()
                            if len(parts) >= 4:
                                try:
                                    channel = int(parts[3])
                                    channel_usage[channel] = channel_usage.get(channel, 0) + 1
                                except ValueError:
                                    continue
                        
                        # Find most congested channels
                        if channel_usage:
                            max_networks = max(channel_usage.values())
                            congested_channels = [ch for ch, count in channel_usage.items() if count >= max_networks * 0.8]
                            
                            return {
                                'total_networks': len(networks),
                                'channel_usage': channel_usage,
                                'congested_channels': congested_channels,
                                'interference_level': 'high' if max_networks > 10 else 'moderate' if max_networks > 5 else 'low'
                            }
                        
                except subprocess.TimeoutExpired:
                    return {'error': 'WiFi scan timed out'}
                except FileNotFoundError:
                    return {'error': 'Airport utility not found'}
                    
            elif platform.system() == 'Linux':
                # Use iwlist to scan for networks
                try:
                    result = subprocess.run(['iwlist', 'scan'], capture_output=True, text=True, timeout=15)
                    if result.returncode == 0:
                        networks_count = result.stdout.count('Cell ')
                        return {
                            'total_networks': networks_count,
                            'interference_level': 'high' if networks_count > 20 else 'moderate' if networks_count > 10 else 'low'
                        }
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass
                    
            return {'error': 'WiFi interference detection not supported on this platform'}
            
        except Exception as e:
            return {'error': f'WiFi interference check failed: {str(e)}'}
    
    def generate_isolation_report(self) -> Dict[str, Any]:
        """Generate a comprehensive network isolation report."""
        print("🔍 Analyzing network isolation...")
        
        report = {
            'timestamp': time.time(),
            'processes': self.check_network_processes(),
            'network_activity': self.check_network_activity(),
            'wifi_interference': self.check_wifi_interference()
        }
        
        # Calculate overall isolation score (0-100)
        isolation_score = 100
        warnings = []
        
        # Process interference
        if 'interfering_processes' in report['processes']:
            process_count = report['processes']['count']
            if process_count > 0:
                isolation_score -= min(30, process_count * 5)
                warnings.append(f"⚠️ {process_count} high-bandwidth applications detected")
        
        # Network activity
        if 'activity_level' in report['network_activity']:
            activity = report['network_activity']['activity_level']
            if activity == 'very_high':
                isolation_score -= 40
                warnings.append("⚠️ Very high background network activity detected")
            elif activity == 'high':
                isolation_score -= 25
                warnings.append("⚠️ High background network activity detected")
            elif activity == 'moderate':
                isolation_score -= 10
                warnings.append("ℹ️ Moderate background network activity detected")
        
        # WiFi interference  
        if 'interference_level' in report['wifi_interference']:
            wifi_level = report['wifi_interference']['interference_level']
            if wifi_level == 'high':
                isolation_score -= 20
                warnings.append("⚠️ High WiFi interference detected")
            elif wifi_level == 'moderate':
                isolation_score -= 10
                warnings.append("ℹ️ Moderate WiFi interference detected")
        
        isolation_score = max(0, isolation_score)
        report['isolation_score'] = isolation_score
        report['warnings'] = warnings
        
        return report
    
    def print_isolation_report(self, report: Dict[str, Any]):
        """Print a formatted isolation report."""
        print("\\n" + "="*60)
        print("NETWORK ISOLATION ANALYSIS")
        print("="*60)
        
        score = report.get('isolation_score', 0)
        if score >= 90:
            status = "🟢 Excellent"
        elif score >= 70:
            status = "🟡 Good"
        elif score >= 50:
            status = "🟠 Fair"
        else:
            status = "🔴 Poor"
            
        print(f"\\nIsolation Score: {score}/100 ({status})")
        
        # Show warnings
        if report.get('warnings'):
            print("\\nWarnings:")
            for warning in report['warnings']:
                print(f"  {warning}")
        
        # Network activity details
        if 'network_activity' in report and 'total_mbps' in report['network_activity']:
            activity = report['network_activity']
            print(f"\\nCurrent Network Usage: {activity['total_mbps']:.1f} Mbps")
            print(f"  Upload: {activity['mbps_sent']:.1f} Mbps | Download: {activity['mbps_received']:.1f} Mbps")
        
        # Process details
        if 'interfering_processes' in report['processes']:
            processes = report['processes']['interfering_processes']
            if processes:
                print(f"\\nHigh-bandwidth Applications ({len(processes)}):")
                for proc in processes[:5]:  # Show top 5
                    print(f"  • {proc['name']} (PID: {proc['pid']})")
                if len(processes) > 5:
                    print(f"  ... and {len(processes) - 5} more")
        
        # Recommendations
        print("\\nRecommendations:")
        if score < 70:
            print("  • Close unnecessary applications (browsers, streaming, downloads)")
            print("  • Pause cloud sync services temporarily")
            print("  • Run tests during off-peak hours")
            if 'wifi_interference' in report and report['wifi_interference'].get('interference_level') == 'high':
                print("  • Consider using ethernet connection instead of WiFi")
        else:
            print("  ✅ Network environment is suitable for reliable testing")

def main():
    """Main function for standalone testing."""
    detector = NetworkIsolationDetector()
    report = detector.generate_isolation_report()
    detector.print_isolation_report(report)

if __name__ == '__main__':
    main()