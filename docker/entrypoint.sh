#!/bin/bash
set -e

echo "=========================================="
echo " Test MCP Server"
echo "=========================================="
echo " Host: 0.0.0.0:${PORT:-8000}"
echo " Workers: ${WORKERS:-1}"
echo "=========================================="

exec uvicorn app:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${WORKERS:-1}" \
    --log-level "${LOG_LEVEL:-info}"
