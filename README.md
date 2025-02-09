
```markdown
# 🕵️‍♂️ Fake WiFi Toolkit - The Dark Side of Connectivity

![Hacker](https://img.shields.io/badge/Theme-Cyber_Security-red) ![License](https://img.shields.io/badge/License-Educational_Use_only-blue) ![Platform](https://img.shields.io/badge/Platform-Linux-black)

**Fake WiFi Toolkit** est une boîte à outils ultime pour explorer les failles des réseaux Wi-Fi. Ce projet, conçu pour les tests de sécurité et les audits, simule un point d'accès Wi-Fi malveillant, capture des données sensibles et manipule les connexions réseau. Utilise-le à bon escient, car chaque grande puissance implique de grandes responsabilités. 🚨

---

## 🎯 Description

Plongez dans l'ombre des réseaux Wi-Fi avec **Fake WiFi Toolkit**. Cette suite de scripts Bash vous permet de :
- Créer un **faux point d'accès Wi-Fi** avec un portail captif pour piéger les utilisateurs.
- **Changer aléatoirement l'adresse MAC** de votre interface pour rester anonyme.
- **Scanner les réseaux Wi-Fi** environnants et capturer des données sensibles en temps réel.
- **Extraire des identifiants, cookies et requêtes HTTP** pour analyser les vulnérabilités.

⚠️ **Avertissement :** Ce projet est strictement destiné à des fins éducatives et de test de sécurité. Toute utilisation malveillante est illégale et contraire à l'éthique.

---

## 🛠️ Scripts Inclus

### 1. `fake_wifi.sh`
- 🕸️ Crée un faux point d'accès Wi-Fi ouvert.
- 🛠️ Utilise `hostapd` pour gérer le point d'accès.
- 🌐 Configure un serveur DHCP avec `dnsmasq`.
- 🎣 Redirige le trafic HTTP vers un portail captif pour simuler une connexion Wi-Fi.

### 2. `fake_wifi_restore.sh`
- 🛑 Arrête le faux point d'accès Wi-Fi.
- 🔄 Restaure la configuration réseau initiale.
- 🔌 Réactive `NetworkManager` et le DHCP.

### 3. `mac_random.sh`
- 🎲 Change aléatoirement l'adresse MAC de l'interface Wi-Fi pour anonymiser votre connexion.

### 4. `mac_reset.sh`
- 🔙 Restaure l'adresse MAC d'origine.

### 5. `wifi_sniffer.sh`
- 👁️ Active le mode monitor sur l'interface Wi-Fi.
- 📡 Scanne les réseaux environnants et affiche les informations (SSID, canal, sécurité).
- 🕵️ Capture le trafic HTTP en clair pour extraire des identifiants.

### 6. `wifi_sniffer_cookie.sh`
- 🍪 Capture et extrait les cookies HTTP émis en clair sur le réseau.

### 7. `wifi_sniffer_all.sh`
- 📂 Capture toutes les requêtes POST HTTP et autres informations sensibles.

### 8. `wifi_restore.sh`
- 🔄 Restaure l'interface Wi-Fi en mode normal.
- 🚫 Désactive le mode monitor et redémarre `NetworkManager`.

---

## 🧰 Prérequis

- **Système d'exploitation :** Linux (testé sur Kali Linux et Ubuntu).
- **Permissions :** Droits root requis (tous les scripts doivent être lancés avec `sudo`).
- **Matériel :** Carte Wi-Fi compatible avec le mode monitor.

---

## ⚙️ Installation des Dépendances

Avant de plonger dans l'ombre, assurez-vous que les outils nécessaires sont installés :

```bash
sudo apt update && sudo apt install -y hostapd dnsmasq iw wireless-tools aircrack-ng tcpdump macchanger
```

---

## 🚀 Utilisation

### 🕵️‍♂️ Démarrer un faux point d'accès Wi-Fi :
```bash
sudo ./fake_wifi.sh
```

### 🛑 Arrêter le faux Wi-Fi et restaurer la configuration :
```bash
sudo ./fake_wifi_restore.sh
```

### 🎲 Changer l'adresse MAC de l'interface Wi-Fi :
```bash
sudo ./mac_random.sh
```

### 🔙 Restaurer l'adresse MAC d'origine :
```bash
sudo ./mac_reset.sh
```

### 📡 Scanner les réseaux Wi-Fi et capturer le trafic :
```bash
sudo ./wifi_sniffer.sh
```

### 🍪 Capturer les cookies des sessions HTTP :
```bash
sudo ./wifi_sniffer_cookie.sh
```

### 📂 Capturer toutes les requêtes sensibles sur un réseau :
```bash
sudo ./wifi_sniffer_all.sh
```

### 🔄 Restaurer l'interface Wi-Fi et désactiver le mode monitor :
```bash
sudo ./wifi_restore.sh
```

---

## ⚠️ Avertissement Légal

L'utilisation de ces scripts sur un réseau sans autorisation explicite est **strictement interdite** par la loi. Assurez-vous d'avoir l'accord du propriétaire du réseau avant toute utilisation. Ce projet est conçu à des fins éducatives et de test de sécurité uniquement.

---

## 👤 Auteur
**Tom** - Explorateur des réseaux et défenseur de la sécurité.

## 📜 Licence
**Usage éducatif uniquement.** Toute utilisation malveillante est interdite.

---

🛡️ **Rappelez-vous :** Avec de grands pouvoirs viennent de grandes responsabilités. Utilisez ce toolkit à bon escient. 🛡️
```