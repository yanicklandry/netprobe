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
import os
import platform
import re
import threading
import queue
from datetime import datetime
from typing import List, Dict, Any, Optional, TypedDict
import click
import requests
from pythonping import ping
import dns.resolver
import dns.exception
from tqdm import tqdm
import geocoder
from vpn_manager import VPNManager
from data_capture import record_run, resolve_user, NotionConfig, DEFAULT_LOG_PATH


class WiFiSample(TypedDict):
    """A single WiFi signal sample collected during a test run."""
    timestamp: float    # Unix epoch seconds
    rssi_dbm: int       # Signal level in dBm (typically -30 to -90)
    noise_dbm: int      # Noise floor in dBm (typically -90 to -100)
    snr_db: int         # Signal-to-noise ratio: rssi_dbm - noise_dbm


class WiFiStabilityResult(TypedDict):
    """Result of WiFi stability score calculation."""
    wifi_stability_score: Optional[int]  # 0-100, or None when unavailable
    wifi_score_type: str                 # "hardware" | "behavior-only" | "unavailable"
    wifi_samples: List[WiFiSample]       # Raw time-series samples
    avg_snr_db: Optional[float]          # Mean SNR across all samples; None if no hardware samples
    wifi_ssid: Optional[str]             # Connected WiFi network name (SSID); None on non-macOS or parse failure


class LocationManager:
    """Manage location detection and naming for test results."""
    
    def __init__(self):
        self.current_location = None
        
    def get_location(self) -> Dict[str, Any]:
        """Get current GPS location and nearby places."""
        try:
            # Get current location using IP geolocation
            g = geocoder.ip('me')
            if g.latlng:
                lat, lng = g.latlng
                location_data = {
                    'latitude': lat,
                    'longitude': lng,
                    'city': g.city or 'Unknown',
                    'country': g.country or 'Unknown',
                    'ip_address': g.ip,
                    'method': 'ip_geolocation'
                }
                
                # Try to get more precise location with additional services
                try:
                    import time
                    time.sleep(0.5)  # Rate limiting for reverse geocoding
                    precise = geocoder.osm([lat, lng], method='reverse')
                    if precise.address:
                        location_data['address'] = precise.address
                        location_data['method'] = 'reverse_geocoding'
                except Exception as e:
                    # Silently ignore reverse geocoding errors (rate limiting, etc.)
                    if '403' not in str(e):  # Only log non-rate-limit errors in debug
                        pass
                
                return location_data
            else:
                return {'error': 'Could not determine location'}
                
        except Exception as e:
            return {'error': f'Location detection failed: {str(e)}'}
    
    def search_nearby_places(self, location_name: str) -> Dict[str, Any]:
        """Search for a specific place name near current location."""
        import time
        
        # Try multiple geocoding services as fallbacks
        geocoding_services = [
            ('ip', lambda name: geocoder.ip('me')),  # Get current location as fallback
            ('arcgis', lambda name: geocoder.arcgis(name)),  # ArcGIS as alternative
            ('osm', lambda name: geocoder.osm(name))  # OpenStreetMap as last resort
        ]
        
        for service_name, service_func in geocoding_services:
            try:
                if service_name == 'osm':
                    time.sleep(1)  # Add delay for OSM rate limiting
                
                if service_name == 'ip':
                    # For IP-based, just get current location and use provided name
                    g = service_func(location_name)
                    if g.latlng:
                        return {
                            'name': location_name,
                            'latitude': g.latlng[0],
                            'longitude': g.latlng[1],
                            'address': f"Near {g.city}, {g.country}" if g.city else "Location detected",
                            'method': f'{service_name}_fallback'
                        }
                else:
                    g = service_func(location_name)
                    if g.latlng:
                        return {
                            'name': location_name,
                            'latitude': g.latlng[0],
                            'longitude': g.latlng[1],
                            'address': g.address,
                            'method': f'{service_name}_search'
                        }
                        
            except Exception as e:
                error_msg = str(e)
                if '403' in error_msg or 'Forbidden' in error_msg:
                    # Skip to next service if this one is rate limited
                    continue
                elif service_name == geocoding_services[-1][0]:  # Last service failed
                    return {'error': f'All location services failed. Last error: {error_msg}'}
        
        return {'error': f'Could not find location: {location_name}. All geocoding services exhausted.'}
    
    def get_location_summary(self, location_data: Dict[str, Any]) -> str:
        """Get a human-readable location summary."""
        if 'error' in location_data:
            return "Location unknown"
        
        if 'name' in location_data:
            return location_data['name']
        elif 'address' in location_data:
            # Extract key parts of address
            address = location_data['address']
            parts = address.split(',')
            if len(parts) >= 2:
                return f"{parts[0].strip()}, {parts[-1].strip()}"
            return address
        elif 'city' in location_data and 'country' in location_data:
            return f"{location_data['city']}, {location_data['country']}"
        else:
            return "Location detected"


