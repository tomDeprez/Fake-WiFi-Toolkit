from flask import Flask, render_template, jsonify, request, redirect, url_for
import subprocess
import os
import json
import netifaces
from pathlib import Path
from datetime import datetime

app = Flask(__name__)

# Configuration des scripts
SCRIPTS = {
    'fake_wifi': {
        'name': 'Faux Point d\'Accès',
        'script': './fake_wifi.sh',
        'icon': 'wifi',
        'description': 'Crée un point d\'accès Wi-Fi malveillant',
        'status': 'stopped'
    },
    'wifi_sniffer': {
        'name': 'Sniffer Wi-Fi',
        'script': './wifi_sniffer.sh',
        'icon': 'radar',
        'description': 'Capture le trafic Wi-Fi',
        'status': 'stopped'
    },
    'wifi_sniffer_all': {
        'name': 'Sniffer Complet',
        'script': './wifi_sniffer_all.sh',
        'icon': 'search',
        'description': 'Capture tout le trafic',
        'status': 'stopped'
    },
    'wifi_sniffer_cookie': {
        'name': 'Cookie Sniffer',
        'script': './wifi_sniffer_cookie.sh',
        'icon': 'cookie',
        'description': 'Capture les cookies',
        'status': 'stopped'
    },
    'mac_random': {
        'name': 'MAC Random',
        'script': './mac_random.sh',
        'icon': 'shuffle',
        'description': 'Change l\'adresse MAC aléatoirement',
        'status': 'stopped'
    }
}

CONFIG_FILE = 'config.json'

# Constante pour le dossier des logs
LOGS_DIR = "logs"
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

def get_network_interfaces():
    interfaces = []
    for iface in netifaces.interfaces():
        try:
            # Récupère les informations de l'interface
            addrs = netifaces.ifaddresses(iface)
            
            # Récupère l'adresse IP si disponible
            ip = addrs.get(netifaces.AF_INET, [{'addr': 'Non connecté'}])[0]['addr']
            
            # Récupère l'adresse MAC si disponible
            mac = addrs.get(netifaces.AF_LINK, [{'addr': 'N/A'}])[0]['addr']
            
            # Vérifie si c'est une interface wifi avec iwconfig
            try:
                wifi_info = subprocess.check_output(['iwconfig', iface], stderr=subprocess.DEVNULL).decode()
                is_wifi = 'no wireless extensions' not in wifi_info
                if is_wifi:
                    wifi_details = wifi_info.split('\n')[0]
                else:
                    wifi_details = None
            except:
                wifi_details = None
            
            # Ajoute l'interface à la liste
            interfaces.append({
                'name': iface,
                'ip': ip,
                'mac': mac,
                'is_wifi': bool(wifi_details),
                'info': wifi_details if wifi_details else f"IP: {ip}, MAC: {mac}"
            })
        except Exception as e:
            print(f"Erreur lors de la lecture de {iface}: {str(e)}")
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
        output = subprocess.check_output(['iw', interface, 'info'], stderr=subprocess.STDOUT).decode()
        supported_modes = subprocess.check_output(['iwconfig', interface], stderr=subprocess.STDOUT).decode()
        monitor_support = 'monitor' in output.lower() or 'monitor' in supported_modes.lower()
        return {
            'supported': monitor_support,
            'current_mode': 'monitor' if 'type monitor' in output else 'managed'
        }
    except:
        return {'supported': False, 'current_mode': 'unknown'}

@app.route('/')
def index():
    config = load_config()
    if not config:
        return redirect(url_for('setup'))
    return render_template('index.html', scripts=SCRIPTS)

@app.route('/setup')
def setup():
    interfaces = get_network_interfaces()
    return render_template('setup.html', interfaces=interfaces)

@app.route('/api/check_interface/<interface>', methods=['POST'])
def check_interface(interface):
    result = check_monitor_support(interface)
    return jsonify(result)

@app.route('/api/save_config', methods=['POST'])
def save_interface_config():
    data = request.json
    config = {
        'wifi_interface': data['interface'],
        'monitor_supported': data['monitor_supported']
    }
    save_config(config)
    return jsonify({'status': 'success'})

@app.route('/api/start/<script_id>', methods=['POST'])
def start_script(script_id):
    if script_id in SCRIPTS:
        try:
            subprocess.Popen(['sudo', SCRIPTS[script_id]['script']], 
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
            SCRIPTS[script_id]['status'] = 'running'
            return jsonify({'status': 'success'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})
    return jsonify({'status': 'error', 'message': 'Script non trouvé'})

@app.route('/api/stop/<script_id>', methods=['POST'])
def stop_script(script_id):
    if script_id in SCRIPTS:
        try:
            subprocess.run(['sudo', 'pkill', '-f', SCRIPTS[script_id]['script']])
            SCRIPTS[script_id]['status'] = 'stopped'
            return jsonify({'status': 'success'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})
    return jsonify({'status': 'error', 'message': 'Script non trouvé'})

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 