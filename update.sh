#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

if [ ! -d .git ]; then
    echo "[ERROR] Este diretório não é um clone do git" >&2
    exit 1
fi

old=$(cat version.txt)
echo "[INFO] Versão atual: $old"

git fetch --quiet origin
git pull --ff-only --quiet

new=$(cat version.txt)

if [ -x .venv/bin/pip ]; then
    echo "[INFO] Atualizando dependências"
    .venv/bin/pip install --quiet -r requirements.txt
fi

if [ "$old" = "$new" ]; then
    echo "[SUCCESS] Já está na versão mais recente ($new)"
else
    echo "[SUCCESS] Atualizado de $old para $new"
fi
