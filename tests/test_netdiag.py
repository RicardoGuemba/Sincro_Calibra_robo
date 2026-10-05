from sincro_robo import netdiag


def test_stream_ingress_flags_traffic_on_wrong_nic():
    before = {"enp3s0": 0, "wlan0": 0, "enp2s0": 0}
    after = {"enp3s0": 17_000, "wlan0": 8_000_000, "enp2s0": 300_000}
    message = netdiag.stream_ingress_issue("enp3s0", before, after)
    assert message is not None
    assert "wlan0" in message and netdiag.FIX_COMMAND in message


def test_stream_ingress_ignores_healthy_camera_nic():
    before = {"enp3s0": 0, "wlan0": 0}
    after = {"enp3s0": 40_000_000, "wlan0": 2_000_000}
    assert netdiag.stream_ingress_issue("enp3s0", before, after) is None


def test_arp_flux_detected_with_default_sysctl(monkeypatch):
    monkeypatch.setattr(netdiag, "active_interfaces", lambda: ["enp2s0", "enp3s0", "wlan0"])
    monkeypatch.setattr(netdiag, "_effective", lambda name, _iface: 0)
    assert "arp_ignore=0" in netdiag.arp_flux_issue("enp3s0")


def test_arp_flux_cleared_after_fix(monkeypatch):
    monkeypatch.setattr(netdiag, "active_interfaces", lambda: ["enp2s0", "enp3s0"])
    monkeypatch.setattr(netdiag, "_effective", lambda name, _iface: {"arp_ignore": 1, "arp_announce": 2}[name])
    assert netdiag.arp_flux_issue("enp3s0") is None


def test_arp_flux_irrelevant_with_single_nic(monkeypatch):
    monkeypatch.setattr(netdiag, "active_interfaces", lambda: ["enp3s0"])
    monkeypatch.setattr(netdiag, "_effective", lambda name, _iface: 0)
    assert netdiag.arp_flux_issue("enp3s0") is None
