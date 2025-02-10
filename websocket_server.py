import asyncio
import websockets
import json
import subprocess
import os
import signal
from datetime import datetime

# Dictionnaire pour stocker les processus en cours
running_processes = {}

async def log_message(websocket, message, type="info"):
    await websocket.send(json.dumps({
        "type": type,
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "message": message
    }))

async def handle_script(websocket, script_path):
    try:
        process = await asyncio.create_subprocess_exec(
            'sudo', script_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE
        )
        
        running_processes[script_path] = process

        while True:
            line = await process.stdout.readline()
            if not line:
                break
            
            message = line.decode().strip()
            await log_message(websocket, message)
            
            # Si une entrée utilisateur est requise
            if "Voulez-vous continuer" in message or "(o/N)" in message:
                await log_message(websocket, "input_required", "prompt")
                response = await websocket.recv()
                process.stdin.write(f"{response}\n".encode())
                await process.stdin.drain()

        await process.wait()
        del running_processes[script_path]
        
    except Exception as e:
        await log_message(websocket, f"Erreur: {str(e)}", "error")

async def handle_connection(websocket, path):
    try:
        async for message in websocket:
            data = json.loads(message)
            command = data.get("command")
            script = data.get("script")
            
            if command == "start":
                if script in running_processes:
                    await log_message(websocket, f"Le script {script} est déjà en cours d'exécution", "warning")
                else:
                    await handle_script(websocket, script)
            
            elif command == "stop":
                if script in running_processes:
                    process = running_processes[script]
                    process.terminate()
                    await log_message(websocket, f"Script {script} arrêté", "info")
                
            elif command == "input":
                user_input = data.get("input", "")
                if script in running_processes:
                    process = running_processes[script]
                    process.stdin.write(f"{user_input}\n".encode())
                    await process.stdin.drain()
                    
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        await log_message(websocket, f"Erreur: {str(e)}", "error")

async def main():
    server = await websockets.serve(handle_connection, "localhost", 8765)
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main()) 