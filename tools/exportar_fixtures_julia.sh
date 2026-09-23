#!/usr/bin/env bash
# Extrai um snapshot do FPSO_Siz Julia num diretório temporário (git archive: só leitura
# no repositório de origem) e exporta as fixtures para tests/fixtures/julia/.
#
#     tools/exportar_fixtures_julia.sh [commit]     (default: ab58fc6)
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
ORIGEM="$RAIZ/../FPSO_Siz"
COMMIT="$(git -C "$ORIGEM" rev-parse "${1:-ab58fc6}")"
SNAP="$(mktemp -d)"
trap 'rm -rf "$SNAP"' EXIT
git -C "$ORIGEM" archive "$COMMIT" | tar -x -C "$SNAP"
julia --startup-file=no --project="$SNAP" "$RAIZ/tools/exportar_fixtures_julia.jl" \
      "$SNAP" "$COMMIT" "$RAIZ/tests/fixtures/julia"
mkdir -p "$RAIZ/tests/fixtures/julia/casos"
cp "$SNAP"/config/cases/exemplo_*.toml "$RAIZ/tests/fixtures/julia/casos/"
cp "$SNAP"/config/stream.toml "$RAIZ/tests/fixtures/julia/casos/stream.toml"
