from __future__ import annotations

import ipaddress
import json
from pathlib import Path
import sys


def parse_wireguard_config(text: str) -> dict[str, object]:
    """Parse Interface and Peer blocks from a WireGuard configuration file."""
    interface: dict[str, str] = {}
    peers: list[dict[str, str]] = []
    current_section: str | None = None
    current_peer: dict[str, str] | None = None

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            if section == "interface":
                current_section = "interface"
            elif section == "peer":
                current_section = "peer"
                current_peer = {}
                peers.append(current_peer)
            else:
                raise ValueError(f"Unsupported section: [{section}]")
            continue

        if "=" not in line or current_section is None:
            raise ValueError(f"Malformed WireGuard config line: {raw_line}")
        key, value = (part.strip() for part in line.split("=", 1))
        if current_section == "interface":
            interface[key] = value
        elif current_peer is not None:
            current_peer[key] = value

    return {"interface": interface, "peers": peers}


def audit_mesh_config(text: str) -> list[str]:
    """Return a list of security/routing violations for an internal mesh WireGuard config."""
    parsed = parse_wireguard_config(text)
    interface = parsed["interface"]
    peers = parsed["peers"]
    issues: list[str] = []

    if not isinstance(interface, dict) or "Address" not in interface:
        issues.append("Missing Interface Address")
    else:
        try:
            net = ipaddress.ip_interface(interface["Address"])
            if not net.ip.is_private:
                issues.append(f"Mesh interface Address must be private/overlay CIDR: {interface['Address']}")
        except ValueError:
            issues.append(f"Invalid Interface Address CIDR: {interface['Address']}")

    if not isinstance(peers, list) or not peers:
        issues.append("At least one [Peer] is required")
        return issues

    for idx, peer in enumerate(peers, 1):
        allowed = peer.get("AllowedIPs", "")
        if not allowed:
            issues.append(f"Peer #{idx} missing AllowedIPs")
            continue
        for cidr_raw in allowed.split(","):
            cidr = cidr_raw.strip()
            try:
                net = ipaddress.ip_network(cidr, strict=False)
            except ValueError:
                issues.append(f"Peer #{idx} invalid CIDR: {cidr}")
                continue
            if net.prefixlen == 0 or not net.is_private:
                issues.append(f"Peer #{idx} exposes non-mesh or default route in AllowedIPs: {cidr}")
        if "PersistentKeepalive" not in peer:
            issues.append(f"Peer #{idx} missing PersistentKeepalive")

    return issues


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python scripts/wg_audit.py <config_path>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    issues = audit_mesh_config(path.read_text(encoding="utf-8"))
    print(json.dumps({"file": str(path), "ok": not issues, "issues": issues}, ensure_ascii=False))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