class ConnectionTester:
    """Main testing engine for connection quality metrics."""
    
    def __init__(self, endpoints=None, duration=60):
        self.endpoints = endpoints or [
            '8.8.8.8',  # Google DNS
            '1.1.1.1',  # Cloudflare DNS
            '208.67.222.222'  # OpenDNS
        ]
        self.duration = duration
        self.force_icmp = False  # Will be set by main() if --icmp flag is used
        self.debug = False  # Will be set by main() if --debug flag is used
        self.local_gateway = self._discover_local_gateway()
        self.results = {
            'latency': [],
            'packet_loss': [],
            'jitter': [],
            'dns_times': [],
            'bandwidth': None,
            'local_router': [],
            'start_time': None,
            'end_time': None
        }
    
    def _discover_local_gateway(self) -> str:
        """Discover the local gateway/router IP address."""
        try:
            if sys.platform == 'darwin' or sys.platform.startswith('linux'):
                # Use route command to find gateway
                result = subprocess.run(['route', '-n', 'get', 'default'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'gateway:' in line.lower():
                            return line.split(':')[1].strip()
                
                # Fallback: try netstat
                result = subprocess.run(['netstat', '-rn'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if line.startswith('default') or line.startswith('0.0.0.0'):
                            parts = line.split()
                            if len(parts) > 1:
                                return parts[1]
                                
            elif sys.platform == 'win32':
                # Windows: use route print
                result = subprocess.run(['route', 'print', '0.0.0.0'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if '0.0.0.0' in line and '0.0.0.0' in line[:15]:
                            parts = line.split()
                            if len(parts) >= 3:
                                return parts[2]
        except:
            pass
        
        return None
    
    def test_local_router(self, count: int = 5) -> Dict[str, Any]:
        """Test connectivity to local router/gateway."""
        if not self.local_gateway:
            return {'error': 'Local gateway not found'}
        
        if self.debug:
            print(f"Testing connectivity to local router ({self.local_gateway})...")
        
        # Test using TCP connection test since ICMP might be blocked
        return self._tcp_ping_test(self.local_gateway, count, port=80)
    
    def test_latency_and_packet_loss(self, host: str, count: int = 10) -> Dict[str, Any]:
        """Test latency and packet loss for a given host."""
        if self.debug:
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
            # Fallback to TCP connection test (common on macOS due to permissions)
            if not self.force_icmp:
                if self.debug:
                    if "Operation not permitted" in str(e) or "Permission denied" in str(e):
                        print(f"Using TCP connection test (ICMP requires elevated permissions)...")
                    else:
                        print(f"ICMP ping failed ({str(e)}), trying TCP connection test...")
                return self._tcp_ping_test(host, count)
            else:
                # User forced ICMP but it failed - show error and exit
                print(f"ICMP ping failed: {str(e)}")
                print("Hint: Try running with sudo for ICMP permissions, or remove --icmp flag")
                return {
                    'host': host,
                    'error': f'ICMP ping failed: {str(e)}'
                }
    
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
        if self.debug:
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
            if self.debug:
                print(f"DNS resolution error for {domain}: {str(e)}")
            return {
                'domain': domain,
                'error': str(e)
            }
    
    def test_bandwidth(self) -> Dict[str, Any]:
        """Advanced bandwidth test with parallel connections and multiple servers."""
        if self.debug:
            print("Testing bandwidth (download)...")
        
        # High-quality test servers with larger files for sustained throughput
        test_urls = [
            'https://speed.cloudflare.com/__down?bytes=104857600',  # 100MB Cloudflare
            'https://proof.ovh.net/files/100Mb.dat',               # 100MB OVH
            'https://speedtest.selectel.ru/100MB',                 # 100MB Selectel
            'https://lg-mia.fdcservers.net/100MBtest.zip',        # 100MB FDC Miami
            'http://speedtest.ftp.otenet.gr/files/test100Mb.db',   # 100MB Greek fallback
        ]
        
        # Try parallel downloads first for maximum throughput
        parallel_result = self._test_bandwidth_parallel(test_urls[:3])  # Use top 3 servers
        if parallel_result and 'download_speed_mbps' in parallel_result:
            return parallel_result
        
        # Fallback to single connection with larger files
        for url in test_urls:
            try:
                start_time = time.time()
                
                # Use larger chunk size and optimized headers
                headers = {
                    'User-Agent': 'NetProbe/1.0 (Speed Test)',
                    'Accept-Encoding': 'identity',  # Disable compression for accurate measurement
                    'Connection': 'keep-alive'
                }
                
                response = requests.get(url, timeout=45, stream=True, headers=headers)
                
                if response.status_code == 200:
                    total_size = 0
                    chunk_size = 65536  # 64KB chunks for better performance
                    min_test_size = 25 * 1024 * 1024  # 25MB minimum for sustained speed
                    max_test_time = 15  # Max 15 seconds per test
                    
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if not chunk:
                            break
                        total_size += len(chunk)
                        
                        current_time = time.time()
                        elapsed = current_time - start_time
                        
                        # Stop if we have enough data or hit time limit
                        if (total_size >= min_test_size and elapsed >= 3) or elapsed >= max_test_time:
                            break
                    
                    end_time = time.time()
                    total_time = end_time - start_time
                    
                    # Require minimum test duration for accuracy
                    if total_time >= 2.0 and total_size > 0:
                        download_speed_mbps = (total_size * 8) / (total_time * 1000000)  # Convert to Mbps
                        
                        if self.debug:
                            print(f"  Downloaded {total_size / 1024 / 1024:.1f}MB in {total_time:.2f}s = {download_speed_mbps:.1f}Mbps")
                        
                        return {
                            'download_speed_mbps': download_speed_mbps,
                            'total_bytes': total_size,
                            'total_time_seconds': total_time,
                            'test_url': url
                        }
                
            except Exception as e:
                if self.debug:
                    print(f"Bandwidth test failed for {url}: {str(e)}")
                continue
        
        return {'error': 'All bandwidth tests failed'}
    
    def _test_bandwidth_parallel(self, urls: List[str], num_connections: int = 2) -> Dict[str, Any]:
        """Test bandwidth using parallel connections for maximum throughput."""
        import threading
        import queue
        
        if self.debug:
            print(f"  Trying parallel downloads with {num_connections} connections...")
        
        results_queue = queue.Queue()
        threads = []
        start_time = time.time()
        
        def download_worker(url_idx: int, url: str):
            try:
                headers = {
                    'User-Agent': f'NetProbe/1.0-{url_idx}',
                    'Accept-Encoding': 'identity',
                    'Connection': 'keep-alive'
                }
                
                response = requests.get(url, timeout=30, stream=True, headers=headers)
                if response.status_code == 200:
                    bytes_downloaded = 0
                    for chunk in response.iter_content(chunk_size=65536):
                        if not chunk:
                            break
                        bytes_downloaded += len(chunk)
                        
                        # Stop after reasonable amount or time limit
                        if time.time() - start_time > 10:  # 10 second limit
                            break
                        if bytes_downloaded > 50 * 1024 * 1024:  # 50MB per connection
                            break
                    
                    results_queue.put(bytes_downloaded)
                else:
                    results_queue.put(0)
            except Exception as e:
                if self.debug:
                    print(f"  Parallel download {url_idx} failed: {str(e)}")
                results_queue.put(0)
        
        # Start parallel downloads
        for i in range(min(num_connections, len(urls))):
            url = urls[i]
            thread = threading.Thread(target=download_worker, args=(i, url))
            thread.start()
            threads.append(thread)
        
        # Wait for all threads with timeout
        for thread in threads:
            thread.join(timeout=15)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Collect results
        total_bytes = 0
        successful_connections = 0
        
        while not results_queue.empty():
            try:
                bytes_result = results_queue.get_nowait()
                if bytes_result > 0:
                    total_bytes += bytes_result
                    successful_connections += 1
            except queue.Empty:
                break
        
        if total_bytes > 0 and total_time > 2.0 and successful_connections > 0:
            download_speed_mbps = (total_bytes * 8) / (total_time * 1000000)
            
            if self.debug:
                print(f"  Parallel: {total_bytes / 1024 / 1024:.1f}MB via {successful_connections} connections in {total_time:.2f}s = {download_speed_mbps:.1f}Mbps")
            
            return {
                'download_speed_mbps': download_speed_mbps,
                'total_bytes': total_bytes,
                'total_time_seconds': total_time,
                'test_url': f'parallel-{successful_connections}x',
                'parallel_connections': successful_connections
            }
        
        return {}
    
    def run_extended_test(self) -> Dict[str, Any]:
        """Run the complete extended test suite."""
        if self.debug:
            print(f"Starting {self.duration}-second connection reliability test...")
            print("=" * 50)

        self.results['start_time'] = datetime.now().isoformat()
        start_time = time.time()

        # Calculate test intervals and total iterations
        interval = max(5, self.duration // 10)  # Test every 5 seconds or 10 times total
        estimated_iterations = max(1, int(self.duration / interval))

        if not self.debug:
            # Create progress bar for normal mode
            pbar = tqdm(
                total=100,
                desc="Testing connection reliability",
                bar_format='{desc}: {percentage:3.0f}%|{bar}| {elapsed}',
                ncols=70,
                leave=False
            )

        # Start WiFi sampler before the test loop
        sampler = WiFiSampler(interval_seconds=5)
        sampler.start()

        test_count = 0

        try:
            while time.time() - start_time < self.duration:
                test_count += 1

                if self.debug:
                    print(f"\nTest iteration {test_count}...")

                # Test latency and packet loss for each endpoint
                # Test local router first
                if self.local_gateway and test_count == 1:  # Only test once
                    router_result = self.test_local_router(count=3)
                    if 'avg_latency_ms' in router_result:
                        self.results['local_router'].append({
                            'timestamp': datetime.now().isoformat(),
                            'gateway': self.local_gateway,
                            **router_result
                        })

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

                # Update progress bar
                if not self.debug:
                    elapsed = time.time() - start_time
                    progress = min(100, (elapsed / self.duration) * 100)
                    pbar.update(progress - pbar.n)  # Update by difference

                # Sleep until next interval
                elapsed = time.time() - start_time
                next_test_time = test_count * interval
                if elapsed < next_test_time and elapsed < self.duration:
                    sleep_time = min(next_test_time - elapsed, self.duration - elapsed)
                    if sleep_time > 0:
                        if self.debug:
                            print(f"Waiting {sleep_time:.1f} seconds until next test...")
                        time.sleep(sleep_time)
        finally:
            # Stop sampler and collect samples — always runs even if loop raises
            sampler.stop(debug=self.debug)
            wifi_samples = sampler.get_samples()
            self.results['wifi_samples'] = wifi_samples

        # Update progress bar to show bandwidth test
        if not self.debug:
            pbar.set_description("Running bandwidth test")
            pbar.update(95 - pbar.n)

        # Run bandwidth test once at the end
        if self.debug:
            print("\nRunning bandwidth test...")
        bandwidth_result = self.test_bandwidth()
        self.results['bandwidth'] = bandwidth_result

        # Complete progress bar
        if not self.debug:
            pbar.update(100 - pbar.n)
            pbar.set_description("Test completed")
            pbar.close()

        self.results['end_time'] = datetime.now().isoformat()

        # Calculate statistics and derive WiFi stability score
        stats = StatisticsCalculator.calculate_statistics(self.results)
        wifi_stability = StatisticsCalculator.calculate_wifi_stability_score(
            wifi_samples,
            stats.get('latency_stats', {}),
            stats.get('jitter_stats', {}),
            stats.get('packet_loss_stats', {}),
        )
        wifi_stability['wifi_ssid'] = sampler.wifi_ssid
        self.results['wifi_stability'] = wifi_stability

        if self.debug:
            print("\nTest completed!")
        return self.results

class WiFiSampler:
    """Background WiFi signal sampler using system_profiler on macOS.

    Collects RSSI, noise floor, and SNR at a fixed interval in a daemon thread.
    On non-macOS platforms or non-WiFi connections, all methods are safe no-ops.
    """

    def __init__(self, interval_seconds: int = 5) -> None:
        self.interval_seconds = interval_seconds
        self._samples: List[WiFiSample] = []
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.wifi_ssid: Optional[str] = None

    def start(self) -> None:
        """Start background sampling thread. No-op on non-macOS or non-WiFi."""
        if platform.system() != "Darwin":
            return
        if not self._is_wifi_connected():
            return
        self.wifi_ssid = self._get_ssid()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def stop(self, debug: bool = False) -> None:
        """Signal thread to stop and join (2s timeout). Safe to call if not started."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2)
            if self._thread.is_alive() and debug:
                print("⚠️  WiFiSampler: thread did not stop within 2 seconds", file=sys.stderr)

    def get_samples(self) -> List[WiFiSample]:
        """Return collected samples. Call only after stop()."""
        return list(self._samples)

    def _is_wifi_connected(self) -> bool:
        """Return True if active interface has an IP address (indicating WiFi connectivity)."""
        try:
            result = subprocess.run(
                ["networksetup", "-getinfo", "Wi-Fi"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Look for a non-empty IP address line
            for line in result.stdout.splitlines():
                if line.startswith("IP address:"):
                    ip_part = line.split(":", 1)[1].strip()
                    if ip_part:
                        return True
            return False
        except Exception:
            return False

    def _get_wifi_device(self) -> Optional[str]:
        """Return the macOS network device name for the Wi-Fi hardware port (e.g. en0).

        Parses `networksetup -listallhardwareports` to find the device whose
        port name contains 'Wi-Fi' or 'AirPort'.
        """
        try:
            result = subprocess.run(
                ["networksetup", "-listallhardwareports"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.splitlines()
                for i, line in enumerate(lines):
                    if "Wi-Fi" in line or "AirPort" in line:
                        for j in range(i + 1, min(i + 4, len(lines))):
                            m = re.match(r'\s*Device:\s+(\S+)', lines[j])
                            if m:
                                return m.group(1)
        except Exception:
            pass
        return None

    # Sentinel returned when WiFi is connected but the SSID is hidden by macOS privacy.
    SSID_REDACTED = "<redacted>"

    @staticmethod
    def _clean_ssid(raw: str) -> Optional[str]:
        """Return the SSID string, SSID_REDACTED sentinel, or None.

        None  → value is empty / no network info found
        SSID_REDACTED → macOS privacy is hiding the name (Location Services off)
        str   → actual SSID
        """
        value = raw.strip()
        if not value:
            return None
        if value == "<redacted>":
            return WiFiSampler.SSID_REDACTED
        return value

    def _get_ssid(self) -> Optional[str]:
        """Return the connected WiFi network name (SSID), or None on failure.

        Uses scutil to read the AirPort dynamic-store entry, which embeds the
        last WiFi scan as an NSKeyedArchiver binary plist containing SSID_STR —
        no Location Services permission required (works on macOS 13+).

        Falls back to networksetup and airport for older macOS versions.
        """
        # Primary: scutil CachedScanRecord (NSKeyedArchiver binary plist).
        # Works on macOS 13+ without Location Services permission.
        try:
            import plistlib as _plistlib
            _sc = subprocess.run(
                ['scutil'],
                input=b'open\nget State:/Network/Interface/en0/AirPort\nd.show\nclose\n',
                capture_output=True, timeout=8,
            )
            _m = re.search(
                r'CachedScanRecord\s*:\s*<data>\s*(0x[0-9a-fA-F]+)',
                _sc.stdout.decode('utf-8', 'replace'),
            )
            if _m:
                _raw = bytes.fromhex(_m.group(1)[2:])
                _arch = _plistlib.loads(_raw)
                _objs = _arch.get('$objects', [])

                def _uid(ref):
                    if hasattr(ref, 'data'):
                        return _objs[ref.data]
                    if isinstance(ref, int):
                        return _objs[ref]
                    return ref

                for _obj in _objs:
                    if not isinstance(_obj, dict):
                        continue
                    _keys = [_uid(k) for k in _obj.get('NS.keys', [])]
                    _vals = [_uid(v) for v in _obj.get('NS.objects', [])]
                    try:
                        _idx = _keys.index('SSID_STR')
                        _candidate = _vals[_idx]
                        if isinstance(_candidate, str) and _candidate:
                            return _candidate
                    except (ValueError, IndexError):
                        pass
        except Exception:
            pass

        saw_redacted = False

        # Fallback 1: networksetup (works on older macOS; returns <redacted> on 13+)
        device = self._get_wifi_device()
        candidates = [device] if device else []
        for d in ("en0", "en1", "en2", "en3"):
            if d not in candidates:
                candidates.append(d)
        for iface in candidates:
            try:
                result = subprocess.run(
                    ["networksetup", "-getairportnetwork", iface],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0 and "Current Wi-Fi Network:" in result.stdout:
                    ssid = self._clean_ssid(
                        result.stdout.split("Current Wi-Fi Network:", 1)[1]
                    )
                    if ssid == self.SSID_REDACTED:
                        saw_redacted = True
                    elif ssid:
                        return ssid
            except Exception:
                pass

        # Fallback 2: airport utility (deprecated; absent on some macOS 15+ machines)
        airport = (
            "/System/Library/PrivateFrameworks/Apple80211.framework"
            "/Versions/Current/Resources/airport"
        )
        try:
            result = subprocess.run(
                [airport, "-I"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                m = re.search(r'\bSSID:\s+(.+)', result.stdout)
                if m:
                    ssid = self._clean_ssid(m.group(1))
                    if ssid == self.SSID_REDACTED:
                        saw_redacted = True
                    elif ssid:
                        return ssid
        except Exception:
            pass

        return self.SSID_REDACTED if saw_redacted else None

    def _parse_output(self, output: str) -> Optional[WiFiSample]:
        """Parse system_profiler text output. Return None on parse failure."""
        match = re.search(r'Signal / Noise: (-?\d+) dBm / (-?\d+) dBm', output)
        if not match:
            return None
        rssi_dbm = int(match.group(1))
        noise_dbm = int(match.group(2))
        snr_db = rssi_dbm - noise_dbm
        return WiFiSample(
            timestamp=time.time(),
            rssi_dbm=rssi_dbm,
            noise_dbm=noise_dbm,
            snr_db=snr_db,
        )

    def _sample_loop(self) -> None:
        """Thread target: loop until stop event set, calling system_profiler each interval."""
        while not self._stop_event.is_set():
            try:
                result = subprocess.run(
                    ["system_profiler", "SPAirPortDataType"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    # Opportunistically capture SSID from the first call if still unknown
                    if self.wifi_ssid is None:
                        m = re.search(
                            r'Current Network Information:\s*\n\s+(.+?):', result.stdout
                        )
                        if m:
                            candidate = self._clean_ssid(m.group(1))
                            if candidate:  # captures both real names and SSID_REDACTED
                                self.wifi_ssid = candidate
                    sample = self._parse_output(result.stdout)
                    if sample is not None:
                        self._samples.append(sample)
                    else:
                        print("⚠️  WiFiSampler: could not parse system_profiler output", file=sys.stderr)
                else:
                    print(f"⚠️  WiFiSampler: system_profiler exited with code {result.returncode}", file=sys.stderr)
            except Exception as exc:
                print(f"⚠️  WiFiSampler: error calling system_profiler: {exc}", file=sys.stderr)
            self._stop_event.wait(timeout=self.interval_seconds)


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

    @staticmethod
    def calculate_wifi_stability_score(
        samples: List[Any],
        latency_stats: Dict[str, Any],
        jitter_stats: Dict[str, Any],
        packet_loss_stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compute wifi_stability_score from WiFi hardware samples and behavior stats.

        Hardware path (len(samples) >= 1): penalises low/variable SNR plus
        latency CoV and jitter std_dev.  Returns WiFiStabilityResult-compatible dict.
        """
        if len(samples) >= 1:
            # --- hardware path ---
            score = 100
            snr_values = [s['snr_db'] for s in samples]
            avg_snr = statistics.mean(snr_values)

            # SNR level penalty (mutually exclusive tiers)
            if avg_snr < 10:
                score -= 40
            elif avg_snr < 20:
                score -= 20
            elif avg_snr < 30:
                score -= 10

            # SNR variance penalty (only when >= 2 samples)
            if len(samples) >= 2:
                snr_std = statistics.stdev(snr_values)
                if snr_std > 10:
                    score -= 20
                elif snr_std > 5:
                    score -= 10
                elif snr_std > 2:
                    score -= 5

            # Latency CoV penalty
            lat_mean = latency_stats.get('avg_ms', 0) or 0
            lat_std = latency_stats.get('std_dev_ms', 0) or 0
            lat_cov = (lat_std / lat_mean) if lat_mean != 0 else 0
            if lat_cov > 0.5:
                score -= 15
            elif lat_cov > 0.2:
                score -= 7

            # Jitter std_dev penalty
            jitter_std = jitter_stats.get('std_dev_ms', 0) or 0
            if jitter_std > 10:
                score -= 10
            elif jitter_std > 5:
                score -= 5

            score = max(0, min(100, score))

            return {
                'wifi_stability_score': score,
                'wifi_score_type': 'hardware',
                'wifi_samples': list(samples),
                'avg_snr_db': avg_snr,
            }

        # behavior-only path: no hardware samples but at least one stats dict is non-empty
        has_behavior_stats = any([
            bool(latency_stats),
            bool(jitter_stats),
            bool(packet_loss_stats),
        ])

        if not has_behavior_stats:
            # unavailable path: nothing to work with
            return {
                'wifi_stability_score': None,
                'wifi_score_type': 'unavailable',
                'wifi_samples': [],
                'avg_snr_db': None,
            }

        # behavior-only path: penalise based on packet loss, latency CoV, jitter std_dev
        score = 100

        # Packet loss penalty (mutually exclusive tiers)
        avg_loss = packet_loss_stats.get('avg_percent', 0) or 0
        if avg_loss > 1:
            score -= 30
        elif avg_loss > 0.1:
            score -= 15

        # Latency CoV penalty
        lat_mean = latency_stats.get('avg_ms', 0) or 0
        lat_std = latency_stats.get('std_dev_ms', 0) or 0
        lat_cov = (lat_std / lat_mean) if lat_mean != 0 else 0
        if lat_cov > 0.5:
            score -= 20
        elif lat_cov > 0.2:
            score -= 10

        # Jitter std_dev penalty
        jitter_std = jitter_stats.get('std_dev_ms', 0) or 0
        if jitter_std > 15:
            score -= 20
        elif jitter_std > 8:
            score -= 10

        score = max(0, min(100, score))

        return {
            'wifi_stability_score': score,
            'wifi_score_type': 'behavior-only',
            'wifi_samples': [],
            'avg_snr_db': None,
        }


class Reporter:
    """Handle output formatting and export functionality."""
    
    @staticmethod
    def print_summary(results: Dict[str, Any], stats: Dict[str, Any]):
        """Print a simplified summary of the test results."""
        # Show location if available
        if 'location' in results:
            loc_mgr = LocationManager()
            location_summary = loc_mgr.get_location_summary(results['location'])
            print(f"\\n📍 Location: {location_summary}")
        
        # Show local router info if available
        if results.get('local_router') and len(results['local_router']) > 0:
            router_data = results['local_router'][0]
            router_latency = router_data.get('avg_latency_ms')
            if router_latency is not None:
                print(f"🏠 Router: {router_data.get('gateway', 'Unknown')} ({router_latency:.1f}ms)")
            else:
                print(f"🏠 Router: {router_data.get('gateway', 'Unknown')} (N/A)")
        
        print(f"📊 Connection Quality Score: {stats['quality_score']}/100")
        
        # Show key metrics in a clean format
        metrics = []
        
        if stats['latency_stats']:
            avg_latency = stats['latency_stats']['avg_ms']
            if avg_latency is not None:
                metrics.append(f"🏓 Latency: {avg_latency:.1f}ms")
            else:
                metrics.append("🏓 Latency: N/A")
        
        if stats['packet_loss_stats']:
            avg_loss = stats['packet_loss_stats']['avg_percent']
            if avg_loss is not None and avg_loss > 0:
                metrics.append(f"📉 Packet Loss: {avg_loss:.1f}%")
        
        if stats['jitter_stats']:
            avg_jitter = stats['jitter_stats']['avg_ms']
            if avg_jitter is not None and avg_jitter > 1:  # Only show if significant
                metrics.append(f"📈 Jitter: {avg_jitter:.1f}ms")
        
        if stats['dns_stats']:
            avg_dns = stats['dns_stats']['avg_ms']
            if avg_dns is not None:
                metrics.append(f"🌐 DNS: {avg_dns:.1f}ms")
            else:
                metrics.append("🌐 DNS: N/A")
        
        if results['bandwidth'] and 'download_speed_mbps' in results['bandwidth']:
            speed = results['bandwidth']['download_speed_mbps']
            if speed is not None:
                metrics.append(f"⬇️  Speed: {speed:.1f}Mbps")
            else:
                metrics.append("⬇️  Speed: N/A")
        
        if metrics:
            print("   " + " | ".join(metrics))
        
        # Quality assessment
        score = stats['quality_score']
        if score >= 90:
            status = "🟢 Excellent"
        elif score >= 80:
            status = "🟡 Good"
        elif score >= 70:
            status = "🟠 Fair"
        else:
            status = "🔴 Poor"
        
        print(f"   Connection Status: {status}")

        # WiFi Stability Score display (task 5.1)
        wifi_stability = results.get('wifi_stability')
        wifi_ssid = (wifi_stability or {}).get('wifi_ssid')
        if wifi_ssid == WiFiSampler.SSID_REDACTED:
            print("   WiFi Network: hidden by macOS privacy")
        elif wifi_ssid:
            print(f"   WiFi Network: {wifi_ssid}")
        if wifi_stability is None:
            print("   WiFi Stability Score: N/A")
        else:
            wifi_score = wifi_stability.get('wifi_stability_score')
            wifi_type = wifi_stability.get('wifi_score_type', 'unavailable')
            if wifi_score is None or wifi_type == 'unavailable':
                print("   WiFi Stability Score: N/A")
            else:
                # Rating bands same as quality_score
                if wifi_score >= 90:
                    wifi_rating = "Excellent"
                elif wifi_score >= 80:
                    wifi_rating = "Good"
                elif wifi_score >= 70:
                    wifi_rating = "Fair"
                else:
                    wifi_rating = "Poor"

                if wifi_type == 'hardware':
                    avg_snr = wifi_stability.get('avg_snr_db')
                    if avg_snr is None:
                        print(f"   WiFi Stability Score: {wifi_score}/100 ({wifi_rating})")
                    else:
                        print(f"   WiFi Stability Score: {wifi_score}/100 ({wifi_rating}) | Avg SNR: {avg_snr:.1f} dB")
                else:
                    print(f"   Connection Stability Score (behavior only): {wifi_score}/100 ({wifi_rating})")

        print()

    @staticmethod
    def export_json(results: Dict[str, Any], stats: Dict[str, Any], filename: str):
        """Export results to JSON file."""
        wifi = results.get('wifi_stability', {})
        location = results.get('location', {})
        export_data = {
            'test_results': results,
            'statistics': stats,
            'export_time': datetime.now().isoformat(),
            'wifi_stability_score': wifi.get('wifi_stability_score', None),
            'wifi_score_type': wifi.get('wifi_score_type', None),
            'wifi_samples': wifi.get('wifi_samples', []),
            'avg_snr_db': wifi.get('avg_snr_db', None),
            'wifi_ssid': wifi.get('wifi_ssid', None),
            'location_latitude': location.get('latitude', None),
            'location_longitude': location.get('longitude', None),
            'location_city': location.get('city', None),
            'location_country': location.get('country', None),
            'location_name': location.get('name', None),
        }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"Results exported to {filename}")
    
    @staticmethod
    def export_csv(results: Dict[str, Any], filename: str):
        """Export latency results to CSV file."""
        wifi = results.get('wifi_stability', {})
        wifi_score = wifi.get('wifi_stability_score', None)
        wifi_samples = wifi.get('wifi_samples', [])

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'endpoint', 'latency_ms', 'packet_loss_percent', 'jitter_ms', 'wifi_stability_score'])
            
            for result in results['latency']:
                writer.writerow([
                    result.get('timestamp', ''),
                    result.get('endpoint', ''),
                    result.get('avg_latency_ms', ''),
                    result.get('packet_loss_percent', ''),
                    result.get('jitter_ms', ''),
                    wifi_score if wifi_score is not None else '',
                ])

            # WiFi samples section
            writer.writerow(['wifi_timestamp', 'rssi_dbm', 'noise_dbm', 'snr_db'])
            for sample in wifi_samples:
                writer.writerow([
                    sample.get('timestamp', ''),
                    sample.get('rssi_dbm', ''),
                    sample.get('noise_dbm', ''),
                    sample.get('snr_db', ''),
                ])
        
        print(f"Latency data exported to {filename}")


@click.command()
@click.option('--duration', '-d', default=60, help='Test duration in seconds (default: 60)')
@click.option('--endpoints', '-e', multiple=True, help='Additional test endpoints')
@click.option('--json', 'export_json', help='Export results to JSON file (default: results/netprobe_TIMESTAMP.json)')
@click.option('--csv', 'export_csv', help='Export latency data to CSV file (default: results/netprobe_TIMESTAMP.csv)')
@click.option('--compare-vpn', is_flag=True, help='Test with and without VPN (toggles VPN state)')
@click.option('--icmp', is_flag=True, help='Force ICMP ping (requires sudo/elevated permissions)')
@click.option('--debug', is_flag=True, help='Enable debug mode with verbose output')
@click.option('--location', help='Specify test location (e.g., "Starbucks Times Square" or "Hilton Hotel NYC")')
@click.option('--detect-location', is_flag=True, help='Auto-detect current location')
@click.option('--no-interactive', is_flag=True, help='Skip interactive VPN prompts (for automation)')
@click.option('--check-isolation', is_flag=True, help='Check network isolation before testing')
@click.option('--user', default=None, help='User identity for run records (or set NETPROBE_USER env var)')
@click.option('--publish', is_flag=True, help='Publish run records to Notion database')
@click.option('--log-file', default='netprobe-results.jsonl', help='Local JSONL log file path (default: netprobe-results.jsonl)')
def main(duration, endpoints, export_json, export_csv, compare_vpn, icmp, debug, location, detect_location, no_interactive, check_isolation, user, publish, log_file):
    """
    NetProbe - Internet Connection Reliability Tool
    
    Test internet connection quality with comprehensive metrics including
    latency, packet loss, jitter, DNS resolution, and bandwidth.
    """
    print("NetProbe - Internet Connection Reliability Tool")
    print("=" * 50)
    
    # Check network isolation if requested
    if check_isolation:
        try:
            from network_isolation_detector import NetworkIsolationDetector
            detector = NetworkIsolationDetector()
            isolation_report = detector.generate_isolation_report()
            detector.print_isolation_report(isolation_report)
            
            # Warn if isolation score is low
            if isolation_report.get('isolation_score', 100) < 70:
                print("\\n⚠️  Network isolation score is below 70. Consider:")
                print("   • Closing high-bandwidth applications")
                print("   • Testing during off-peak hours")
                print("   • Using ethernet instead of WiFi if possible")
                
                if not no_interactive:
                    response = input("\\nContinue with testing anyway? [y/N]: ").lower()
                    if response != 'y':
                        print("Test cancelled.")
                        return
        except ImportError:
            print("⚠️  Network isolation detector not available (missing psutil)")
        except Exception as e:
            print(f"⚠️  Network isolation check failed: {e}")
    
    
    # Initialize VPN manager and location manager
    vpn_manager = VPNManager()
    vpn_manager.debug = debug  # Pass debug mode to VPN manager
    location_manager = LocationManager()
    
    # Handle location detection/specification
    # NOTE: Location should be detected without VPN to get actual physical location
    location_data = None
    original_vpn_connected = False
    
    if location:
        # User specified a location name
        location_data = location_manager.search_nearby_places(location)
        if debug:
            print(f"Location search result: {location_data}")
    elif detect_location:
        # For location detection, temporarily disconnect VPN if it's connected
        current_vpn_status = vpn_manager.get_status()
        original_vpn_connected = current_vpn_status.get('connected', False)
        
        if original_vpn_connected and compare_vpn:
            if debug:
                print("Temporarily checking VPN status for location detection...")
            # Note: We can't auto-disconnect GUI VPN, but we can warn the user
            if vpn_manager.vpn_type == 'nordvpn-macos':
                if debug:
                    print("Note: For accurate location detection, consider manually disconnecting VPN first")
        
        # Auto-detect current location (may show VPN location if connected)
        location_data = location_manager.get_location()
        if debug:
            if original_vpn_connected:
                print(f"Location detected (may be VPN server location): {location_data}")
            else:
                print(f"Auto-detected physical location: {location_data}")
    
    # Ensure results directory exists
    os.makedirs('results', exist_ok=True)
    
    # Set default export filenames if not provided
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not export_json and not export_csv:
        # If no export options specified, don't export by default
        pass
    else:
        if export_json and export_json == True:  # Boolean True from flag
            export_json = f"results/netprobe_{timestamp}.json"
        elif export_json and not export_json.startswith('/') and not export_json.startswith('./'):
            # Relative path, put in results directory
            export_json = f"results/{export_json}"
            
        if export_csv and export_csv == True:  # Boolean True from flag
            export_csv = f"results/netprobe_{timestamp}.csv"
        elif export_csv and not export_csv.startswith('/') and not export_csv.startswith('./'):
            # Relative path, put in results directory
            export_csv = f"results/{export_csv}"
    
    # Initialize tester
    test_endpoints = list(endpoints) if endpoints else None
    tester = ConnectionTester(endpoints=test_endpoints, duration=duration)
    tester.force_icmp = icmp  # Pass ICMP preference to tester
    tester.debug = debug  # Pass debug mode to tester
    exit_code = 0
    
    try:
        # Check VPN status and capabilities
        if compare_vpn:
            vpn_status = vpn_manager.get_status()
            if vpn_manager.vpn_type:
                print(f"Detected VPN client: {vpn_manager.vpn_type}")
                print(f"Current VPN status: {'Connected' if vpn_status.get('connected') else 'Disconnected'}")
                if vpn_status.get('server'):
                    print(f"Connected to server: {vpn_status['server']}")
                
                # Special handling for GUI-based VPN clients
                if vpn_manager.vpn_type == 'nordvpn-macos' and compare_vpn:
                    print("📝 NordVPN GUI detected. Interactive VPN comparison enabled:")
                    print("   • Tool will prompt when VPN changes are needed")
                    print("   • Simply connect/disconnect manually when prompted")
                    print("   • VPN status detection works automatically")
                print()
            else:
                print("No supported VPN client found. Supported: NordVPN, ProtonVPN, ExpressVPN")
                if compare_vpn:
                    print("Cannot perform VPN testing without a supported VPN client.")
                    return
        
        # Save original VPN state (only when VPN comparison is requested)
        if compare_vpn:
            vpn_manager.save_state()
        
        all_results = []
        all_stats = []

        # Resolve data-capture configuration once before the scenario loop
        resolved_user = resolve_user(user)
        notion_config = NotionConfig.from_env() if publish else None

        # Determine test scenarios
        test_scenarios = []
        if compare_vpn:
            test_scenarios = [('without_vpn', False), ('with_vpn', True)]
        else:
            test_scenarios = [('default', None)]  # Don't change VPN state
        
        for scenario_name, vpn_should_be_connected in test_scenarios:
            if debug:
                print(f"\\n{'='*60}")
                print(f"RUNNING TEST: {scenario_name.replace('_', ' ').upper()}")
                print(f"{'='*60}")
            elif len(test_scenarios) > 1:
                scenario_display = scenario_name.replace('_', ' ').title()
                print(f"\\n🔍 Testing {scenario_display}")
            
            # Configure VPN state if needed
            if vpn_should_be_connected is not None:
                current_status = vpn_manager.get_status()
                current_connected = current_status.get('connected', False)
                
                if vpn_should_be_connected and not current_connected:
                    if debug:
                        print("Connecting to VPN...")
                    
                    if vpn_manager.vpn_type == 'nordvpn-macos':
                        # Interactive prompt for GUI VPN
                        print(f"\n🔌 Please CONNECT your VPN manually now")
                        print("   1. Open NordVPN app")
                        print("   2. Click connect to any server")
                        print("   3. Wait for connection to establish")
                        
                        # Wait for user to connect
                        if no_interactive:
                            print("❌ Interactive mode disabled. Skipping this test scenario.")
                            continue
                        
                        try:
                            input("Press Enter when VPN is connected and ready...")
                        except (EOFError, KeyboardInterrupt):
                            print("\\n❌ Interactive input not available. Skipping this test scenario.")
                            continue
                        
                        # Verify connection
                        new_status = vpn_manager.get_status()
                        if not new_status.get('connected'):
                            print("❌ VPN still appears disconnected. Skipping this test scenario.")
                            continue
                        else:
                            print(f"✅ VPN connection detected! Server: {new_status.get('server', 'Unknown')}")
                    else:
                        # Try automatic connection for CLI VPNs
                        if not vpn_manager.connect():
                            print("⚠️  Failed to connect to VPN. Skipping this test scenario.")
                            continue
                    
                    time.sleep(2)  # Brief pause for connection to stabilize
                    
                elif not vpn_should_be_connected and current_connected:
                    if debug:
                        print("Disconnecting from VPN...")
                    
                    if vpn_manager.vpn_type == 'nordvpn-macos':
                        # Interactive prompt for GUI VPN  
                        print(f"\n🔌 Please DISCONNECT your VPN manually now")
                        print("   1. Open NordVPN app")
                        print("   2. Click disconnect")
                        print("   3. Wait for disconnection to complete")
                        
                        # Wait for user to disconnect
                        if no_interactive:
                            print("❌ Interactive mode disabled. Skipping this test scenario.")
                            continue
                        
                        try:
                            input("Press Enter when VPN is disconnected and ready...")
                        except (EOFError, KeyboardInterrupt):
                            print("\\n❌ Interactive input not available. Skipping this test scenario.")
                            continue
                        
                        # Verify disconnection
                        new_status = vpn_manager.get_status()
                        if new_status.get('connected'):
                            print("❌ VPN still appears connected. Skipping this test scenario.")
                            continue
                        else:
                            print("✅ VPN disconnection detected!")
                    else:
                        # Try automatic disconnection for CLI VPNs
                        if not vpn_manager.disconnect():
                            print("⚠️  Failed to disconnect from VPN. Skipping this test scenario.")
                            continue
                    
                    time.sleep(2)  # Brief pause for disconnection to stabilize
            
            # Run the test
            results = tester.run_extended_test()
            results['test_scenario'] = scenario_name
            results['vpn_status'] = vpn_manager.get_status()
            
            if debug:
                print(f"DEBUG: Stored scenario_name='{scenario_name}', vpn_connected={results['vpn_status'].get('connected')}")
            
            # Validate VPN state matches expected scenario
            vpn_connected = results['vpn_status'].get('connected', False)
            if scenario_name == 'without_vpn' and vpn_connected:
                print("⚠️  WARNING: VPN is still connected during 'without VPN' test. Results may not be accurate.")
            elif scenario_name == 'with_vpn' and not vpn_connected:
                print("⚠️  WARNING: VPN is disconnected during 'with VPN' test. Results may not be accurate.")
            
            # Add location information to results
            if location_data:
                results['location'] = location_data
            
            # Calculate statistics
            stats = StatisticsCalculator.calculate_statistics(results)

            # Persist and optionally publish the run record
            record_run(results, stats, user=resolved_user, log_path=log_file, publish=publish, notion_config=notion_config)

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
                scenario_key = results['test_scenario']
                vpn_status = results['vpn_status']
                
                if debug:
                    print(f"DEBUG: Processing result {i}: scenario_key='{scenario_key}', connected={vpn_status.get('connected')}")
                
                # Format scenario name correctly and check for mismatches
                vpn_connected = vpn_status.get('connected', False)
                if scenario_key == 'without_vpn':
                    scenario = "Without Vpn"
                    if vpn_connected:
                        scenario += " ⚠️ (VPN was still connected)"
                elif scenario_key == 'with_vpn':
                    scenario = "With Vpn"  
                    if not vpn_connected:
                        scenario += " ⚠️ (VPN was disconnected)"
                else:
                    scenario = scenario_key.replace('_', ' ').title()
                
                vpn_info = f" ({vpn_status.get('server', 'Unknown server')})" if vpn_connected else ""
                
                print(f"\\n{scenario}{vpn_info}:")
                print(f"  Quality Score: {stats['quality_score']}/100")
                
                # Build emoji summary line like the individual test results
                summary_parts = []
                if stats.get('latency_stats'):
                    latency = stats['latency_stats']['avg_ms']
                    if latency is not None:
                        summary_parts.append(f"🏓 Latency: {latency:.1f}ms")
                    else:
                        summary_parts.append("🏓 Latency: N/A")
                
                if stats.get('packet_loss_stats'):
                    loss = stats['packet_loss_stats']['avg_percent']
                    if loss is not None and loss > 0:
                        summary_parts.append(f"📉 Packet Loss: {loss:.1f}%")
                
                if stats.get('jitter_stats'):
                    jitter = stats['jitter_stats']['avg_ms']
                    if jitter is not None:
                        summary_parts.append(f"📈 Jitter: {jitter:.1f}ms")
                    else:
                        summary_parts.append("📈 Jitter: N/A")
                
                if stats.get('dns_stats'):
                    dns = stats['dns_stats']['avg_ms']
                    if dns is not None:
                        summary_parts.append(f"🌐 DNS: {dns:.1f}ms")
                    else:
                        summary_parts.append("🌐 DNS: N/A")
                
                if results['bandwidth'] and 'download_speed_mbps' in results['bandwidth']:
                    speed = results['bandwidth']['download_speed_mbps']
                    if speed is not None:
                        summary_parts.append(f"⬇️ Speed: {speed:.1f}Mbps")
                    else:
                        summary_parts.append("⬇️ Speed: N/A")
                
                if summary_parts:
                    summary_line = "   " + " | ".join(summary_parts)
                    print(summary_line)
            
            # Calculate differences
            if len(all_stats) == 2:
                no_vpn_stats = all_stats[0] if all_results[0]['test_scenario'] == 'without_vpn' else all_stats[1]
                vpn_stats = all_stats[1] if all_results[1]['test_scenario'] == 'with_vpn' else all_stats[0]
                
                print(f"\\nDifferences (VPN impact):")
                
                if no_vpn_stats.get('latency_stats') and vpn_stats.get('latency_stats'):
                    vpn_latency = vpn_stats['latency_stats']['avg_ms']
                    no_vpn_latency = no_vpn_stats['latency_stats']['avg_ms']
                    if vpn_latency is not None and no_vpn_latency is not None:
                        latency_diff = vpn_latency - no_vpn_latency
                        print(f"  Latency change: {latency_diff:+.2f} ms")
                
                if no_vpn_stats.get('packet_loss_stats') and vpn_stats.get('packet_loss_stats'):
                    vpn_loss = vpn_stats['packet_loss_stats']['avg_percent']
                    no_vpn_loss = no_vpn_stats['packet_loss_stats']['avg_percent']
                    if vpn_loss is not None and no_vpn_loss is not None:
                        loss_diff = vpn_loss - no_vpn_loss
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
                print(f"\nWarning: Connection quality is below acceptable threshold (worst score: {min_quality_score})!")
                exit_code = 1
            else:
                print(f"\nConnection quality is good (best score: {max(stats['quality_score'] for stats in all_stats)}).")
                exit_code = 0
        else:
            exit_code = 1

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        exit_code = 1
    except Exception as e:
        print(f"\nError during testing: {str(e)}")
        exit_code = 1
    finally:
        # Restore original VPN state only when VPN comparison was requested
        try:
            if compare_vpn and vpn_manager and hasattr(vpn_manager, 'original_state') and vpn_manager.original_state:
                print("\nRestoring original VPN state...")
                vpn_manager.restore_state()
        except Exception as e:
            print(f"Warning: Failed to restore VPN state: {str(e)}")
        
        exit(exit_code)


if __name__ == '__main__':
    main()