#!/usr/bin/env pipenv run python
"""
NetProbe - Internet Connection Reliability Tool
A comprehensive tool for testing internet connection quality over extended periods.
"""

import time
import statistics
import json
import csv
import socket
import subprocess
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional
import click
import requests
from pythonping import ping
import dns.resolver
import dns.exception


class VPNManager:
    """Manage VPN connections for testing."""
    
    def __init__(self):
        self.vpn_type = self._detect_vpn()
        self.original_state = None
    
    def _detect_vpn(self) -> Optional[str]:
        """Detect which VPN client is available."""
        vpn_commands = {
            'nordvpn': ['nordvpn', '--help'],
            'protonvpn-cli': ['protonvpn-cli', '--help'],
            'expressvpn': ['expressvpn', 'help'],
            'surfshark': ['surfshark-vpn', '--help']
        }
        
        # First try CLI tools
        for vpn_name, test_command in vpn_commands.items():
            try:
                result = subprocess.run(test_command, capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return vpn_name
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        
        # On macOS, check for GUI apps that can be controlled via AppleScript
        if sys.platform == 'darwin':
            try:
                # Check if NordVPN app is available
                result = subprocess.run(['osascript', '-e', 'tell application "NordVPN" to get name'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and 'NordVPN' in result.stdout:
                    return 'nordvpn-macos'
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        
        return None
    
    def get_status(self) -> Dict[str, Any]:
        """Get current VPN status."""
        if not self.vpn_type:
            return {'connected': False, 'error': 'No supported VPN client found'}
        
        try:
            if self.vpn_type == 'nordvpn':
                result = subprocess.run(['nordvpn', 'status'], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    output = result.stdout.lower()
                    connected = 'connected' in output and 'disconnected' not in output
                    server = None
                    if connected:
                        for line in result.stdout.split('\n'):
                            if 'server:' in line.lower():
                                server = line.split(':')[1].strip()
                                break
                    return {'connected': connected, 'server': server, 'client': 'nordvpn'}
            
            elif self.vpn_type == 'nordvpn-macos':
                # Use AppleScript to check NordVPN app status on macOS
                applescript = '''
                tell application "NordVPN"
                    try
                        set connectionStatus to connection status
                        if connectionStatus is "Connected" then
                            return "Connected"
                        else
                            return "Disconnected"
                        end if
                    on error
                        return "Disconnected"
                    end try
                end tell
                '''
                result = subprocess.run(['osascript', '-e', applescript], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    connected = 'Connected' in result.stdout
                    return {'connected': connected, 'server': None, 'client': 'nordvpn-macos'}
            
            elif self.vpn_type == 'protonvpn-cli':
                result = subprocess.run(['protonvpn-cli', 'status'], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    connected = 'connected' in result.stdout.lower()
                    return {'connected': connected, 'client': 'protonvpn-cli'}
            
            elif self.vpn_type == 'expressvpn':
                result = subprocess.run(['expressvpn', 'status'], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    connected = 'connected' in result.stdout.lower()
                    return {'connected': connected, 'client': 'expressvpn'}
                    
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return {'connected': False, 'error': str(e)}
        
        return {'connected': False, 'error': 'Failed to get VPN status'}
    
    def connect(self) -> bool:
        """Connect to VPN."""
        if not self.vpn_type:
            return False
        
        try:
            if self.vpn_type == 'nordvpn':
                result = subprocess.run(['nordvpn', 'connect'], capture_output=True, text=True, timeout=30)
                return result.returncode == 0
            
            elif self.vpn_type == 'nordvpn-macos':
                # Use AppleScript to connect NordVPN app on macOS
                applescript = '''
                tell application "NordVPN"
                    activate
                    try
                        connect to quick connect
                        return "Success"
                    on error
                        return "Failed"
                    end try
                end tell
                '''
                result = subprocess.run(['osascript', '-e', applescript], capture_output=True, text=True, timeout=30)
                return result.returncode == 0 and 'Success' in result.stdout
            
            elif self.vpn_type == 'protonvpn-cli':
                result = subprocess.run(['protonvpn-cli', 'connect', '--fastest'], capture_output=True, text=True, timeout=30)
                return result.returncode == 0
            
            elif self.vpn_type == 'expressvpn':
                result = subprocess.run(['expressvpn', 'connect'], capture_output=True, text=True, timeout=30)
                return result.returncode == 0
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
        
        return False
    
    def disconnect(self) -> bool:
        """Disconnect from VPN."""
        if not self.vpn_type:
            return True  # Already disconnected
        
        try:
            if self.vpn_type == 'nordvpn':
                result = subprocess.run(['nordvpn', 'disconnect'], capture_output=True, text=True, timeout=30)
                return result.returncode == 0
            
            elif self.vpn_type == 'protonvpn-cli':
                result = subprocess.run(['protonvpn-cli', 'disconnect'], capture_output=True, text=True, timeout=30)
                return result.returncode == 0
            
            elif self.vpn_type == 'expressvpn':
                result = subprocess.run(['expressvpn', 'disconnect'], capture_output=True, text=True, timeout=30)
                return result.returncode == 0
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
        
        return False
    
    def save_state(self):
        """Save current VPN state."""
        self.original_state = self.get_status()
    
    def restore_state(self):
        """Restore VPN to original state."""
        if not self.original_state:
            return True
        
        current_status = self.get_status()
        original_connected = self.original_state.get('connected', False)
        current_connected = current_status.get('connected', False)
        
        if original_connected and not current_connected:
            print("Restoring VPN connection...")
            return self.connect()
        elif not original_connected and current_connected:
            print("Restoring VPN disconnection...")
            return self.disconnect()
        
        return True  # No change needed


class ConnectionTester:
    """Main testing engine for connection quality metrics."""
    
    def __init__(self, endpoints=None, duration=60):
        self.endpoints = endpoints or [
            '8.8.8.8',  # Google DNS
            '1.1.1.1',  # Cloudflare DNS
            '208.67.222.222'  # OpenDNS
        ]
        self.duration = duration
        self.results = {
            'latency': [],
            'packet_loss': [],
            'jitter': [],
            'dns_times': [],
            'bandwidth': None,
            'start_time': None,
            'end_time': None
        }
    
    def test_latency_and_packet_loss(self, host: str, count: int = 10) -> Dict[str, Any]:
        """Test latency and packet loss for a given host."""
        print(f"Testing latency and packet loss to {host}...")
        
        try:
            # First try ICMP ping
            response = ping(host, count=count, timeout=2)
            
            # Extract timing data
            times = [r.time_elapsed_ms for r in response if r.success]
            packet_loss = ((count - len(times)) / count) * 100
            
            if times:
                avg_latency = statistics.mean(times)
                min_latency = min(times)
                max_latency = max(times)
                jitter = statistics.stdev(times) if len(times) > 1 else 0
            else:
                avg_latency = min_latency = max_latency = jitter = None
            
            return {
                'host': host,
                'avg_latency_ms': avg_latency,
                'min_latency_ms': min_latency,
                'max_latency_ms': max_latency,
                'packet_loss_percent': packet_loss,
                'jitter_ms': jitter,
                'successful_pings': len(times),
                'total_pings': count,
                'method': 'ICMP'
            }
            
        except Exception as e:
            # Fallback to TCP connection test
            print(f"ICMP ping failed ({str(e)}), trying TCP connection test...")
            return self._tcp_ping_test(host, count)
    
    def _tcp_ping_test(self, host: str, count: int = 10, port: int = 80) -> Dict[str, Any]:
        """Fallback TCP connection test when ICMP ping fails."""
        times = []
        successful = 0
        
        for i in range(count):
            try:
                start_time = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                result = sock.connect_ex((host, port))
                end_time = time.time()
                sock.close()
                
                if result == 0:  # Connection successful
                    times.append((end_time - start_time) * 1000)  # Convert to ms
                    successful += 1
                    
            except Exception:
                pass
        
        packet_loss = ((count - successful) / count) * 100
        
        if times:
            avg_latency = statistics.mean(times)
            min_latency = min(times)
            max_latency = max(times)
            jitter = statistics.stdev(times) if len(times) > 1 else 0
        else:
            avg_latency = min_latency = max_latency = jitter = None
        
        return {
            'host': host,
            'avg_latency_ms': avg_latency,
            'min_latency_ms': min_latency,
            'max_latency_ms': max_latency,
            'packet_loss_percent': packet_loss,
            'jitter_ms': jitter,
            'successful_pings': successful,
            'total_pings': count,
            'method': f'TCP:{port}'
        }
    
    def test_dns_resolution(self, domain: str = 'google.com') -> Dict[str, Any]:
        """Test DNS resolution time."""
        print(f"Testing DNS resolution for {domain}...")
        
        try:
            start_time = time.time()
            resolver = dns.resolver.Resolver()
            resolver.timeout = 5
            resolver.lifetime = 5
            
            answers = resolver.resolve(domain, 'A')
            end_time = time.time()
            
            resolution_time_ms = (end_time - start_time) * 1000
            
            return {
                'domain': domain,
                'resolution_time_ms': resolution_time_ms,
                'resolved_ips': [str(answer) for answer in answers]
            }
            
        except Exception as e:
            print(f"DNS resolution error for {domain}: {str(e)}")
            return {
                'domain': domain,
                'error': str(e)
            }
    
    def test_bandwidth(self) -> Dict[str, Any]:
        """Simple bandwidth test using a small file download."""
        print("Testing bandwidth (download)...")
        
        test_urls = [
            'https://speed.cloudflare.com/__down?bytes=10485760',  # 10MB
            'http://speedtest.ftp.otenet.gr/files/test10Mb.db',    # Fallback
        ]
        
        for url in test_urls:
            try:
                start_time = time.time()
                response = requests.get(url, timeout=30, stream=True)
                
                if response.status_code == 200:
                    total_size = 0
                    chunk_times = []
                    
                    for chunk in response.iter_content(chunk_size=8192):
                        chunk_start = time.time()
                        total_size += len(chunk)
                        chunk_times.append(time.time() - chunk_start)
                        
                        # Break if we've downloaded enough for the test
                        if total_size >= 5 * 1024 * 1024:  # 5MB limit
                            break
                    
                    end_time = time.time()
                    total_time = end_time - start_time
                    
                    if total_time > 0:
                        download_speed_mbps = (total_size * 8) / (total_time * 1000000)  # Convert to Mbps
                        
                        return {
                            'download_speed_mbps': download_speed_mbps,
                            'total_bytes': total_size,
                            'total_time_seconds': total_time,
                            'test_url': url
                        }
                
            except Exception as e:
                print(f"Bandwidth test failed for {url}: {str(e)}")
                continue
        
        return {'error': 'All bandwidth tests failed'}
    
    def run_extended_test(self) -> Dict[str, Any]:
        """Run the complete extended test suite."""
        print(f"Starting {self.duration}-second connection reliability test...")
        print("=" * 50)
        
        self.results['start_time'] = datetime.now().isoformat()
        start_time = time.time()
        
        # Test each endpoint multiple times during the duration
        interval = max(5, self.duration // 10)  # Test every 5 seconds or 10 times total
        test_count = 0
        
        while time.time() - start_time < self.duration:
            test_count += 1
            print(f"\\nTest iteration {test_count}...")
            
            # Test latency and packet loss for each endpoint
            for endpoint in self.endpoints:
                result = self.test_latency_and_packet_loss(endpoint, count=5)
                
                if 'avg_latency_ms' in result and result['avg_latency_ms'] is not None:
                    self.results['latency'].append({
                        'timestamp': datetime.now().isoformat(),
                        'endpoint': endpoint,
                        **result
                    })
            
            # Test DNS resolution
            dns_result = self.test_dns_resolution()
            if 'resolution_time_ms' in dns_result:
                self.results['dns_times'].append({
                    'timestamp': datetime.now().isoformat(),
                    **dns_result
                })
            
            # Sleep until next interval
            elapsed = time.time() - start_time
            next_test_time = test_count * interval
            if elapsed < next_test_time and elapsed < self.duration:
                sleep_time = min(next_test_time - elapsed, self.duration - elapsed)
                if sleep_time > 0:
                    print(f"Waiting {sleep_time:.1f} seconds until next test...")
                    time.sleep(sleep_time)
        
        # Run bandwidth test once at the end
        print("\\nRunning bandwidth test...")
        bandwidth_result = self.test_bandwidth()
        self.results['bandwidth'] = bandwidth_result
        
        self.results['end_time'] = datetime.now().isoformat()
        
        print("\\nTest completed!")
        return self.results


class StatisticsCalculator:
    """Calculate statistics and generate quality scores."""
    
    @staticmethod
    def calculate_statistics(results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate comprehensive statistics from test results."""
        stats = {
            'latency_stats': {},
            'packet_loss_stats': {},
            'jitter_stats': {},
            'dns_stats': {},
            'quality_score': 0
        }
        
        # Latency statistics
        latencies = [r['avg_latency_ms'] for r in results['latency'] if r.get('avg_latency_ms') is not None]
        if latencies:
            stats['latency_stats'] = {
                'min_ms': min(latencies),
                'max_ms': max(latencies),
                'avg_ms': statistics.mean(latencies),
                'median_ms': statistics.median(latencies),
                'p95_ms': StatisticsCalculator._percentile(latencies, 95),
                'std_dev_ms': statistics.stdev(latencies) if len(latencies) > 1 else 0
            }
        
        # Packet loss statistics  
        packet_losses = [r['packet_loss_percent'] for r in results['latency'] if 'packet_loss_percent' in r]
        if packet_losses:
            stats['packet_loss_stats'] = {
                'min_percent': min(packet_losses),
                'max_percent': max(packet_losses),
                'avg_percent': statistics.mean(packet_losses),
                'total_tests': len(packet_losses)
            }
        
        # Jitter statistics
        jitters = [r['jitter_ms'] for r in results['latency'] if r.get('jitter_ms') is not None]
        if jitters:
            stats['jitter_stats'] = {
                'min_ms': min(jitters),
                'max_ms': max(jitters),
                'avg_ms': statistics.mean(jitters),
                'std_dev_ms': statistics.stdev(jitters) if len(jitters) > 1 else 0
            }
        
        # DNS statistics
        dns_times = [r['resolution_time_ms'] for r in results['dns_times'] if 'resolution_time_ms' in r]
        if dns_times:
            stats['dns_stats'] = {
                'min_ms': min(dns_times),
                'max_ms': max(dns_times),
                'avg_ms': statistics.mean(dns_times),
                'median_ms': statistics.median(dns_times)
            }
        
        # Calculate quality score (0-100)
        stats['quality_score'] = StatisticsCalculator._calculate_quality_score(stats, results)
        
        return stats
    
    @staticmethod
    def _percentile(data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0
        data_sorted = sorted(data)
        index = (percentile / 100) * (len(data_sorted) - 1)
        if index.is_integer():
            return data_sorted[int(index)]
        else:
            lower = data_sorted[int(index)]
            upper = data_sorted[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))
    
    @staticmethod
    def _calculate_quality_score(stats: Dict[str, Any], results: Dict[str, Any]) -> int:
        """Calculate overall connection quality score (0-100)."""
        score = 100
        
        # Latency penalty
        if stats['latency_stats']:
            avg_latency = stats['latency_stats']['avg_ms']
            if avg_latency > 100:
                score -= 30
            elif avg_latency > 50:
                score -= 15
            elif avg_latency > 25:
                score -= 5
        
        # Packet loss penalty
        if stats['packet_loss_stats']:
            avg_loss = stats['packet_loss_stats']['avg_percent']
            if avg_loss > 1:
                score -= 40
            elif avg_loss > 0.1:
                score -= 20
            elif avg_loss > 0:
                score -= 10
        
        # Jitter penalty
        if stats['jitter_stats']:
            avg_jitter = stats['jitter_stats']['avg_ms']
            if avg_jitter > 25:
                score -= 20
            elif avg_jitter > 15:
                score -= 10
            elif avg_jitter > 5:
                score -= 5
        
        # DNS penalty
        if stats['dns_stats']:
            avg_dns = stats['dns_stats']['avg_ms']
            if avg_dns > 100:
                score -= 10
            elif avg_dns > 50:
                score -= 5
        
        return max(0, min(100, score))


class Reporter:
    """Handle output formatting and export functionality."""
    
    @staticmethod
    def print_summary(results: Dict[str, Any], stats: Dict[str, Any]):
        """Print a human-readable summary of the test results."""
        print("\\n" + "=" * 60)
        print("CONNECTION RELIABILITY TEST RESULTS")
        print("=" * 60)
        
        print(f"\\nTest Duration: {results['start_time']} to {results['end_time']}")
        print(f"Overall Quality Score: {stats['quality_score']}/100")
        
        # Latency results
        if stats['latency_stats']:
            print(f"\\nLatency Statistics:")
            print(f"  Average: {stats['latency_stats']['avg_ms']:.2f} ms")
            print(f"  Minimum: {stats['latency_stats']['min_ms']:.2f} ms")
            print(f"  Maximum: {stats['latency_stats']['max_ms']:.2f} ms")
            print(f"  95th Percentile: {stats['latency_stats']['p95_ms']:.2f} ms")
        
        # Packet loss results
        if stats['packet_loss_stats']:
            print(f"\\nPacket Loss Statistics:")
            print(f"  Average: {stats['packet_loss_stats']['avg_percent']:.2f}%")
            print(f"  Maximum: {stats['packet_loss_stats']['max_percent']:.2f}%")
        
        # Jitter results
        if stats['jitter_stats']:
            print(f"\\nJitter Statistics:")
            print(f"  Average: {stats['jitter_stats']['avg_ms']:.2f} ms")
            print(f"  Maximum: {stats['jitter_stats']['max_ms']:.2f} ms")
        
        # DNS results
        if stats['dns_stats']:
            print(f"\\nDNS Resolution Statistics:")
            print(f"  Average: {stats['dns_stats']['avg_ms']:.2f} ms")
            print(f"  Minimum: {stats['dns_stats']['min_ms']:.2f} ms")
            print(f"  Maximum: {stats['dns_stats']['max_ms']:.2f} ms")
        
        # Bandwidth results
        if results['bandwidth'] and 'download_speed_mbps' in results['bandwidth']:
            print(f"\\nBandwidth Test:")
            print(f"  Download Speed: {results['bandwidth']['download_speed_mbps']:.2f} Mbps")
        
        print("\\n" + "=" * 60)
    
    @staticmethod
    def export_json(results: Dict[str, Any], stats: Dict[str, Any], filename: str):
        """Export results to JSON file."""
        export_data = {
            'test_results': results,
            'statistics': stats,
            'export_time': datetime.now().isoformat()
        }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"Results exported to {filename}")
    
    @staticmethod
    def export_csv(results: Dict[str, Any], filename: str):
        """Export latency results to CSV file."""
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'endpoint', 'latency_ms', 'packet_loss_percent', 'jitter_ms'])
            
            for result in results['latency']:
                writer.writerow([
                    result.get('timestamp', ''),
                    result.get('endpoint', ''),
                    result.get('avg_latency_ms', ''),
                    result.get('packet_loss_percent', ''),
                    result.get('jitter_ms', '')
                ])
        
        print(f"Latency data exported to {filename}")


@click.command()
@click.option('--duration', '-d', default=60, help='Test duration in seconds (default: 60)')
@click.option('--endpoints', '-e', multiple=True, help='Additional test endpoints')
@click.option('--json', 'export_json', help='Export results to JSON file')
@click.option('--csv', 'export_csv', help='Export latency data to CSV file')
@click.option('--compare-vpn', is_flag=True, help='Test with and without VPN (toggles VPN state)')
@click.option('--vpn-only', is_flag=True, help='Test only with VPN enabled')
@click.option('--no-vpn', is_flag=True, help='Test only without VPN')
def main(duration, endpoints, export_json, export_csv, compare_vpn, vpn_only, no_vpn):
    """
    NetProbe - Internet Connection Reliability Tool
    
    Test internet connection quality with comprehensive metrics including
    latency, packet loss, jitter, DNS resolution, and bandwidth.
    """
    print("NetProbe - Internet Connection Reliability Tool")
    print("=" * 50)
    
    # Validate VPN options
    vpn_options = sum([compare_vpn, vpn_only, no_vpn])
    if vpn_options > 1:
        print("Error: Only one VPN option can be specified at a time.")
        exit(1)
    
    # Initialize VPN manager
    vpn_manager = VPNManager()
    
    # Initialize tester
    test_endpoints = list(endpoints) if endpoints else None
    tester = ConnectionTester(endpoints=test_endpoints, duration=duration)
    exit_code = 0
    
    try:
        # Check VPN status and capabilities
        if compare_vpn or vpn_only or no_vpn:
            vpn_status = vpn_manager.get_status()
            if vpn_manager.vpn_type:
                print(f"Detected VPN client: {vpn_manager.vpn_type}")
                print(f"Current VPN status: {'Connected' if vpn_status.get('connected') else 'Disconnected'}")
                if vpn_status.get('server'):
                    print(f"Connected to server: {vpn_status['server']}")
                print()
            else:
                print("No supported VPN client found. Supported: NordVPN, ProtonVPN, ExpressVPN")
                if compare_vpn or vpn_only:
                    print("Cannot perform VPN testing without a supported VPN client.")
                    return
        
        # Save original VPN state
        vpn_manager.save_state()
        
        all_results = []
        all_stats = []
        
        # Determine test scenarios
        test_scenarios = []
        if compare_vpn:
            test_scenarios = [('without_vpn', False), ('with_vpn', True)]
        elif vpn_only:
            test_scenarios = [('with_vpn', True)]
        elif no_vpn:
            test_scenarios = [('without_vpn', False)]
        else:
            test_scenarios = [('default', None)]  # Don't change VPN state
        
        for scenario_name, vpn_should_be_connected in test_scenarios:
            print(f"\\n{'='*60}")
            print(f"RUNNING TEST: {scenario_name.replace('_', ' ').upper()}")
            print(f"{'='*60}")
            
            # Configure VPN state if needed
            if vpn_should_be_connected is not None:
                current_status = vpn_manager.get_status()
                current_connected = current_status.get('connected', False)
                
                if vpn_should_be_connected and not current_connected:
                    print("Connecting to VPN...")
                    if not vpn_manager.connect():
                        print("Failed to connect to VPN. Skipping this test scenario.")
                        continue
                    time.sleep(5)  # Wait for connection to stabilize
                    
                elif not vpn_should_be_connected and current_connected:
                    print("Disconnecting from VPN...")
                    if not vpn_manager.disconnect():
                        print("Failed to disconnect from VPN. Skipping this test scenario.")
                        continue
                    time.sleep(5)  # Wait for disconnection to stabilize
            
            # Run the test
            results = tester.run_extended_test()
            results['test_scenario'] = scenario_name
            results['vpn_status'] = vpn_manager.get_status()
            
            # Calculate statistics
            stats = StatisticsCalculator.calculate_statistics(results)
            
            # Store results for comparison
            all_results.append(results)
            all_stats.append(stats)
            
            # Print summary for this scenario
            Reporter.print_summary(results, stats)
        
        # Print comparison if multiple scenarios
        if len(all_results) > 1:
            print("\\n" + "="*60)
            print("VPN COMPARISON SUMMARY")
            print("="*60)
            
            for i, (results, stats) in enumerate(zip(all_results, all_stats)):
                scenario = results['test_scenario'].replace('_', ' ').title()
                vpn_status = results['vpn_status']
                vpn_info = f" ({vpn_status.get('server', 'Unknown server')})" if vpn_status.get('connected') else ""
                
                print(f"\\n{scenario}{vpn_info}:")
                print(f"  Quality Score: {stats['quality_score']}/100")
                if stats.get('latency_stats'):
                    print(f"  Average Latency: {stats['latency_stats']['avg_ms']:.2f} ms")
                if stats.get('packet_loss_stats'):
                    print(f"  Average Packet Loss: {stats['packet_loss_stats']['avg_percent']:.2f}%")
                if results['bandwidth'] and 'download_speed_mbps' in results['bandwidth']:
                    print(f"  Download Speed: {results['bandwidth']['download_speed_mbps']:.2f} Mbps")
            
            # Calculate differences
            if len(all_stats) == 2:
                no_vpn_stats = all_stats[0] if all_results[0]['test_scenario'] == 'without_vpn' else all_stats[1]
                vpn_stats = all_stats[1] if all_results[1]['test_scenario'] == 'with_vpn' else all_stats[0]
                
                print(f"\\nDifferences (VPN impact):")
                
                if no_vpn_stats.get('latency_stats') and vpn_stats.get('latency_stats'):
                    latency_diff = vpn_stats['latency_stats']['avg_ms'] - no_vpn_stats['latency_stats']['avg_ms']
                    print(f"  Latency change: {latency_diff:+.2f} ms")
                
                if no_vpn_stats.get('packet_loss_stats') and vpn_stats.get('packet_loss_stats'):
                    loss_diff = vpn_stats['packet_loss_stats']['avg_percent'] - no_vpn_stats['packet_loss_stats']['avg_percent']
                    print(f"  Packet loss change: {loss_diff:+.2f}%")
                
                score_diff = vpn_stats['quality_score'] - no_vpn_stats['quality_score']
                print(f"  Quality score change: {score_diff:+d} points")
        
        # Export results if requested
        if export_json:
            export_data = {
                'test_results': all_results,
                'statistics': all_stats,
                'export_time': datetime.now().isoformat()
            }
            
            with open(export_json, 'w') as f:
                json.dump(export_data, f, indent=2)
            print(f"\\nResults exported to {export_json}")
        
        if export_csv and all_results:
            # Export latency data from all scenarios
            with open(export_csv, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['scenario', 'timestamp', 'endpoint', 'latency_ms', 'packet_loss_percent', 'jitter_ms'])
                
                for results in all_results:
                    scenario = results['test_scenario']
                    for result in results['latency']:
                        writer.writerow([
                            scenario,
                            result.get('timestamp', ''),
                            result.get('endpoint', ''),
                            result.get('avg_latency_ms', ''),
                            result.get('packet_loss_percent', ''),
                            result.get('jitter_ms', '')
                        ])
            print(f"Latency data exported to {export_csv}")
        
        # Determine exit code based on worst quality score
        if all_stats:
            min_quality_score = min(stats['quality_score'] for stats in all_stats)
            if min_quality_score < 70:
                print(f"\\nWarning: Connection quality is below acceptable threshold (worst score: {min_quality_score})!")
                exit_code = 1
            else:
                print(f"\\nConnection quality is good (best score: {max(stats['quality_score'] for stats in all_stats)}).")
                exit_code = 0
        else:
            exit_code = 1
            
    except KeyboardInterrupt:
        print("\\n\\nTest interrupted by user.")
        exit_code = 1
    except Exception as e:
        print(f"\\nError during testing: {str(e)}")
        exit_code = 1
    finally:
        # Always restore original VPN state
        try:
            if vpn_manager and hasattr(vpn_manager, 'original_state') and vpn_manager.original_state:
                print("\\nRestoring original VPN state...")
                vpn_manager.restore_state()
        except Exception as e:
            print(f"Warning: Failed to restore VPN state: {str(e)}")
        
        exit(exit_code)


if __name__ == '__main__':
    main()