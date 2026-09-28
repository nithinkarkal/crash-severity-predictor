#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# generate-dev-cert.sh - Create a development self-signed TLS certificate for
# the ASP project (hostname: asp.local).
#
# Usage:
#   bash infra/nginx/generate-dev-cert.sh
#
# Output:
#   infra/nginx/certs/nginx.crt   - self-signed public certificate (4096-byte RSA)
#   infra/nginx/certs/nginx.key   - private key
#
# NOTE:
#   - Development / local only. Do not use these certificates in production.
#   - The generated files are git-ignored (see .gitignore lines 165-166).
#   - Requires OpenSSH / OpenSSL (pre-installed on most Linux distros).
# ---------------------------------------------------------------------------
set -euo pipefail

CERT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/certs" && pwd)"
HOSTNAME="asp.local"
VALID_DAYS=365

mkdir -p "${CERT_DIR}"

echo "[*] Generating self-signed certificate for '${HOSTNAME}' (${VALID_DAYS} days)..."
echo "    Output: ${CERT_DIR}"

openssl req -x509 \
    -nodes \
    -newkey rsa:4096 \
    -keyout "${CERT_DIR}/nginx.key" \
    -out    "${CERT_DIR}/nginx.crt" \
    -days   "${VALID_DAYS}" \
    -subj   "/CN=${HOSTNAME}" \
    -addext "subjectAltName=DNS:${HOSTNAME},IP:127.0.0.1"

chmod 600 "${CERT_DIR}/nginx.key"
chmod 644 "${CERT_DIR}/nginx.crt"

echo "[+] Done."
echo "    ${CERT_DIR}/nginx.crt"
echo "    ${CERT_DIR}/nginx.key"
echo ""
echo "Remember to add the following entry to /etc/hosts:"
echo "    127.0.0.1 ${HOSTNAME}"
