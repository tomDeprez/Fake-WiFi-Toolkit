from flask import Flask, render_template, jsonify, request, redirect, url_for
import asyncio
import websockets
import json
import os
import subprocess
import netifaces
from datetime import datetime
from threading import Thread
import pexpect
from pathlib import Path

app = Flask(__name__)

# Configuration des scripts avec des descriptions plus détaillées
SCRIPTS = {
    'fake_wifi': {
        'name': 'Point d\'Accès Malveillant',
        'script': './fake_wifi.sh',
        'icon': 'wifi',
        'description': 'Crée un point d\'accès Wi-Fi piège pour capturer les mots de passe',
        'status': 'stopped',
        'requires_monitor': True,
        'requires_sudo': True
    },
    'wifi_sniffer': {
        'name': 'Analyseur Wi-Fi',
        'script': './wifi_sniffer.sh',
        'icon': 'search',
        'description': 'Capture et analyse le trafic Wi-Fi en temps réel',
        'status': 'stopped',
        'requires_monitor': True,
        'requires_sudo': True
    },
    'wifi_sniffer_all': {
        'name': 'Analyseur Réseau Complet',
        'script': './wifi_sniffer_all.sh',
        'icon': 'network-wired',
        'description': 'Capture tout le trafic réseau, y compris les paquets HTTP',
        'status': 'stopped',
        'requires_monitor': True,
        'requires_sudo': True
    },
    'mac_random': {
        'name': 'Changeur MAC',
        'script': './mac_random.sh',
        'icon': 'random',
        'description': 'Change aléatoirement l\'adresse MAC de l\'interface',
        'status': 'stopped',
        'requires_monitor': False,
        'requires_sudo': True
    },
    'wifi_jammer': {
        'name': 'Brouilleur Wi-Fi',
        'script': './wifi_jammer.sh',
        'icon': 'ban',
        'description': 'Scanne les réseaux Wi-Fi et lance une attaque de désauthentification',
        'status': 'stopped',
        'requires_monitor': True,
        'requires_sudo': True
    },
    'wifi_stealer' : {
        'name': 'Capture Handshake',
        'script': './wifi_stealer.sh',
        'icon': 'lock',
        'description': 'Capture les handshakes WPA2/WPA3 pour analyse',
        'status': 'stopped',
        'requires_monitor': True,
        'requires_sudo': True
    }
}

CONFIG_FILE = 'config.json'

# Constante pour le dossier des logs
LOGS_DIR = "logs"
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# Ajout des constantes pour Docker
DOCKER_NETWORK = "wifi_network"
DOCKER_SUBNET = "172.18.0.0/16"

# Ajout de la constante pour le fichier de stockage
VIRTUAL_INTERFACES_FILE = "virtual_interfaces.json"

