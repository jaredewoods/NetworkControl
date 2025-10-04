import socket
import psutil
import subprocess
import re
import wmi


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
            capture_output=True, text=True, encoding="utf-8", errors="ignore"
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


def _get_adapter_descriptions():
    """
    Return {adapter_name: friendly_description} using WMI.
    Example: {'Ethernet': 'Intel(R) Ethernet Controller I225-V'}
    """
    descriptions = {}
    try:
        c = wmi.WMI()
        for nic in c.Win32_NetworkAdapter():
            if nic.NetConnectionID:  # skip disconnected / virtual
                descriptions[nic.NetConnectionID] = nic.Name
    except Exception:
        pass
    return descriptions


def get_network_interfaces():
    """Return list of real NICs with IP, subnet, gateway, DHCP mode, and description."""
    interfaces = psutil.net_if_addrs()
    dhcp_modes, gateway_map = _parse_dhcp_and_gateway()
    desc_map = _get_adapter_descriptions()

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
        description = desc_map.get(name, name)  # fallback to adapter name

        data.append({
            "connection": name,
            "description": description,
            "ip": ipv4,
            "subnet": subnet,
            "gateway": gateway,
            "mode": dhcp_mode
        })

    return data
