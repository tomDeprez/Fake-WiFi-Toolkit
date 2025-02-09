# Fake WiFi Toolkit

## Description
**Fake WiFi Toolkit** est une suite de scripts Bash permettant de configurer un faux point d'accès Wi-Fi avec un portail captif pour collecter les identifiants des utilisateurs, modifier aléatoirement l'adresse MAC d'une interface, scanner les réseaux Wi-Fi et capturer les paquets en mode monitor.

⚠ **Ce projet est destiné à des fins de test et d'audit de sécurité. L'utilisation de ces scripts à des fins malveillantes est illégale.**

## Scripts inclus

### 1. `fake_wifi.sh`
- Crée un faux point d'accès Wi-Fi ouvert
- Utilise `hostapd` pour la gestion du point d'accès
- Configure un serveur DHCP avec `dnsmasq`
- Redirige le trafic HTTP vers un portail captif simulant une connexion Wi-Fi

### 2. `fake_wifi_restore.sh`
- Arrête le faux point d'accès Wi-Fi
- Restaure la configuration réseau initiale
- Réactive `NetworkManager` et le DHCP

### 3. `mac_random.sh`
- Change aléatoirement l'adresse MAC de l'interface Wi-Fi pour anonymiser la connexion

### 4. `mac_reset.sh`
- Restaure l'adresse MAC d'origine

### 5. `wifi_sniffer.sh`
- Active le mode monitor sur l'interface Wi-Fi
- Scanne les réseaux environnants et affiche les informations (SSID, canal, sécurité)
- Capture le trafic HTTP en clair pour extraire des identifiants

### 6. `wifi_sniffer_cookie.sh`
- Capture et extrait les cookies HTTP émis en clair sur le réseau

### 7. `wifi_sniffer_all.sh`
- Capture toutes les requêtes POST HTTP et autres informations sensibles

### 8. `wifi_restore.sh`
- Restaure l'interface Wi-Fi en mode normal
- Désactive le mode monitor et redémarre `NetworkManager`

## Prérequis
- **Linux** (Testé sur Kali Linux et Ubuntu)
- **Droits root** (Tous les scripts doivent être lancés avec `sudo`)
- **Matériel compatible Wi-Fi** prenant en charge le mode monitor

## Installation des dépendances
Avant d'exécuter les scripts, assurez-vous que les paquets suivants sont installés :
```bash
sudo apt update && sudo apt install -y hostapd dnsmasq iw wireless-tools aircrack-ng tcpdump macchanger
```

## Utilisation

### Démarrer un faux point d'accès Wi-Fi :
```bash
sudo ./fake_wifi.sh
```

### Arrêter le faux Wi-Fi et restaurer la configuration :
```bash
sudo ./fake_wifi_restore.sh
```

### Changer l'adresse MAC de l'interface Wi-Fi :
```bash
sudo ./mac_random.sh
```

### Restaurer l'adresse MAC d'origine :
```bash
sudo ./mac_reset.sh
```

### Scanner les réseaux Wi-Fi et capturer le trafic :
```bash
sudo ./wifi_sniffer.sh
```

### Capturer les cookies des sessions HTTP :
```bash
sudo ./wifi_sniffer_cookie.sh
```

### Capturer toutes les requêtes sensibles sur un réseau :
```bash
sudo ./wifi_sniffer_all.sh
```

### Restaurer l'interface Wi-Fi et désactiver le mode monitor :
```bash
sudo ./wifi_restore.sh
```

## Avertissement
L'utilisation de ces scripts sur un réseau sans autorisation explicite est **strictement interdite** par la loi. Assurez-vous d'avoir l'accord du propriétaire du réseau avant toute utilisation.

**Auteur :** Tom
**Licence :** Usage éducatif uniquement

