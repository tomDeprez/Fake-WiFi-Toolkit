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
        const terminal = document.querySelector(`#terminal-${data.script}`);
        if (!terminal) return;

        const line = document.createElement('div');
        line.className = data.type || 'output';
        line.textContent = data.message;
        terminal.appendChild(line);
        terminal.scrollTop = terminal.scrollHeight;

        if (data.type === 'password_prompt') {
            const inputContainer = document.querySelector(`#input-${data.script}`);
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
                const scriptId = e.target.closest('.card').dataset.script;
                const action = e.target.dataset.action;
                
                if (action === 'start') {
                    this.sendCommand('start', scriptId);
                    e.target.innerHTML = '<i class="fas fa-stop"></i> Arrêter';
                    e.target.dataset.action = 'stop';
                } else {
                    this.sendCommand('stop', scriptId);
                    e.target.innerHTML = '<i class="fas fa-play"></i> Démarrer';
                    e.target.dataset.action = 'start';
                }
            });
        });

        document.querySelectorAll('.terminal-input input').forEach(input => {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    const scriptId = e.target.closest('.card').dataset.script;
                    this.sendCommand('password', scriptId, e.target.value);
                    e.target.value = '';
                    e.target.closest('.terminal-input').style.display = 'none';
                }
            });
        });
    }

    sendCommand(command, scriptId, input = null) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const message = {
                command,
                script: scriptId
            };
            if (input !== null) {
                message.input = input;
            }
            this.ws.send(JSON.stringify(message));
        }
    }
}

// Attendre que le DOM soit complètement chargé
window.addEventListener('load', () => {
    console.log('DOM chargé, initialisation du ScriptManager');
    new ScriptManager();
});