# Gestion des processus et des WebSockets
class ScriptProcess:
    def __init__(self, script_id, websocket, interface=None):
        self.script_id = script_id
        self.websocket = websocket
        self.interface = interface
        self.process = None
        self.output_buffer = []
        self.status = 'stopped'
        print(f"ScriptProcess initialisé avec interface: {self.interface}")  # Debug

    async def expect_async(self, patterns):
        """Méthode asynchrone pour attendre un pattern dans la sortie du processus"""
        try:
            return await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.process.expect(patterns, timeout=5)
            )
        except pexpect.TIMEOUT:
            return -1
        except pexpect.EOF:
            return -2
        except Exception as e:
            print(f"Erreur dans expect_async: {e}")
            return -3

    async def send_message(self, type, message):
        try:
            response = {
                'script': self.script_id,
                'interface': self.interface,
                'type': type,
                'message': message,
                'target': 'docker' if self.interface else 'host'
            }
            print(f"Envoi du message: {response}")  # Debug
            await self.websocket.send(json.dumps(response))
        except Exception as e:
            print(f"Erreur lors de l'envoi du message: {e}")  # Debug
            pass

    async def start(self, sudo_password):
        try:
            script_path = os.path.abspath(SCRIPTS[self.script_id]['script'])
            if not os.path.exists(script_path):
                await self.send_message('error', f"Script introuvable: {script_path}")
                return False

            script_name = os.path.basename(script_path)
            print(f"Chemin du script: {script_path}")
            print(f"Nom du script: {script_name}")

            if self.interface:
                container_name = f"virtual_interface_{self.interface}"
                
                # Installation des dépendances avec les bons noms de paquets pour Alpine
                await self.send_message('info', "Installation des dépendances...")
                print("Installation des paquets dans le conteneur...")
                
                # Mise à jour des dépôts
                update_cmd = f"docker exec {container_name} apk update"
                try:
                    update_result = subprocess.run(update_cmd, shell=True, capture_output=True, text=True)
                    print(f"Résultat mise à jour: {update_result.stdout}")
                except subprocess.CalledProcessError as e:
                    print(f"Erreur mise à jour: {e.stderr}")
                
                # Installation des paquets un par un pour mieux identifier les erreurs
                packages = [
                    "sudo",
                    "bash",
                    "wireless-tools",
                    "iw",
                    "hostapd",
                    "dnsmasq",
                    "iptables",
                    "tcpdump",
                    "iproute2",  # remplace ip-tools
                    "net-tools"
                ]
                
                for package in packages:
                    await self.send_message('info', f"Installation de {package}...")
                    install_cmd = f"docker exec {container_name} apk add --no-cache {package}"
                    try:
                        result = subprocess.run(install_cmd, shell=True, capture_output=True, text=True)
                        print(f"Installation de {package}: {result.stdout}")
                        if result.stderr:
                            print(f"Erreur pour {package}: {result.stderr}")
                    except subprocess.CalledProcessError as e:
                        await self.send_message('error', f"Erreur lors de l'installation de {package}: {str(e)}")
                        print(f"Erreur détaillée pour {package}: {e.stderr}")
                        continue

                # Détection de l'interface réseau avec plus de logs
                await self.send_message('info', "Détection de l'interface réseau...")
                
                try:
                    # Obtenir juste le nom de base de l'interface
                    iface_cmd = f"docker exec {container_name} sh -c \"ip -br link | grep -v lo | head -n1 | cut -d'@' -f1 | awk '{{print $1}}'\""
                    iface_result = subprocess.run(iface_cmd, shell=True, capture_output=True, text=True, check=True)
                    interface_name = iface_result.stdout.strip()
                    print(f"Interface détectée: '{interface_name}'")
                    
                    if not interface_name:
                        # Méthode alternative
                        backup_cmd = f"docker exec {container_name} sh -c \"ls /sys/class/net | grep -v lo | head -n1\""
                        backup_result = subprocess.run(backup_cmd, shell=True, capture_output=True, text=True)
                        interface_name = backup_result.stdout.strip()
                        print(f"Interface détectée (méthode alternative): '{interface_name}'")

                    if not interface_name:
                        await self.send_message('error', "Impossible de détecter l'interface réseau")
                        return False
                    
                    # Vérifier le support du mode moniteur
                    monitor_cmd = f"docker exec {container_name} iw dev {interface_name} info"
                    monitor_result = subprocess.run(monitor_cmd, shell=True, capture_output=True, text=True)
                    monitor_supported = "Supported interface modes" in monitor_result.stdout and "monitor" in monitor_result.stdout
                    print(f"Support du mode moniteur: {monitor_supported}")
                    
                    # Vérification du contenu avant la copie
                    await self.send_message('info', "Préparation de l'environnement...")
                    
                    # Créer la configuration
                    config = {
                        "wifi_interface": interface_name,
                        "monitor_supported": monitor_supported,
                        "virtual_support": True
                    }
                    
                    print(f"Configuration à créer: {json.dumps(config, indent=4)}")
                    
                    # Écrire la configuration dans le même dossier que le script
                    config_cmd = f"""docker exec {container_name} sh -c '
                        cd /root &&
                        echo \'{json.dumps(config)}\' > config.json &&
                        ls -la config.json'
                    """
                    subprocess.run(config_cmd, shell=True, check=True)
                    
                    # Copie du script
                    await self.send_message('info', "Copie du script...")
                    copy_cmd = f"docker cp {script_path} {container_name}:/root/{script_name}"
                    subprocess.run(copy_cmd, shell=True, check=True)
                    
                    # Permissions d'exécution
                    chmod_cmd = f"docker exec {container_name} chmod +x /root/{script_name}"
                    subprocess.run(chmod_cmd, shell=True, check=True)

                    # Vérification de l'environnement
                    verify_cmd = f"""docker exec {container_name} sh -c '
                        echo "=== Contenu du répertoire de travail ===" &&
                        pwd &&
                        ls -la /root &&
                        echo "=== Contenu du fichier config.json ===" &&
                        cat /root/config.json'
                    """
                    verify_result = subprocess.run(verify_cmd, shell=True, capture_output=True, text=True)
                    print("=== Vérification de l'environnement ===")
                    print(verify_result.stdout)

                    # Exécution du script dans /root
                    await self.send_message('info', "Exécution du script...")
                    cmd = f"docker exec -w /root {container_name} bash ./{script_name}"
                    print(f"Commande d'exécution: {cmd}")

                    self.process = pexpect.spawn(cmd, encoding='utf-8')
                    
                    if not self.interface:
                        index = await self.expect_async(['[sudo]', pexpect.EOF, pexpect.TIMEOUT])
                        if index == 0:
                            self.process.sendline(sudo_password)
                        elif index < 0:
                            await self.send_message('error', "Timeout ou erreur lors de l'attente du prompt sudo")
                            return False
                
                    self.status = 'running'
                    asyncio.create_task(self.read_output())
                    return True

                except subprocess.CalledProcessError as e:
                    print(f"Erreur détaillée: {e.stderr if e.stderr else e}")
                    await self.send_message('error', f"Erreur lors de la configuration réseau: {str(e)}")
                    return False

                # Configuration de sudo
                setup_sudo_cmd = f"""docker exec {container_name} sh -c 'echo "root ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/root'"""
                subprocess.run(setup_sudo_cmd, shell=True, check=True)
                
            else:
                cmd = f"sudo -S {script_path}"

            self.process = pexpect.spawn(cmd, encoding='utf-8')
            
            if not self.interface:
                index = await self.expect_async(['[sudo]', pexpect.EOF, pexpect.TIMEOUT])
                if index == 0:
                    self.process.sendline(sudo_password)
                elif index < 0:
                    await self.send_message('error', "Timeout ou erreur lors de l'attente du prompt sudo")
                    return False
            
            self.status = 'running'
            asyncio.create_task(self.read_output())
            return True

        except Exception as e:
            print(f"Erreur lors du démarrage: {e}")
            await self.send_message('error', f"Erreur de démarrage: {str(e)}")
            return False

    async def stop(self):
        if self.process and not self.process.closed:
            self.process.terminate(force=True)
            
            # Nettoyage
            if self.interface:
                try:
                    container_name = f"virtual_interface_{self.interface}"
                    script_name = os.path.basename(SCRIPTS[self.script_id]['script'])
                    cleanup_cmd = f"docker exec {container_name} rm -f /root/{script_name}"
                    subprocess.run(cleanup_cmd, shell=True, check=True)
                except:
                    pass
            else:
                self.process.close()
            self.status = 'stopped'
            SCRIPTS[self.script_id]['status'] = 'stopped'
            await self.send_message('info', "Script arrêté")

    async def read_output(self):
        try:
            while self.process and not self.process.closed:
                try:
                    line = await asyncio.get_event_loop().run_in_executor(
                        None, self.process.readline
                    )
                    if not line:
                        break
                    await self.send_message('output', line.strip())
                except:
                    break
        except Exception as e:
            await self.send_message('error', f"Erreur de lecture: {str(e)}")

    async def verify_sudo(self, password):
        try:
            # Utilisation de subprocess au lieu de pexpect pour la vérification
            process = await asyncio.create_subprocess_exec(
                'sudo', '-S', 'true',
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Envoi du mot de passe
            stdout, stderr = await process.communicate(input=f"{password}\n".encode())
            
            # Vérification du code de retour
            return process.returncode == 0
        except Exception as e:
            print(f"Erreur verification sudo: {str(e)}")
            return False

# Gestionnaire de connexion WebSocket
async def websocket_handler(websocket):
    processes = {}
    
    try:
        async for message in websocket:
            data = json.loads(message)
            script_id = data.get('script')
            command = data.get('command')
            interface = data.get('interface')
            target = data.get('target', 'host')
            
            # Logs de débogage
            print(f"Message reçu: {data}")
            print(f"Interface: {interface}")
            print(f"Target: {target}")

            if not script_id or script_id not in SCRIPTS:
                continue

            process_key = f"{script_id}-{interface}" if interface else script_id
            print(f"Process key: {process_key}")  # Debug

            if command == 'start':
                if process_key not in processes:
                    response = {
                        'script': script_id,
                        'interface': interface,
                        'type': 'password_prompt',
                        'message': f"Veuillez entrer le mot de passe sudo pour {target}",
                        'target': target
                    }
                    print(f"Envoi de la réponse: {response}")  # Debug
                    await websocket.send(json.dumps(response))
                
            elif command == 'password':
                print(f"Création du processus avec interface: {interface}")  # Debug
                process = ScriptProcess(script_id, websocket, interface)
                if await process.start(data.get('input')):
                    processes[process_key] = process
                    print(f"Processus créé avec succès: {process_key}")  # Debug
                
            elif command == 'stop':
                if process_key in processes:
                    await processes[process_key].stop()
                    del processes[process_key]

    except websockets.exceptions.ConnectionClosed:
        for process in processes.values():
            await process.stop()
    except Exception as e:
        print(f"Erreur WebSocket: {e}")

# Routes Flask
@app.route('/')
def index():
    config = load_config()
    scripts = load_scripts()
    virtual_interfaces = get_virtual_interfaces()  # Récupère les interfaces Docker existantes
    
    # Générer le HTML pour chaque interface Docker existante
    interfaces_html = {}
    for interface in virtual_interfaces:
        interfaces_html[interface] = render_template(
            'scripts_grid.html',
            scripts=scripts,
            interface_name=interface
        )
    
    return render_template(
        'index.html',
        config=config or {'virtual_support': True},  # Assure que virtual_support est True
        scripts=scripts,
        virtual_interfaces=virtual_interfaces,
        interfaces_html=interfaces_html  # Passe le HTML généré au template
    )

@app.route('/setup')
def setup():
    interfaces = get_network_interfaces()
    return render_template('setup.html', interfaces=interfaces)

def get_network_interfaces():
    interfaces = []
    for iface in netifaces.interfaces():
        try:
            addrs = netifaces.ifaddresses(iface)
            mac = addrs.get(netifaces.AF_LINK, [{'addr': 'N/A'}])[0]['addr']
            ip = addrs.get(netifaces.AF_INET, [{'addr': 'Non connecté'}])[0]['addr']
            
            # Détection Wi-Fi
            is_wifi = False
            try:
                output = subprocess.check_output(['iwconfig', iface], stderr=subprocess.DEVNULL).decode()
                is_wifi = 'no wireless extensions' not in output
            except:
                pass
                
            interfaces.append({
                'name': iface,
                'mac': mac,
                'ip': ip,
                'is_wifi': is_wifi
            })
        except:
            continue
    return interfaces

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return None

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def check_monitor_support(interface):
    try:
        # Vérifie les modes supportés avec 'iw list'
        iw_list_output = subprocess.check_output(['iw', 'list'], stderr=subprocess.STDOUT).decode()
        supports_monitor = "monitor" in iw_list_output.lower()

        # Vérifie le support des interfaces virtuelles
        supports_virtual = False
        try:
            # Vérifie si la carte supporte la création d'interfaces virtuelles
            iw_info = subprocess.check_output(['iw', interface, 'info'], stderr=subprocess.STDOUT).decode()
            # Recherche des indications de support multi-interface
            supports_virtual = any(indicator in iw_info.lower() for indicator in [
                "valid interface combinations",
                "simultaneous",
                "combination",
                "#{ managed } <= 1, #{ AP, P2P-client, P2P-GO } <= 1",
            ])
        except:
            pass

        # Vérifie le mode actuel
        iw_info_output = subprocess.check_output(['iw', interface, 'info'], stderr=subprocess.STDOUT).decode()
        is_monitor_mode = 'type monitor' in iw_info_output

        return {
            'supported': supports_monitor,
            'current_mode': 'monitor' if is_monitor_mode else 'managed',
            'virtual_support': supports_virtual
        }
    except subprocess.CalledProcessError:
        return {
            'supported': False,
            'current_mode': 'unknown',
            'virtual_support': False
        }

def check_docker_support():
    try:
        # Vérifie les permissions du socket Docker
        docker_socket = '/var/run/docker.sock'
        if not os.path.exists(docker_socket):
            print("Docker socket not found")
            return False
            
        socket_perms = os.stat(docker_socket)
        socket_group = socket_perms.st_gid
        
        # Vérifie si l'utilisateur est dans le groupe docker
        user_groups = os.getgroups()
        if socket_group not in user_groups:
            print(f"User not in docker group (socket group: {socket_group})")
            # Tente de corriger automatiquement les permissions
            try:
                subprocess.run(['sudo', 'chmod', '666', docker_socket], check=True)
                print("Fixed docker socket permissions")
            except:
                print("Failed to fix docker socket permissions")
                pass
        
        # Vérifie si le service Docker est actif
        service_check = subprocess.run(['systemctl', 'is-active', 'docker'], 
                                    capture_output=True, 
                                    text=True)
        
        # Tente d'exécuter docker avec sudo si nécessaire
        try:
            docker_check = subprocess.run(['docker', 'info'], 
                                        capture_output=True, 
                                        text=True)
            if docker_check.returncode != 0:
                docker_check = subprocess.run(['sudo', 'docker', 'info'], 
                                            capture_output=True, 
                                            text=True)
        except:
            print("Failed to run docker info")
            return False
            
        docker_supported = (
            service_check.returncode == 0 and  # Service actif
            docker_check.returncode == 0       # Docker fonctionne
        )
        
        print(f"Docker support check results:")
        print(f"- Service active: {service_check.returncode == 0}")
        print(f"- Docker working: {docker_check.returncode == 0}")
        print(f"Final result: {docker_supported}")
        
        return docker_supported
        
    except Exception as e:
        print(f"Error checking Docker support: {str(e)}")
        return False

@app.route('/api/check_interface/<interface>', methods=['POST'])
def check_interface(interface):
    result = check_monitor_support(interface)
    
    # Vérification explicite du support Docker
    docker_supported = check_docker_support()
    result['docker_support'] = docker_supported
    
    # Log pour le débogage
    print(f"Interface check result: {result}")
    print(f"Docker support: {docker_supported}")
    
    # Si Docker est supporté, on peut simuler les interfaces virtuelles
    if docker_supported:
        result['virtual_support'] = True
        result['virtual_method'] = 'docker'
    
    return jsonify(result)

@app.route('/api/save_config', methods=['POST'])
def save_interface_config():
    data = request.json
    config = {
        'wifi_interface': data['interface'],
        'monitor_supported': data['monitor_supported'],
        'virtual_support': data.get('virtual_support', False)
    }
    save_config(config)
    return jsonify({'status': 'success'})

@app.route('/api/logs')
def get_logs():
    try:
        logs = []
        
        # Récupérer les logs système (journalctl) pour nos scripts
        for script_id, script in SCRIPTS.items():
            script_name = os.path.basename(script['script'])
            try:
                # Récupère les 50 dernières lignes de log pour chaque script
                cmd = f"journalctl -n 50 -u {script_name} 2>/dev/null || true"
                output = subprocess.check_output(cmd, shell=True).decode('utf-8')
                if output:
                    logs.append({
                        'script': script['name'],
                        'type': 'system',
                        'content': output.split('\n')
                    })
            except:
                pass

        # Récupérer les logs spécifiques (captured_passwords.txt)
        if os.path.exists('captured_passwords.txt'):
            with open('captured_passwords.txt', 'r') as f:
                password_logs = f.readlines()
                if password_logs:
                    logs.append({
                        'script': 'Captures',
                        'type': 'passwords',
                        'content': password_logs
                    })

        # Récupérer les logs des fichiers .log dans le dossier logs
        for log_file in os.listdir(LOGS_DIR):
            if log_file.endswith('.log'):
                script_name = log_file.replace('.log', '')
                with open(os.path.join(LOGS_DIR, log_file), 'r') as f:
                    content = f.readlines()
                    if content:
                        logs.append({
                            'script': script_name,
                            'type': 'file',
                            'content': content
                        })

        return jsonify({'logs': logs})
    except Exception as e:
        return jsonify({'error': str(e), 'logs': []})

@app.route('/api/config')
def get_config():
    config = load_config()
    if config:
        return jsonify(config)
    return jsonify({'error': 'Configuration non trouvée'}), 404

# Fonction pour créer une interface virtuelle via Docker
def create_docker_interface(interface_name):
    try:
        # Crée un réseau Docker s'il n'existe pas
        subprocess.run([
            'docker', 'network', 'create',
            '--subnet', DOCKER_SUBNET,
            DOCKER_NETWORK
        ], check=True)
        
        # Crée un conteneur avec l'interface réseau
        container_name = f"virtual_interface_{interface_name}"
        subprocess.run([
            'docker', 'run', '-d',
            '--name', container_name,
            '--network', DOCKER_NETWORK,
            '--cap-add=NET_ADMIN',
            'alpine', 'sleep', 'infinity'
        ], check=True)
        
        return True
    except subprocess.CalledProcessError:
        return False

def load_virtual_interfaces():
    try:
        if os.path.exists(VIRTUAL_INTERFACES_FILE):
            with open(VIRTUAL_INTERFACES_FILE, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Error loading virtual interfaces: {e}")
        return []

def save_virtual_interfaces(interfaces):
    try:
        with open(VIRTUAL_INTERFACES_FILE, 'w') as f:
            json.dump(interfaces, f)
    except Exception as e:
        print(f"Error saving virtual interfaces: {e}")

@app.route('/api/create_virtual_interface', methods=['POST'])
def create_virtual_interface():
    data = request.json
    interface_name = data.get('name')
    
    if not interface_name:
        return jsonify({'error': 'Nom d\'interface requis'}), 400
        
    try:
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docker_interface.sh')
        
        if not os.path.exists(script_path):
            return jsonify({'error': 'Script docker_interface.sh non trouvé'}), 500
            
        os.chmod(script_path, 0o755)
        
        result = subprocess.run([script_path, 'create', interface_name], 
                              capture_output=True, text=True, check=True)
        
        if result.returncode == 0:
            scripts = load_scripts()
            scripts_html = render_template(
                'scripts_grid.html',
                scripts=scripts,
                interface_name=interface_name
            )
            
            return jsonify({
                'success': True,
                'message': result.stdout,
                'html': scripts_html,
                'scripts': scripts  # Ajouter les scripts dans la réponse
            })
        else:
            return jsonify({
                'error': 'Création incomplète',
                'details': result.stdout + result.stderr
            }), 500
            
    except Exception as e:
        print(f"Script failed with error:\n{e.stderr}")
        return jsonify({
            'error': 'Erreur lors de la création de l\'interface',
            'details': e.stderr
        }), 500
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return jsonify({
            'error': f'Erreur inattendue: {str(e)}'
        }), 500

@app.route('/api/delete_virtual_interface', methods=['POST'])
def delete_virtual_interface():
    data = request.json
    interface_name = data.get('name')
    
    if not interface_name:
        return jsonify({'error': 'Nom d\'interface requis'}), 400
        
    try:
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docker_interface.sh')
        
        if not os.path.exists(script_path):
            return jsonify({'error': 'Script docker_interface.sh non trouvé'}), 500
            
        result = subprocess.run(
            [script_path, 'delete', interface_name],
            check=True,
            capture_output=True,
            text=True
        )
        
        # Supprimer l'interface de la liste sauvegardée
        interfaces = load_virtual_interfaces()
        if interface_name in interfaces:
            interfaces.remove(interface_name)
            save_virtual_interfaces(interfaces)
        
        return jsonify({
            'status': 'success',
            'message': f'Interface {interface_name} supprimée'
        })
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': f'Erreur: {str(e)}'}), 500

def get_virtual_interfaces():
    """Récupère la liste des interfaces Docker existantes"""
    try:
        # Récupérer tous les conteneurs qui commencent par virtual_interface_
        cmd = ["docker", "ps", "-a", "--filter", "name=virtual_interface_", "--format", "{{.Names}}"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Extraire les noms des interfaces (enlever le préfixe virtual_interface_)
        interfaces = []
        for container in result.stdout.strip().split('\n'):
            if container:  # Ignorer les lignes vides
                interface_name = container.replace('virtual_interface_', '')
                # Vérifier si le conteneur est en cours d'exécution
                check_status = subprocess.run(
                    ["docker", "inspect", "-f", "{{.State.Running}}", container],
                    capture_output=True, text=True
                )
                if check_status.stdout.strip() == 'true':
                    interfaces.append(interface_name)
        
        print(f"Interfaces Docker trouvées: {interfaces}")  # Debug log
        return interfaces
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors de la récupération des interfaces virtuelles: {e}")
        return []

def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False)

def run_websocket():
    async def start_websocket():
        async with websockets.serve(websocket_handler, "localhost", 8765):
            await asyncio.Future()  # run forever

    asyncio.run(start_websocket())

def load_scripts():
    """Charge la configuration des scripts"""
    return {
        'fake_wifi': {
            'name': 'Point d\'Accès Malveillant',
            'script': './fake_wifi.sh',
            'icon': 'wifi',
            'description': 'Crée un point d\'accès Wi-Fi piège pour capturer les mots de passe',
            'status': 'stopped',
            'requires_monitor': True,
            'requires_sudo': True
        },
        'wifi_sniffer': {
            'name': 'Analyseur Wi-Fi',
            'script': './wifi_sniffer.sh',
            'icon': 'magnifying-glass',
            'description': 'Capture et analyse le trafic Wi-Fi en temps réel',
            'status': 'stopped',
            'requires_monitor': True,
            'requires_sudo': True
        },
        'network_analyzer': {
            'name': 'Analyseur Réseau Complet',
            'script': './network_analyzer.sh',
            'icon': 'network-wired',
            'description': 'Capture tout le trafic réseau, y compris les paquets HTTP',
            'status': 'stopped',
            'requires_monitor': False,
            'requires_sudo': True
        },
        'mac_changer': {
            'name': 'Changeur MAC',
            'script': './mac_changer.sh',
            'icon': 'random',
            'description': 'Change aléatoirement l\'adresse MAC de l\'interface',
            'status': 'stopped',
            'requires_monitor': False,
            'requires_sudo': True
        },
        'wifi_jammer': {
            'name': 'Brouilleur Wi-Fi',
            'script': './wifi_jammer.sh',
            'icon': 'signal',
            'description': 'Scanne les réseaux Wi-Fi et lance une attaque de désauthentification',
            'status': 'stopped',
            'requires_monitor': True,
            'requires_sudo': True
        },
        'handshake_capture': {
            'name': 'Capture Handshake',
            'script': './handshake_capture.sh',
            'icon': 'key',
            'description': 'Capture les handshakes WPA2/WPA3 pour analyse',
            'status': 'stopped',
            'requires_monitor': True,
            'requires_sudo': True
        }
    }

@app.route('/api/get_scripts_html')
def get_scripts_html():
    interface_name = request.args.get('interface')
    scripts = load_scripts()
    return render_template('scripts_grid.html', 
                         scripts=scripts, 
                         interface_name=interface_name)

if __name__ == '__main__':
    # Démarrage du serveur Flask dans un thread séparé
    flask_thread = Thread(target=run_flask)
    flask_thread.start()

    # Démarrage du serveur WebSocket dans le thread principal
    try:
        run_websocket()
    except KeyboardInterrupt:
        print("\nServeur arrêté")