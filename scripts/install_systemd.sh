#!/usr/bin/env bash
# Instala y habilita epayroll-api como servicio systemd (apps srv).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_SRC="$ROOT/scripts/epayroll-api.service"
UNIT_DST="/etc/systemd/system/epayroll-api.service"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Ejecutar con sudo: sudo bash scripts/install_systemd.sh"
  exit 1
fi

if [[ ! -f "$ROOT/.venv/bin/python" ]]; then
  echo "Falta venv en $ROOT/.venv — ejecuta: python3 -m venv .venv && pip install -r requirements.txt"
  exit 1
fi

if [[ ! -f "$ROOT/.env" ]]; then
  echo "Falta $ROOT/.env — copia desde .env.example y configura DATABASE_URL"
  exit 1
fi

install -m 644 "$UNIT_SRC" "$UNIT_DST"
systemctl daemon-reload
systemctl enable epayroll-api.service
systemctl restart epayroll-api.service

echo ""
echo "✅ epayroll-api instalado"
systemctl --no-pager status epayroll-api.service || true
echo ""
echo "Comandos útiles:"
echo "  journalctl -u epayroll-api -f"
echo "  curl http://localhost:8001/health"
