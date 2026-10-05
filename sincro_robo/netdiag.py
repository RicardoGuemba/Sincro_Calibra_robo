from __future__ import annotations

from pathlib import Path

SYSCTL_FILE = "/etc/sysctl.d/99-sincro-robo-gige.conf"
FIX_COMMAND = "sudo scripts/fix_gige_network.sh"

_SYS_NET = Path("/sys/class/net")
_PROC_CONF = Path("/proc/sys/net/ipv4/conf")
_IGNORED_PREFIXES = ("lo", "docker", "veth", "br-", "virbr", "tailscale", "tun", "wg")


def _read_int(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def _effective(name: str, interface: str) -> int | None:
    # The kernel applies max(conf/all, conf/<iface>) for arp_ignore/arp_announce.
    values = [_read_int(_PROC_CONF / scope / name) for scope in ("all", interface)]
    known = [value for value in values if value is not None]
    return max(known) if known else None


def active_interfaces() -> list[str]:
    names: list[str] = []
    try:
        entries = sorted(_SYS_NET.iterdir())
    except OSError:
        return names
    for entry in entries:
        if entry.name.startswith(_IGNORED_PREFIXES):
            continue
        if _read_int(entry / "carrier") == 1:
            names.append(entry.name)
    return names


def rx_bytes() -> dict[str, int]:
    counters: dict[str, int] = {}
    for name in active_interfaces():
        value = _read_int(_SYS_NET / name / "statistics" / "rx_bytes")
        if value is not None:
            counters[name] = value
    return counters


def arp_flux_issue(interface: str) -> str | None:
    """Return a message when other NICs may answer ARP for the camera NIC's address."""
    if not interface:
        return None
    others = [name for name in active_interfaces() if name != interface]
    if not others:
        return None
    arp_ignore = _effective("arp_ignore", interface)
    arp_announce = _effective("arp_announce", interface)
    if arp_ignore is None or (arp_ignore >= 1 and (arp_announce or 0) >= 2):
        return None
    return (
        f"ARP não restrito por interface (arp_ignore={arp_ignore}, arp_announce={arp_announce}) "
        f"com outras placas ativas ({', '.join(others)}): a câmera pode enviar o stream pela placa errada. "
        f"Corrija com: {FIX_COMMAND}"
    )


def stream_ingress_issue(interface: str, before: dict[str, int], after: dict[str, int]) -> str | None:
    """Detect GigE stream traffic landing on a NIC other than the camera NIC."""
    if not interface or not before or not after:
        return None
    deltas = {name: after[name] - before[name] for name in after if name in before}
    camera_delta = deltas.pop(interface, 0)
    if not deltas:
        return None
    culprit, culprit_delta = max(deltas.items(), key=lambda item: item[1])
    if culprit_delta < 1_000_000 or culprit_delta < 4 * max(camera_delta, 1):
        return None
    return (
        f"Stream da câmera chegando por {culprit} ({culprit_delta / 1e6:.1f} MB) em vez de {interface} "
        f"({camera_delta / 1e6:.2f} MB). Corrija com: {FIX_COMMAND} e religue a câmera"
    )
