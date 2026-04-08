#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Execute com sudo."
  exit 1
fi

OPENVPN_DIR="/etc/openvpn/server/spygym"
PKI_DIR="${OPENVPN_DIR}/pki"
EASYRSA_DIR="/etc/openvpn/easy-rsa"

mkdir -p "${OPENVPN_DIR}"
rm -rf "${EASYRSA_DIR}"
make-cadir "${EASYRSA_DIR}"

cd "${EASYRSA_DIR}"

./easyrsa init-pki
EASYRSA_BATCH=1 ./easyrsa build-ca nopass
EASYRSA_BATCH=1 ./easyrsa build-server-full spygym-server nopass
./easyrsa gen-crl
openvpn --genkey secret "${PKI_DIR}/tls-crypt.key"

mkdir -p "${PKI_DIR}/issued" "${PKI_DIR}/private"
cp -f pki/ca.crt "${PKI_DIR}/ca.crt"
cp -f pki/issued/spygym-server.crt "${PKI_DIR}/issued/server.crt"
cp -f pki/private/spygym-server.key "${PKI_DIR}/private/server.key"
cp -f pki/crl.pem "${PKI_DIR}/crl.pem"
chmod 600 "${PKI_DIR}/private/server.key" "${PKI_DIR}/tls-crypt.key"

echo
echo "PKI base criada em ${PKI_DIR}"
echo "Para emitir um cliente por unidade, use:"
echo "bash scripts/issue_openvpn_client_cert.sh NOME_DO_CLIENTE"
