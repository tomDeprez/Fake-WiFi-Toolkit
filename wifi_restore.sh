#!/bin/bash

# Trouver l'interface monitor active
MONITOR_INTERFACE=$(iw dev | awk '$1=="Interface" {print $2}' | grep "mon")

if [[ -z "$MONITOR_INTERFACE" ]]; then
    echo "[✅] Aucune interface en mode monitor détectée."
    exit 0
fi

# Récupérer le nom de l'interface Wi-Fi d'origine (ex: wlp7s0)
BASE_INTERFACE=${MONITOR_INTERFACE%"mon"}

echo "[🔄] Restauration de l'interface $BASE_INTERFACE..."

# Désactiver le mode monitor
sudo airmon-ng stop "$MONITOR_INTERFACE"

# Redémarrer NetworkManager et wpa_supplicant
echo "[🔄] Redémarrage des services réseau..."
sudo systemctl restart NetworkManager
sudo systemctl restart wpa_supplicant

echo "[✅] Mode normal activé sur $BASE_INTERFACE. Connexion rétablie !"

