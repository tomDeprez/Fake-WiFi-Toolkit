class ScriptManager {
    constructor() {
        this.ws = null;
        this.wsPort = document.getElementById('ws-port')?.value || '8765';
        this.retryCount = 0;
        this.maxRetries = 5;
        this.connectWebSocket();
        this.setupEventListeners();
    }

    connectWebSocket() {
        try {
            console.log(`Tentative de connexion WebSocket sur le port ${this.wsPort}`);
            this.ws = new WebSocket(`ws://localhost:${this.wsPort}`);
            
            this.ws.onopen = () => {
                console.log('WebSocket connecté');
                this.retryCount = 0;
                this.updateStatus('connected');
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket déconnecté');
                this.updateStatus('disconnected');
                this.retryConnection();
            };
            
            this.ws.onerror = (error) => {
                console.error('Erreur WebSocket:', error);
                this.updateStatus('error');
                this.retryConnection();
            };
            
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            };
        } catch (error) {
            console.error('Erreur lors de la création du WebSocket:', error);
            this.retryConnection();
        }
    }

    updateStatus(status) {
        document.querySelectorAll('.script-action').forEach(button => {
            button.disabled = status !== 'connected';
        });
    }

    retryConnection() {
        if (this.retryCount < this.maxRetries) {
            this.retryCount++;
            console.log(`Tentative de reconnexion ${this.retryCount}/${this.maxRetries}`);
            setTimeout(() => this.connectWebSocket(), 2000);
        }
    }

    handleMessage(data) {
        const terminalId = data.interface ? 
            `terminal-${data.script}-${data.interface}` : 
            `terminal-${data.script}`;
            
        const terminal = document.querySelector(`#${terminalId}`);
        if (!terminal) {
            console.error(`Terminal non trouvé: ${terminalId}`);
            return;
        }

        const line = document.createElement('div');
        line.className = data.type || 'output';
        line.textContent = data.message;
        terminal.appendChild(line);
        terminal.scrollTop = terminal.scrollHeight;

        if (data.type === 'password_prompt') {
            const inputId = data.interface ? 
                `input-${data.script}-${data.interface}` : 
                `input-${data.script}`;
            const inputContainer = document.querySelector(`#${inputId}`);
            if (inputContainer) {
                inputContainer.style.display = 'block';
                const input = inputContainer.querySelector('input');
                input.focus();
            }
        }
    }

    setupEventListeners() {
        document.querySelectorAll('.script-action').forEach(button => {
            button.addEventListener('click', (e) => {
                const card = e.target.closest('.card');
                const scriptId = card.dataset.script;
                const interfaceName = card.dataset.interface;
                const action = e.target.dataset.action;
                
                console.log('Button clicked:', {
                    scriptId,
                    interfaceName,
                    action,
                    cardDataset: card.dataset,
                    cardHTML: card.outerHTML
                });
                
                if (action === 'start') {
                    this.sendCommand('start', scriptId, null, interfaceName);
                    e.target.innerHTML = '<i class="fas fa-stop"></i> Arrêter';
                    e.target.dataset.action = 'stop';
                } else {
                    this.sendCommand('stop', scriptId, null, interfaceName);
                    e.target.innerHTML = '<i class="fas fa-play"></i> Démarrer';
                    e.target.dataset.action = 'start';
                }
            });
        });

        document.querySelectorAll('.terminal-input input').forEach(input => {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    const card = e.target.closest('.card');
                    const scriptId = card.dataset.script;
                    const interfaceName = card.dataset.interface || null;
                    this.sendCommand('password', scriptId, e.target.value, interfaceName);
                    e.target.value = '';
                    e.target.closest('.terminal-input').style.display = 'none';
                }
            });
        });
    }

    sendCommand(command, scriptId, input = null, interfaceName = null) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            console.log('Card interface name:', interfaceName);
            console.log('Interface type:', typeof interfaceName);
            
            const cleanInterface = interfaceName && interfaceName.trim() !== '' ? interfaceName : null;
            
            const message = {
                command,
                script: scriptId,
                interface: cleanInterface,
                target: cleanInterface ? 'docker' : 'host'
            };
            
            if (input !== null) {
                message.input = input;
            }
            
            console.log('Final message:', message);
            console.log('Stringified message:', JSON.stringify(message));
            
            this.ws.send(JSON.stringify(message));
        }
    }
}

// Attendre que le DOM soit complètement chargé
window.addEventListener('load', () => {
    console.log('DOM chargé, initialisation du ScriptManager');
    new ScriptManager();
});