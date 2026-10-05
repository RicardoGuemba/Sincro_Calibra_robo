#!/usr/bin/env bash
# Restringe as respostas ARP à placa dona de cada IP. Sem isso, com várias placas no mesmo
# segmento (cabo + Wi-Fi), a câmera GigE envia o stream para o MAC da placa errada.
set -euo pipefail

CONF="/etc/sysctl.d/99-sincro-robo-gige.conf"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Execute como root: sudo $0" >&2
  exit 2
fi

cat > "$CONF" <<'EOF'
# SINCRO_ROBO: câmera GigE Vision com várias placas de rede no mesmo segmento.
net.ipv4.conf.all.arp_ignore = 1
net.ipv4.conf.all.arp_announce = 2
EOF

sysctl -q --load="$CONF"
ip -s -s neigh flush all >/dev/null 2>&1 || true

echo "Aplicado: $CONF"
sysctl net.ipv4.conf.all.arp_ignore net.ipv4.conf.all.arp_announce
echo "Reinicie o SINCRO_ROBO (ou aguarde a reconexão automática da câmera)."
