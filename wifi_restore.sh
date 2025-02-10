#!/bin/bash

# Configuration du logging
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/wifi_restore.log"

# Création du dossier logs s'il n'existe pas
mkdir -p "$LOG_DIR"

# Fonction de logging
log() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local message="[$timestamp] $1"
    echo "$message" | tee -a "$LOG_FILE"
}

# Nettoyage du fichier de log au démarrage
echo "" > "$LOG_FILE"

# Redirection de stderr vers le fichier de log
exec 2>> "$LOG_FILE"

# Trouver l'interface monitor active
MONITOR_INTERFACE=$(iw dev | awk '$1=="Interface" {print $2}' | grep "mon")

if [[ -z "$MONITOR_INTERFACE" ]]; then
    log "[✅] Aucune interface en mode monitor détectée."
    exit 0
fi

# Récupérer le nom de l'interface Wi-Fi d'origine (ex: wlp7s0)
BASE_INTERFACE=${MONITOR_INTERFACE%"mon"}

log "[🔄] Restauration de l'interface $BASE_INTERFACE..."

# Désactiver le mode monitor
sudo airmon-ng stop "$MONITOR_INTERFACE"

# Redémarrer NetworkManager et wpa_supplicant
log "[🔄] Redémarrage des services réseau..."
sudo systemctl restart NetworkManager
sudo systemctl restart wpa_supplicant

log "[✅] Mode normal activé sur $BASE_INTERFACE. Connexion rétablie !"

