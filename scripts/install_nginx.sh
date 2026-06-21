#!/usr/bin/env bash
# Nginx reverse proxy para EPayRoll (eplanilla.etsrv.site → :8001)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOMAIN="${EPAYROLL_DOMAIN:-eplanilla.etsrv.site}"
SITE_SRC="$ROOT/scripts/nginx-eplanilla.etsrv.site.conf"
SITE_DST="/etc/nginx/sites-available/${DOMAIN}.conf"
SITE_LINK="/etc/nginx/sites-enabled/${DOMAIN}.conf"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Ejecutar con sudo: sudo bash scripts/install_nginx.sh"
  exit 1
fi

if ! command -v nginx >/dev/null 2>&1; then
  echo "nginx no instalado"
  exit 1
fi

mkdir -p /var/www/certbot
install -m 644 "$SITE_SRC" "$SITE_DST"
ln -sf "$SITE_DST" "$SITE_LINK"
nginx -t
systemctl reload nginx

if command -v certbot >/dev/null 2>&1; then
  if [[ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
    echo "→ Solicitando certificado TLS para ${DOMAIN}…"
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email || {
      echo "⚠️  certbot falló — verifica DNS/proxy Cloudflare (modo SSL Full recomendado)"
    }
  else
    echo "✓ Certificado existente para ${DOMAIN}"
    certbot install --cert-name "$DOMAIN" 2>/dev/null || true
  fi
fi

echo ""
echo "✅ Nginx configurado: https://${DOMAIN}/app/"
echo "   Actualiza .env: EPAYROLL_PUBLIC_URL=https://${DOMAIN}"
