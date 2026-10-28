#!/bin/bash
# gen-certs.sh — Generate a self-signed TLS certificate for HPMS
# Run this ONCE on EC2 before starting the production stack.
# The cert is valid for 365 days and is stored in nginx/certs/.
#
# Usage:
#   chmod +x scripts/gen-certs.sh
#   ./scripts/gen-certs.sh

set -e

CERT_DIR="$(dirname "$0")/../nginx/certs"
mkdir -p "$CERT_DIR"

# Replace the CN with your EC2 public IP or domain if you have one
EC2_IP="${1:-localhost}"

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$CERT_DIR/hpms.key" \
  -out    "$CERT_DIR/hpms.crt" \
  -subj   "/C=IN/ST=State/L=City/O=MediCare Hospital/CN=${EC2_IP}" \
  -addext "subjectAltName=IP:${EC2_IP},DNS:localhost"

chmod 600 "$CERT_DIR/hpms.key"
echo "✅ Certificate generated: $CERT_DIR/hpms.crt"
echo "   CN / SAN = ${EC2_IP}"
echo "   Valid for 365 days."
