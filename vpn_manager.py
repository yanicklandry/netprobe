#!/usr/bin/env pipenv run python
"""
VPN Manager for NetProbe
Handles VPN detection, connection management, and status monitoring.
"""

import subprocess
import sys
import time
from typing import Dict, Any, Optional


class VPNManager:
    """Manage VPN connections for testing."""
    
    def __init__(self):
        self.vpn_type = self._detect_vpn()
        self.original_state = None
        self.debug = False
    
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
                # Use the reliable bash script method: check for utun in IPv4 routing table
                try:
                    # Primary check: Look for utun in IPv4 default routes (most reliable)
                    route_check = subprocess.run(['netstat', '-rn', '-f', 'inet'], capture_output=True, text=True, timeout=10)
                    
                    if route_check.returncode == 0:
                        routes_output = route_check.stdout
                        
                        # Check for utun interfaces in routing table
                        vpn_connected = 'utun' in routes_output
                        
                        # Secondary check for older VPN types if utun not found
                        if not vpn_connected:
                            vpn_connected = any(vpn_type in routes_output for vpn_type in ['pptp', 'l2tp'])
                        
                        # Get external IP for server info if connected
                        external_ip = None
                        if vpn_connected:
                            try:
                                ip_check = subprocess.run(['curl', '-s', '--connect-timeout', '3', '--max-time', '5', 'ifconfig.me'], 
                                                        capture_output=True, text=True, timeout=8)
                                if ip_check.returncode == 0 and ip_check.stdout.strip():
                                    external_ip = ip_check.stdout.strip()
                            except:
                                pass
                        
                        if self.debug:
                            print(f"Debug VPN Detection:")
                            print(f"  - Routing table check: {'utun found' if 'utun' in routes_output else 'utun not found'}")
                            print(f"  - VPN connected: {vpn_connected}")
                            print(f"  - External IP: {external_ip}")
                        
                        return {
                            'connected': vpn_connected,
                            'server': external_ip if vpn_connected else None,
                            'client': 'nordvpn-macos',
                            'method': 'netstat_routing_table',
                            'debug_info': {
                                'routing_table_has_utun': 'utun' in routes_output,
                                'external_ip': external_ip
                            } if self.debug else None
                        }
                    
                except Exception as e:
                    if self.debug:
                        print(f"VPN detection error: {e}")
                    
                # Final fallback: assume disconnected
                return {'connected': False, 'server': None, 'client': 'nordvpn-macos', 'error': 'Detection failed'}
            
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
                # Try to connect via GUI automation (less reliable but works)
                try:
                    # First, open NordVPN app
                    subprocess.run(['open', '-a', 'NordVPN'], capture_output=True, timeout=5)
                    time.sleep(2)  # Wait for app to open
                    
                    # Check if already connected
                    current_status = self.get_status()
                    if current_status.get('connected'):
                        return True
                    
                    # For now, return False as GUI automation is complex
                    # User can manually connect through the GUI
                    return False
                except Exception:
                    return False
            
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
            
            elif self.vpn_type == 'nordvpn-macos':
                # For macOS GUI app, user needs to manually disconnect
                # We can't reliably automate the GUI
                try:
                    subprocess.run(['open', '-a', 'NordVPN'], capture_output=True, timeout=5)
                    # Return False to indicate manual action needed
                    return False
                except Exception:
                    return False
            
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