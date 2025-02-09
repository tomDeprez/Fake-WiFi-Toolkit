#!/bin/bash

# Interface Wi-Fi détectée
INTERFACE="wlp7s0"

# Désactiver l'interface
sudo ip link set dev $INTERFACE down

# Restaurer l'adresse MAC d'origine
sudo macchanger -p $INTERFACE

# Réactiver l'interface
sudo ip link set dev $INTERFACE up

# Redémarrer la connexion Wi-Fi
sudo systemctl restart NetworkManager

# Afficher l'adresse MAC actuelle
ip link show $INTERFACE | grep ether

echo "Adresse MAC restaurée."

