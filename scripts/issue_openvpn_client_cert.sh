#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Uso: bash scripts/issue_openvpn_client_cert.sh NOME_DO_CLIENTE"
  exit 1
fi

CLIENT_NAME="$1"
EASYRSA_DIR="/etc/openvpn/easy-rsa"

if [[ ! -d "${EASYRSA_DIR}" ]]; then
  echo "Easy-RSA nao encontrado em ${EASYRSA_DIR}. Rode antes scripts/create_openvpn_pki_ubuntu.sh"
  exit 1
fi

cd "${EASYRSA_DIR}"
EASYRSA_BATCH=1 ./easyrsa build-client-full "${CLIENT_NAME}" nopass

echo
echo "Cliente emitido: ${CLIENT_NAME}"
echo "Certificado: ${EASYRSA_DIR}/pki/issued/${CLIENT_NAME}.crt"
echo "Chave: ${EASYRSA_DIR}/pki/private/${CLIENT_NAME}.key"
