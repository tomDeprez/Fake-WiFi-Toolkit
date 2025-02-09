#!/bin/bash

# Interface Wi-Fi détectée
INTERFACE="wlp7s0"

# Vérifier si macchanger est installé
if ! command -v macchanger &> /dev/null; then
    echo "macchanger n'est pas installé. Installation en cours..."
    sudo apt update && sudo apt install macchanger -y
fi

# Désactiver l'interface
sudo ip link set dev $INTERFACE down

# Changer l'adresse MAC de manière aléatoire
sudo macchanger -r $INTERFACE

# Réactiver l'interface
sudo ip link set dev $INTERFACE up

# Redémarrer la connexion Wi-Fi pour prendre en compte le changement
sudo systemctl restart NetworkManager

# Afficher la nouvelle adresse MAC
ip link show $INTERFACE | grep ether

echo "Adresse MAC changée avec succès."

