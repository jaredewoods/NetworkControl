"""
network_apply.py
----------------
Handles applying network adapter configuration changes via PowerShell.

All commands are executed in a subprocess and require Administrator privileges.
"""

import subprocess


def apply_nic_settings(adapter_name: str, ip: str, subnet: str, gateway: str, mode: str) -> dict:
    """
    Apply configuration changes to a network adapter.

    Args:
        adapter_name (str): The Windows interface alias (e.g., "Ethernet", "Wi-Fi")
        ip (str): IPv4 address to assign
        subnet (str): Prefix length (e.g., 24)
        gateway (str): Default gateway address
        mode (str): Either "DHCP" or "Static"

    Returns:
        dict: {
            "success": bool,
            "command": str,
            "stdout": str,
            "stderr": str
        }
    """
    mode = mode.strip().upper()
    if not adapter_name:
        return {"success": False, "command": None, "stdout": "", "stderr": "Missing adapter name"}

    if mode == "DHCP":
        # Enable DHCP on adapter
        cmd = f'Set-NetIPInterface -InterfaceAlias "{adapter_name}" -Dhcp Enabled'
    else:
        # Configure static IP settings
        cmd = (
            f'New-NetIPAddress -InterfaceAlias "{adapter_name}" '
            f'-IPAddress {ip} -PrefixLength {subnet} -DefaultGateway {gateway} '
            f'-ErrorAction SilentlyContinue'
        )

    try:
        result = subprocess.run(
            ["powershell", "-Command", cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15
        )
        success = result.returncode == 0
        return {
            "success": success,
            "command": cmd,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }

    except Exception as e:
        return {"success": False, "command": cmd, "stdout": "", "stderr": str(e)}


def validate_ip_structure(ip: str) -> bool:
    """Basic IPv4 structure validation."""
    try:
        parts = ip.split(".")
        return len(parts) == 4 and all(0 <= int(p) <= 255 for p in parts)
    except Exception:
        return False
