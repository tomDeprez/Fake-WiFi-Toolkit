#!/bin/bash
set -euo pipefail
trap 'echo "[❌] Erreur sur la ligne ${LINENO} dans la commande: ${BASH_COMMAND}"' ERR

export PATH=$PATH:/sbin:/usr/sbin

if [[ $EUID -ne 0 ]]; then
    echo "[❌] Ce script doit être exécuté en tant que root."
    exit 1
fi

# Arrêt des processus du faux Wi-Fi s'ils sont encore en cours
echo "[ℹ️] Arrêt de hostapd, dnsmasq et du portail captif s'ils sont en cours..."
pkill hostapd || true
pkill dnsmasq || true
pkill -f captive.py || true

# Suppression de l'interface virtuelle ap0 si elle existe
if ip link show ap0 &>/dev/null; then
    echo "[ℹ️] Suppression de l'interface virtuelle ap0..."
    ip link set ap0 down || true
    if command -v iw &>/dev/null; then
        iw dev ap0 del || true
    else
        ip link delete ap0 || true
    fi
fi

# Fonction pour exécuter une commande en l'affichant
run_cmd() {
    echo "[ℹ️] Exécution: $*"
    "$@"
}

echo "[ℹ️] Réactivation de systemd-resolved..."
run_cmd systemctl enable systemd-resolved --now
run_cmd systemctl restart systemd-resolved

if [ -e /run/systemd/resolve/stub-resolv.conf ]; then
    run_cmd ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf
    echo "[✅] /etc/resolv.conf lié à /run/systemd/resolve/stub-resolv.conf"
elif [ -e /run/systemd/resolve/resolv.conf ]; then
    run_cmd ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf
    echo "[✅] /etc/resolv.conf lié à /run/systemd/resolve/resolv.conf"
else
    echo "[❌] Aucun fichier resolv.conf de systemd-resolved trouvé."
fi

echo "[ℹ️] Contenu de /etc/resolv.conf :"
grep '^nameserver' /etc/resolv.conf || echo "[⚠️] Aucun nameserver trouvé dans /etc/resolv.conf"

echo "[ℹ️] Suppression des règles NAT..."
run_cmd iptables -t nat -F

echo "[ℹ️] Désactivation de l'IP forwarding..."
run_cmd sysctl -w net.ipv4.ip_forward=0

if command -v nmcli &>/dev/null; then
    echo "[ℹ️] Réactivation de NetworkManager sur les interfaces Wi-Fi..."
    for iface in $(nmcli device status | awk '/wifi/ {print $1}'); do
        if nmcli device set "$iface" managed yes; then
            echo "[✅] $iface est désormais géré par NetworkManager"
        else
            echo "[❌] Impossible de réactiver $iface"
        fi
    done
fi

echo "[ℹ️] Redémarrage de NetworkManager..."
run_cmd systemctl restart NetworkManager

renew_dhcp() {
    local iface="$1"
    echo "[ℹ️] Flush des adresses IP et des routes pour $iface..."
    run_cmd ip addr flush dev "$iface"
    run_cmd ip route flush dev "$iface"
    echo "[ℹ️] Flush du cache de routage..."
    ip route flush cache || true
    if command -v dhclient &>/dev/null; then
        echo "[ℹ️] Renouvellement du bail DHCP pour $iface avec dhclient..."
        if ! dhclient -r "$iface"; then
            echo "[⚠️] Échec de libérer le bail DHCP pour $iface"
        fi
        if dhclient "$iface"; then
            echo "[✅] Bail DHCP renouvelé pour $iface avec dhclient"
        else
            echo "[❌] Échec du renouvellement du bail DHCP pour $iface avec dhclient"
        fi
    elif command -v nmcli &>/dev/null; then
        echo "[ℹ️] Renouvellement du bail DHCP pour $iface avec nmcli..."
        if ! nmcli device reapply "$iface"; then
            echo "[⚠️] Échec du renouvellement du bail DHCP pour $iface via nmcli."
            echo "[ℹ️] Tentative de reconnecter $iface..."
            if nmcli device connect "$iface"; then
                echo "[✅] $iface reconnecté. Nouvelle tentative de renouvellement..."
                if nmcli device reapply "$iface"; then
                    echo "[✅] Bail DHCP renouvelé pour $iface via nmcli"
                else
                    echo "[❌] Échec du renouvellement du bail DHCP pour $iface via nmcli après reconnexion"
                fi
            else
                echo "[❌] Échec de connecter $iface avec nmcli"
            fi
        else
            echo "[✅] Bail DHCP renouvelé pour $iface via nmcli"
        fi
    else
        echo "[⚠️] Aucun client DHCP (dhclient ou nmcli) trouvé pour renouveler le bail sur $iface"
    fi
}

echo "[ℹ️] Renouvellement du bail DHCP sur les interfaces Wi-Fi..."
for iface in $(nmcli device status | awk '/wifi/ {print $1}'); do
    if [[ "$iface" == ap0 || "$iface" == p2p* ]]; then
         echo "[ℹ️] Ignorer l'interface $iface (virtuel ou p2p)"
         continue
    fi
    renew_dhcp "$iface"
done

echo "[✅] La configuration réseau a été rétablie."

