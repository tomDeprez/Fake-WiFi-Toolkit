#!/bin/bash
set -euo pipefail

DOCKER_NETWORK_PREFIX="wifi_network"
DOCKER_SUBNET_BASE="192.168"
DOCKER_SUBNET_MASK="/24"

create_interface() {
    local name="$1"
    local container_name="virtual_interface_${name}"
    
    echo "[ℹ️] Création de l'interface virtuelle ${name}..."
    
    # Supprimer l'ancien conteneur s'il existe
    docker rm -f "${container_name}" 2>/dev/null || true
    
    # Créer le conteneur avec accès réseau hôte
    if ! docker run -d \
        --name "${container_name}" \
        --network host \
        --cap-add=NET_ADMIN \
        --cap-add=SYS_ADMIN \
        -v /dev:/dev \
        alpine sh -c 'apk add --no-cache sudo wireless-tools iw hostapd dnsmasq iptables tcpdump iproute2 net-tools && echo "root ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/root && tail -f /dev/null'; then
        echo "[❌] Erreur lors de la création du conteneur"
        exit 1
    fi
    
    echo "[✅] Interface virtuelle ${name} créée avec succès"
}

delete_interface() {
    local name="$1"
    local network_name="${DOCKER_NETWORK_PREFIX}_${name}"
    local container_name="virtual_interface_${name}"

    echo "[ℹ️] Suppression de l'interface virtuelle ${name}..."

    # Supprimer le conteneur
    if docker ps -a | grep -q "${container_name}"; then
        echo "[ℹ️] Suppression du conteneur..."
        docker rm -f "${container_name}" || true
    fi

    # Supprimer le réseau
    if docker network ls | grep -q "${network_name}"; then
        echo "[ℹ️] Suppression du réseau..."
        docker network rm "${network_name}" || true
    fi

    echo "[✅] Interface virtuelle ${name} supprimée avec succès"
}

# Nettoyer tous les réseaux et conteneurs
cleanup_all() {
    echo "[ℹ️] Nettoyage complet des réseaux et conteneurs..."

    # Supprimer tous les conteneurs liés aux interfaces virtuelles
    docker ps -a --filter "name=virtual_interface_" -q | xargs -r docker rm -f

    # Supprimer tous les réseaux wifi_network
    docker network ls --filter "name=wifi_network" -q | xargs -r docker network rm

    echo "[✅] Nettoyage terminé"
}

case "${1:-}" in
create)
    if [ -z "${2:-}" ]; then
        echo "[❌] Nom d'interface requis"
        exit 1
    fi
    create_interface "$2"
    ;;
delete)
    if [ -z "${2:-}" ]; then
        echo "[❌] Nom d'interface requis"
        exit 1
    fi
    delete_interface "$2"
    ;;
cleanup)
    cleanup_all
    ;;
*)
    echo "Usage: $0 {create|delete|cleanup} [interface_name]"
    exit 1
    ;;
esac
