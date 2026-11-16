#!/bin/sh
# Compila cine para esta máquina y lo deja en bin/<so>-<arq>/. Para las demás plataformas, usa el
# workflow .github/workflows/motor.yml (compila en runners nativos de cada sistema) o `nix build`.
set -e
d=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cargo test --release --manifest-path "$d/Cargo.toml"
cargo build --release --manifest-path "$d/Cargo.toml"
os=$(uname -s | tr '[:upper:]' '[:lower:]'); arch=$(uname -m)
case "$arch" in x86_64|amd64) arch=x64 ;; arm64|aarch64) arch=arm64 ;; esac
mkdir -p "$d/../bin/$os-$arch"
cp "$d/target/release/cine" "$d/../bin/$os-$arch/cine"
echo "bin/$os-$arch/cine"
