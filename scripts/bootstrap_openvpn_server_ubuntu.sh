#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Execute com sudo."
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  openvpn \
  easy-rsa \
  ufw

mkdir -p /etc/openvpn/server/spygym
mkdir -p /etc/openvpn/server/spygym/ccd
mkdir -p /etc/openvpn/server/spygym/pki
mkdir -p /var/log/openvpn

if ! grep -q '^net.ipv4.ip_forward=1' /etc/sysctl.conf; then
  echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf
fi
sysctl -p

ufw allow 1194/udp
ufw allow OpenSSH
ufw reload || true

echo
echo "Bootstrap inicial do OpenVPN concluido."
echo "Agora siga esta ordem:"
echo "1. Copie deploy/openvpn-server.conf.example para /etc/openvpn/server/spygym.conf"
echo "2. Rode scripts/create_openvpn_pki_ubuntu.sh para gerar CA, server cert e tls-crypt"
echo "3. Rode scripts/generate_openvpn_routing_artifacts.py para criar rotas e arquivos CCD"
echo "4. Copie os CCDs gerados para /etc/openvpn/server/spygym/ccd/"
echo "5. Inicie o servico: systemctl enable --now openvpn-server@spygym"
