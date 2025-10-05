import socket
import psutil
import subprocess
import re
import json
import wmi


# ------------------------------------------------------------
# Helper: Parse DHCP + Gateway info via netsh
# ------------------------------------------------------------
def _parse_dhcp_and_gateway():
    """
    Return dicts for {adapter_name: dhcp_mode} and {adapter_name: gateway_ip}
    using 'netsh interface ip show config'.
    """
    dhcp_modes = {}
    gateways = {}

    try:
        result = subprocess.run(
            ["netsh", "interface", "ip", "show", "config"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        current_adapter = None
        for line in result.stdout.splitlines():
            header = re.match(r'Configuration for interface "(.*)"', line)
            if header:
                current_adapter = header.group(1).strip()
                continue

            if not current_adapter:
                continue

            dhcp_match = re.search(r"DHCP enabled:\s+(Yes|No)", line, re.IGNORECASE)
            if dhcp_match:
                dhcp_modes[current_adapter] = (
                    "DHCP" if dhcp_match.group(1).lower() == "yes" else "Static"
                )

            gw_match = re.search(r"Default Gateway:\s*(.*)", line)
            if gw_match:
                gw = gw_match.group(1).strip()
                if gw and gw != "None":
                    gateways[current_adapter] = gw

    except Exception:
        pass

    return dhcp_modes, gateways


# ------------------------------------------------------------
# Helper: Get adapter hardware descriptions via WMI
# ------------------------------------------------------------
def _get_adapter_descriptions():
    """
    Return {adapter_name: friendly_description} using WMI.
    Example: {'Ethernet': 'Intel(R) Ethernet Controller I225-V'}
    """
    descriptions = {}
    try:
        c = wmi.WMI()
        for nic in c.Win32_NetworkAdapter():
            if nic.NetConnectionID:
                descriptions[nic.NetConnectionID] = nic.Name
    except Exception:
        pass
    return descriptions


# ------------------------------------------------------------
# Normal / Fast Scan (psutil + WMI + netsh)
# ------------------------------------------------------------
def get_network_interfaces():
    """Return list of real network interfaces with IP, subnet, gateway, DHCP mode, and link status."""
    interfaces = psutil.net_if_addrs()
    dhcp_modes, gateway_map = _parse_dhcp_and_gateway()
    desc_map = _get_adapter_descriptions()
    stats = psutil.net_if_stats()

    data = []
    for name, addrs in interfaces.items():
        if name.lower().startswith(("loopback", "lo")):
            continue

        ipv4 = next((a.address for a in addrs if a.family == socket.AF_INET), "")
        subnet = next((a.netmask for a in addrs if a.family == socket.AF_INET), "")

        if not ipv4:
            continue

        dhcp_mode = dhcp_modes.get(name, "Unknown")
        gateway = gateway_map.get(name, "—")
        description = desc_map.get(name, name)

        if any(x in description.lower() for x in ["bluetooth", "virtual", "vmware", "hyper-v", "loopback"]):
            continue
        if any(x in name.lower() for x in ["bluetooth", "virtual", "vmware", "hyper-v", "loopback"]):
            continue

        link_status = "Up"
        try:
            if name in stats and not stats[name].isup:
                link_status = "Down"
        except Exception:
            pass

        data.append({
            "connection": name,
            "description": description,
            "ip": ipv4,
            "subnet": subnet,
            "gateway": gateway,
            "mode": dhcp_mode,
            "link": link_status
        })

    return data


# ------------------------------------------------------------
# Deep Scan (PowerShell JSON)
# ------------------------------------------------------------
def get_network_interfaces_deep():
    """
    Use PowerShell to gather verified adapter data with real gateways,
    DHCP/Static status, and hardware description.
    Bluetooth and virtual adapters are filtered out.
    """
    cmd = [
        "powershell",
        "-Command",
        (
            "Get-NetIPConfiguration | Select-Object "
            "InterfaceAlias, InterfaceDescription, "
            "@{n='IPAddress';e={$_.IPv4Address.IPAddress}}, "
            "@{n='PrefixLength';e={$_.IPv4Address.PrefixLength}}, "
            "@{n='Gateway';e={$_.IPv4DefaultGateway.NextHop}}, "
            "@{n='DHCP';e={"
            " if ($_.IPv4Address.PrefixOrigin -eq 'Dhcp') {'DHCP'} "
            " else {'Static'} } } "
            "| ConvertTo-Json -Depth 3"
        ),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=10
        )
        if not result.stdout.strip():
            raise RuntimeError("PowerShell returned no data")

        adapters = json.loads(result.stdout)

        # Normalize JSON output
        if isinstance(adapters, dict):
            adapters = [adapters]

        data = []
        for nic in adapters:
            desc = nic.get("InterfaceDescription", "") or ""
            name = nic.get("InterfaceAlias", "") or ""

            # Filter out Bluetooth, virtual, etc.
            if any(x in desc.lower() for x in ["bluetooth", "virtual", "vmware", "hyper-v", "loopback"]):
                continue
            if any(x in name.lower() for x in ["bluetooth", "virtual", "vmware", "hyper-v", "loopback"]):
                continue

            data.append({
                "connection": name or "—",
                "description": desc or "—",
                "ip": nic.get("IPAddress", "—"),
                "subnet": str(nic.get("PrefixLength", "—")),
                "gateway": nic.get("Gateway", "—"),
                "mode": nic.get("DHCP", "—"),
            })

        return data

    except Exception as e:
        return [{
            "connection": "Error",
            "description": str(e),
            "ip": "—",
            "subnet": "—",
            "gateway": "—",
            "mode": "—"
        }]
