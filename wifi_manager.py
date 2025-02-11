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
    }
}

CONFIG_FILE = 'config.json'

# Constante pour le dossier des logs
LOGS_DIR = "logs"
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# Gestion des processus et des WebSockets
class ScriptProcess:
    def __init__(self, script_id, websocket):
        self.script_id = script_id
        self.websocket = websocket
        self.process = None
        self.output_buffer = []
        self.status = 'stopped'

    async def start(self, sudo_password):
        if not os.path.exists(SCRIPTS[self.script_id]['script']):
            await self.send_message('error', f"Script introuvable: {self.script_id}")
            return False

        try:
            # Rendre le script exécutable
            script_path = os.path.abspath(SCRIPTS[self.script_id]['script'])
            os.chmod(script_path, 0o755)

            # Démarrage du script avec pexpect
            cmd = f"sudo -S bash {script_path}"
            self.process = pexpect.spawn(cmd, encoding='utf-8', timeout=10)
            
            # Gestion plus robuste du prompt sudo
            patterns = [
                '[Pp]assword.*:', 
                '[Mm]ot de passe.*:',
                pexpect.EOF,
                pexpect.TIMEOUT
            ]
            
            index = self.process.expect(patterns)
            
            if index in [0, 1]:  # Si on trouve un prompt de mot de passe
                self.process.sendline(sudo_password)
                await self.send_message('info', "Mot de passe envoyé, démarrage du script...")
            elif index == 2:  # EOF
                await self.send_message('error', "Le script s'est terminé prématurément")
                return False
            elif index == 3:  # TIMEOUT
                await self.send_message('error', "Timeout lors de l'attente du prompt sudo")
                return False

            # Mise à jour du statut
            self.status = 'running'
            SCRIPTS[self.script_id]['status'] = 'running'
            
            # Démarrage de la lecture de sortie
            asyncio.create_task(self.read_output())
            return True

        except Exception as e:
            await self.send_message('error', f"Erreur de démarrage: {str(e)}")
            if self.process:
                self.process.close()
            return False

    async def stop(self):
        if self.process and self.process.isalive():
            self.process.terminate()
            self.process.close()
            self.status = 'stopped'
            SCRIPTS[self.script_id]['status'] = 'stopped'
            await self.send_message('info', "Script arrêté")

    async def read_output(self):
        while self.process and self.process.isalive():
            try:
                # Lecture de la sortie avec timeout
                index = self.process.expect(['.+', pexpect.TIMEOUT, pexpect.EOF], timeout=1)
                
                if index == 0:  # Nouvelle sortie disponible
                    line = self.process.match.group(0).strip()
                    if line:
                        # Détection du type de message
                        msg_type = 'output'
                        if '[❌]' in line:
                            msg_type = 'error'
                        elif '[✅]' in line:
                            msg_type = 'success'
                        elif '[ℹ️]' in line:
                            msg_type = 'info'
                        elif '[⚠️]' in line:
                            msg_type = 'warning'
                        
                        await self.send_message(msg_type, line)
                
            except Exception as e:
                await self.send_message('error', f"Erreur de lecture: {str(e)}")
                break

        # Nettoyage final
        if self.status != 'stopped':
            self.status = 'stopped'
            SCRIPTS[self.script_id]['status'] = 'stopped'
            await self.send_message('info', "Script terminé")

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

    async def send_message(self, type, message):
        try:
            await self.websocket.send(json.dumps({
                'script': self.script_id,
                'type': type,
                'message': message
            }))
        except:
            pass

# Gestionnaire de connexion WebSocket
async def websocket_handler(websocket):
    processes = {}
    
    try:
        async for message in websocket:
            data = json.loads(message)
            script_id = data.get('script')
            command = data.get('command')
            
            if not script_id or script_id not in SCRIPTS:
                continue

            if command == 'start':
                if script_id not in processes:
                    await websocket.send(json.dumps({
                        'script': script_id,
                        'type': 'password_prompt',
                        'message': 'Veuillez entrer le mot de passe sudo'
                    }))
                
            elif command == 'password':
                process = ScriptProcess(script_id, websocket)
                if await process.start(data.get('input')):
                    processes[script_id] = process
                
            elif command == 'stop':
                if script_id in processes:
                    await processes[script_id].stop()
                    del processes[script_id]

    except websockets.exceptions.ConnectionClosed:
        for process in processes.values():
            await process.stop()
    except Exception as e:
        print(f"Erreur WebSocket: {e}")

# Routes Flask
@app.route('/')
def index():
    config = load_config()
    if not config:
        return redirect(url_for('setup'))
    return render_template('index.html', scripts=SCRIPTS, ws_port=8765, config=config)

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

@app.route('/api/check_interface/<interface>', methods=['POST'])
def check_interface(interface):
    result = check_monitor_support(interface)
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

def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False)

def run_websocket():
    async def start_websocket():
        async with websockets.serve(websocket_handler, "localhost", 8765):
            await asyncio.Future()  # run forever

    asyncio.run(start_websocket())

if __name__ == '__main__':
    # Démarrage du serveur Flask dans un thread séparé
    flask_thread = Thread(target=run_flask)
    flask_thread.start()

    # Démarrage du serveur WebSocket dans le thread principal
    try:
        run_websocket()
    except KeyboardInterrupt:
        print("\nServeur arrêté")