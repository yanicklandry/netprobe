#!/usr/bin/env pipenv run python
"""
Router Congestion Analyzer for NetProbe
Estimates router load and connected client count.
"""

import subprocess
import socket
import threading
import time
from typing import Dict, List, Any, Optional
import ipaddress
import concurrent.futures
import sys
import platform

class RouterAnalyzer:
    """Analyze router congestion and estimate connected clients."""
    
    def __init__(self, gateway_ip: str = None, debug: bool = False):
        self.debug = debug
        self.gateway_ip = gateway_ip or self._discover_gateway()
        self.network_range = self._get_network_range()
        self.active_hosts = []
        
    def _discover_gateway(self) -> Optional[str]:
        """Discover local gateway IP."""
        try:
            if platform.system() == 'Darwin':
                # Try netstat method for macOS
                result = subprocess.run(['netstat', '-rn', '-f', 'inet'], 
                                      capture_output=True, text=True, timeout=5)
                if self.debug:
                    print(f"netstat output: {result.stdout[:200]}")
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        line = line.strip()
                        if self.debug and line:
                            print(f"Processing line: '{line}'")
                        if line.startswith('default'):
                            # Split on whitespace and filter empty strings
                            parts = [p for p in line.split() if p]
                            if self.debug:
                                print(f"Default route line: '{line}'")
                                print(f"Parsed parts: {parts}")
                            if len(parts) >= 2:
                                gateway = parts[1]
                                # Validate it's an IP address
                                try:
                                    socket.inet_aton(gateway)
                                    if self.debug:
                                        print(f"✅ Detected gateway: {gateway}")
                                    return gateway
                                except Exception as e:
                                    if self.debug:
                                        print(f"❌ Invalid IP '{gateway}': {e}")
                                    continue
            elif platform.system().startswith('Linux'):
                result = subprocess.run(['ip', 'route', 'show', 'default'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    parts = result.stdout.strip().split()
                    if 'via' in parts:
                        return parts[parts.index('via') + 1]
        except Exception:
            pass
        return None
    
    def _get_network_range(self) -> Optional[str]:
        """Get the local network range (e.g., 192.168.1.0/24)."""
        if not self.gateway_ip:
            return None
        
        try:
            # Common home network patterns
            ip_parts = self.gateway_ip.split('.')
            if len(ip_parts) == 4:
                # Assume /24 subnet for home networks
                network_base = '.'.join(ip_parts[:3]) + '.0/24'
                return network_base
        except Exception:
            pass
        return None
    
    def _ping_host(self, ip: str, timeout: int = 1) -> bool:
        """Ping a single host to check if it's alive."""
        try:
            if platform.system() == 'Windows':
                cmd = ['ping', '-n', '1', '-w', str(timeout * 1000), ip]
            else:
                cmd = ['ping', '-c', '1', '-W', str(timeout), ip]
            
            result = subprocess.run(cmd, capture_output=True, timeout=timeout + 1)
            return result.returncode == 0
        except Exception:
            return False
    
    def _tcp_probe(self, ip: str, port: int = 80, timeout: float = 0.5) -> bool:
        """Probe a host using TCP connection attempt."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def scan_network_range(self, max_workers: int = 50) -> List[str]:
        """Scan the network range to find active hosts."""
        if not self.network_range:
            return []
        
        active_hosts = []
        
        try:
            network = ipaddress.IPv4Network(self.network_range, strict=False)
            
            if self.debug:
                print(f"Scanning network range: {self.network_range}")
            
            # Use threading for faster scanning
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Create a list of IPs to scan (skip network and broadcast)
                ips_to_scan = [str(ip) for ip in network.hosts()]
                
                # Submit ping tasks
                future_to_ip = {
                    executor.submit(self._ping_host, ip, 1): ip 
                    for ip in ips_to_scan
                }
                
                # Collect results
                for future in concurrent.futures.as_completed(future_to_ip):
                    ip = future_to_ip[future]
                    try:
                        if future.result():
                            active_hosts.append(ip)
                            if self.debug:
                                print(f"Found active host: {ip}")
                    except Exception:
                        pass
                        
        except Exception as e:
            if self.debug:
                print(f"Network scan error: {e}")
        
        self.active_hosts = sorted(active_hosts, key=lambda x: ipaddress.IPv4Address(x))
        return self.active_hosts
    
    def analyze_arp_table(self) -> Dict[str, Any]:
        """Analyze ARP table for device discovery."""
        devices = []
        
        try:
            if platform.system() == 'Darwin':
                result = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=10)
            elif platform.system().startswith('Linux'):
                result = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=10)
            elif platform.system() == 'Windows':
                result = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=10)
            else:
                return {'error': 'ARP analysis not supported on this platform'}
            
            if result.returncode == 0:
                for line in result.stdout.split('\\n'):
                    line = line.strip()
                    if line and not line.startswith('?'):
                        # Parse ARP entries
                        if '(' in line and ')' in line:
                            # macOS format: hostname (ip) at mac [ifce]
                            try:
                                ip_start = line.find('(') + 1
                                ip_end = line.find(')')
                                ip = line[ip_start:ip_end]
                                
                                mac_start = line.find('at ') + 3
                                mac_end = line.find(' on')
                                if mac_end == -1:
                                    mac_end = line.find('[')
                                mac = line[mac_start:mac_end].strip()
                                
                                if self._is_valid_ip(ip) and mac != '(incomplete)':
                                    devices.append({'ip': ip, 'mac': mac})
                            except Exception:
                                continue
                        else:
                            # Linux/Windows format may vary
                            parts = line.split()
                            if len(parts) >= 3:
                                ip = parts[0].strip('()')
                                mac = parts[2] if len(parts) > 2 else 'unknown'
                                if self._is_valid_ip(ip) and mac != '<incomplete>':
                                    devices.append({'ip': ip, 'mac': mac})
            
            return {
                'devices': devices,
                'count': len(devices),
                'method': 'arp_table'
            }
            
        except Exception as e:
            return {'error': f'ARP table analysis failed: {str(e)}'}
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Check if string is a valid IP address."""
        try:
            ipaddress.IPv4Address(ip)
            return True
        except ValueError:
            return False
    
    def estimate_router_load(self) -> Dict[str, Any]:
        """Estimate router congestion based on various factors."""
        analysis = {
            'timestamp': time.time(),
            'gateway_ip': self.gateway_ip,
            'network_range': self.network_range
        }
        
        if self.debug:
            print("🔍 Analyzing router load and congestion...")
        
        # Method 1: ARP table analysis
        arp_data = self.analyze_arp_table()
        analysis['arp_analysis'] = arp_data
        
        # Method 2: Network scanning
        if self.network_range:
            scan_start = time.time()
            active_hosts = self.scan_network_range(max_workers=30)
            scan_duration = time.time() - scan_start
            
            analysis['network_scan'] = {
                'active_hosts': active_hosts,
                'count': len(active_hosts),
                'scan_duration_sec': round(scan_duration, 2),
                'method': 'ping_sweep'
            }
        
        # Method 3: Gateway response time analysis
        if self.gateway_ip:
            gateway_times = []
            for _ in range(5):
                start_time = time.time()
                if self._ping_host(self.gateway_ip, timeout=2):
                    response_time = (time.time() - start_time) * 1000
                    gateway_times.append(response_time)
                time.sleep(0.1)
            
            if gateway_times:
                avg_response = sum(gateway_times) / len(gateway_times)
                analysis['gateway_response'] = {
                    'avg_response_ms': round(avg_response, 2),
                    'response_times': [round(t, 2) for t in gateway_times],
                    'method': 'ping_response'
                }
        
        # Calculate congestion score
        congestion_score = self._calculate_congestion_score(analysis)
        analysis['congestion_score'] = congestion_score
        
        return analysis
    
    def _calculate_congestion_score(self, analysis: Dict) -> Dict[str, Any]:
        """Calculate router congestion score based on analysis."""
        score = 100  # Start with perfect score
        factors = []
        
        # Factor 1: Device count
        device_count = 0
        if 'arp_analysis' in analysis and analysis['arp_analysis'].get('count'):
            device_count = max(device_count, analysis['arp_analysis']['count'])
        if 'network_scan' in analysis and analysis['network_scan'].get('count'):
            device_count = max(device_count, analysis['network_scan']['count'])
        
        if device_count > 20:
            score -= 30
            factors.append(f"High device count ({device_count} devices)")
        elif device_count > 10:
            score -= 15
            factors.append(f"Moderate device count ({device_count} devices)")
        
        # Factor 2: Gateway response time
        if 'gateway_response' in analysis:
            avg_response = analysis['gateway_response']['avg_response_ms']
            if avg_response > 50:
                score -= 25
                factors.append(f"Slow gateway response ({avg_response:.1f}ms)")
            elif avg_response > 20:
                score -= 10
                factors.append(f"Moderate gateway response ({avg_response:.1f}ms)")
        
        # Factor 3: Scan performance
        if 'network_scan' in analysis:
            scan_duration = analysis['network_scan']['scan_duration_sec']
            host_count = analysis['network_scan']['count']
            if host_count > 0:
                scan_rate = scan_duration / host_count
                if scan_rate > 2:  # More than 2 seconds per host indicates congestion
                    score -= 20
                    factors.append("Slow network scanning performance")
        
        score = max(0, score)
        
        # Determine congestion level
        if score >= 80:
            level = "low"
        elif score >= 60:
            level = "moderate"  
        elif score >= 40:
            level = "high"
        else:
            level = "severe"
        
        return {
            'score': score,
            'level': level,
            'factors': factors,
            'estimated_clients': device_count
        }
    
    def print_analysis_report(self, analysis: Dict[str, Any]):
        """Print a formatted router analysis report."""
        print("\\n" + "="*60)
        print("ROUTER CONGESTION ANALYSIS")
        print("="*60)
        
        if self.gateway_ip:
            print(f"\\n🏠 Router: {self.gateway_ip}")
            if self.network_range:
                print(f"📡 Network: {self.network_range}")
        
        congestion = analysis.get('congestion_score', {})
        score = congestion.get('score', 0)
        level = congestion.get('level', 'unknown')
        
        level_icons = {
            'low': '🟢',
            'moderate': '🟡', 
            'high': '🟠',
            'severe': '🔴'
        }
        
        icon = level_icons.get(level, '❓')
        print(f"\\n{icon} Congestion Level: {level.title()} (Score: {score}/100)")
        
        # Show device counts
        estimated_clients = congestion.get('estimated_clients', 0)
        print(f"\\n👥 Estimated Connected Devices: {estimated_clients}")
        
        # Show details from different methods
        if 'arp_analysis' in analysis and not analysis['arp_analysis'].get('error'):
            arp_count = analysis['arp_analysis']['count']
            print(f"   📋 ARP Table: {arp_count} devices")
        
        if 'network_scan' in analysis:
            scan_count = analysis['network_scan']['count'] 
            scan_time = analysis['network_scan']['scan_duration_sec']
            print(f"   🔍 Network Scan: {scan_count} active hosts (took {scan_time}s)")
        
        # Show gateway performance
        if 'gateway_response' in analysis:
            response_time = analysis['gateway_response']['avg_response_ms']
            print(f"\\n⚡ Gateway Response Time: {response_time:.1f}ms")
        
        # Show congestion factors
        factors = congestion.get('factors', [])
        if factors:
            print("\\n⚠️  Congestion Factors:")
            for factor in factors:
                print(f"   • {factor}")
        
        # Recommendations
        print("\\nRecommendations:")
        if level in ['high', 'severe']:
            print("   • Disconnect unused devices")
            print("   • Use 5GHz WiFi instead of 2.4GHz if available") 
            print("   • Consider upgrading router firmware")
            print("   • Test during off-peak hours")
        elif level == 'moderate':
            print("   • Monitor network usage during tests")
            print("   • Consider testing during less busy times")
        else:
            print("   ✅ Router performance appears optimal for testing")

def main():
    """Main function for standalone testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze router congestion and client count')
    parser.add_argument('--gateway', help='Gateway IP address (auto-detected if not specified)')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    
    args = parser.parse_args()
    
    # Create analyzer with debug mode
    analyzer = RouterAnalyzer(gateway_ip=args.gateway, debug=args.debug)
    
    if not analyzer.gateway_ip:
        print("❌ Could not detect gateway IP address")
        return 1
    
    analysis = analyzer.estimate_router_load()
    analyzer.print_analysis_report(analysis)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())