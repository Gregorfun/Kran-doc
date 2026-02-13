# Kran-Doc Installation Guide

**Version:** 2.0  
**Letzte Aktualisierung:** 16. Januar 2026

---

## 📋 Übersicht

Dieser Guide führt durch die Installation von Kran-Doc für verschiedene Deployment-Szenarien:

1. **Lokale Entwicklung** (Windows/Linux/Mac)
2. **Docker Compose** (Empfohlen für Produktion)
3. **VPS/Server Deployment** (Netcup, Hetzner, etc.)
4. **Offline-Installation** (Werkstatt/Baustelle)

---

## 🔧 System-Anforderungen

### Minimum

- **CPU:** 2 Cores
- **RAM:** 4 GB
- **Storage:** 10 GB freier Speicher
- **OS:** Windows 10+, Ubuntu 20.04+, macOS 12+

### Empfohlen

- **CPU:** 4+ Cores
- **RAM:** 8 GB (16 GB für große Datenmengen)
- **Storage:** 50 GB SSD
- **GPU:** Optional (für schnelleres OCR/ML)

### Software-Voraussetzungen

- **Python:** 3.8 - 3.11 (Python 3.11 empfohlen)
- **Docker:** 20.10+ (für Container-Deployment)
- **Git:** Aktuellste Version

---

## 🚀 Installation

### Option 1: Lokale Installation (Windows)

#### 1.1 Repository klonen

```powershell
git clone https://github.com/Gregorfun/Kran-doc.git
cd Kran-doc\kran-tools
```

#### 1.2 Virtuelle Umgebung erstellen

```powershell
python -m venv venv
venv\Scripts\activate
```

#### 1.3 Dependencies installieren

**Vollständige Installation (alle Features):**
```powershell
pip install -r requirements-full.txt
```

**Minimale Installation (begrenzte Ressourcen):**
```powershell
pip install -r requirements-minimal.txt
```

#### 1.4 Tesseract OCR installieren

1. Download: [Tesseract OCR Windows Installer](https://github.com/UB-Mannheim/tesseract/wiki)
2. Installieren nach `C:\Program Files\Tesseract-OCR`
3. Pfad zu PATH hinzufügen oder in `config/config.yaml` setzen

#### 1.5 Konfiguration

```powershell
# .env-Datei erstellen
Copy-Item .env.example .env

# .env anpassen
notepad .env
```

Wichtige Einstellungen:
```ini
FLASK_SECRET_KEY=dein-geheimer-schlüssel-hier
QDRANT_HOST=localhost
QDRANT_PORT=6333
OCR_ENGINE=paddle
EMBEDDING_MODEL=paraphrase-multilingual-mpnet-base-v2
```

#### 1.6 Qdrant starten (lokal)

**Option A: Docker**
```powershell
docker run -d -p 6333:6333 -v ${PWD}/data/qdrant:/qdrant/storage qdrant/qdrant
```

**Option B: Lokal (ohne Docker)**
```powershell
# Wird automatisch im Datei-Modus verwendet
# Speichert in ./data/qdrant
```

#### 1.7 Datenbank initialisieren

```powershell
python scripts/qdrant_manager.py
```

#### 1.8 Anwendung starten

```powershell
python webapp/app.py
```

Öffne Browser: `http://localhost:5000`

---

### Option 2: Lokale Installation (Linux/Mac)

#### 2.1 Repository klonen

```bash
git clone https://github.com/Gregorfun/Kran-doc.git
cd Kran-doc/kran-tools
```

#### 2.2 System-Dependencies installieren

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y \
    python3.11 python3.11-venv python3-pip \
    tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng \
    poppler-utils ghostscript \
    libgl1-mesa-glx libglib2.0-0
```

**macOS (Homebrew):**
```bash
brew install python@3.11 tesseract tesseract-lang poppler
```

#### 2.3 Virtuelle Umgebung erstellen

```bash
python3.11 -m venv venv
source venv/bin/activate
```

#### 2.4 Dependencies installieren

```bash
# Vollständig
pip install -r requirements-full.txt

# Oder minimal
pip install -r requirements-minimal.txt
```

#### 2.5 Konfiguration

```bash
cp .env.example .env
nano .env  # oder vim, etc.
```

#### 2.6 Qdrant starten

```bash
# Docker
docker run -d -p 6333:6333 \
    -v $(pwd)/data/qdrant:/qdrant/storage \
    qdrant/qdrant

# Oder lokaler Modus (keine Docker nötig)
```

#### 2.7 Datenbank initialisieren

```bash
python scripts/qdrant_manager.py
```

#### 2.8 Anwendung starten

```bash
python webapp/app.py
```

---

### Option 3: Docker Compose (Empfohlen)

#### 3.1 Repository klonen

```bash
git clone https://github.com/Gregorfun/Kran-doc.git
cd Kran-doc/kran-tools
```

#### 3.2 Umgebungsvariablen setzen

```bash
cp .env.example .env
nano .env
```

Wichtige Variablen:
```ini
FLASK_SECRET_KEY=production-secret-key-very-secure
QDRANT_HOST=qdrant
QDRANT_PORT=6333
LOG_LEVEL=INFO
```

#### 3.3 Docker Compose starten

**Basis-Stack (App + Qdrant):**
```bash
docker-compose -f docker-compose.production.yml up -d
```

**Mit Monitoring (Grafana + Prometheus):**
```bash
docker-compose -f docker-compose.production.yml --profile monitoring up -d
```

#### 3.4 Logs prüfen

```bash
docker-compose -f docker-compose.production.yml logs -f kran-doc
```

#### 3.5 Services verwalten

```bash
# Stoppen
docker-compose -f docker-compose.production.yml down

# Neu starten
docker-compose -f docker-compose.production.yml restart kran-doc

# Status
docker-compose -f docker-compose.production.yml ps
```

---

### Option 4: VPS/Server Deployment (z.B. Netcup)

#### 4.1 Server-Setup (Ubuntu 22.04)

```bash
# Als root
apt-get update && apt-get upgrade -y

# Docker installieren
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Docker Compose installieren
apt-get install -y docker-compose-plugin

# Firewall konfigurieren
ufw allow 22/tcp     # SSH
ufw allow 80/tcp     # HTTP
ufw allow 443/tcp    # HTTPS
ufw enable
```

#### 4.2 Application User erstellen

```bash
adduser krandoc
usermod -aG docker krandoc
su - krandoc
```

#### 4.3 Repository klonen

```bash
cd ~
git clone https://github.com/Gregorfun/Kran-doc.git
cd Kran-doc/kran-tools
```

#### 4.4 SSL-Zertifikat (Let's Encrypt)

```bash
# Certbot installieren
sudo apt-get install -y certbot

# Zertifikat anfordern
sudo certbot certonly --standalone -d dein-domain.de
```

#### 4.5 Nginx Reverse Proxy

```bash
sudo apt-get install -y nginx

# Konfiguration erstellen
sudo nano /etc/nginx/sites-available/kran-doc
```

Inhalt:
```nginx
server {
    listen 80;
    server_name dein-domain.de;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name dein-domain.de;

    ssl_certificate /etc/letsencrypt/live/dein-domain.de/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dein-domain.de/privkey.pem;

    location / {
        proxy_pass http://localhost:5002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Aktivieren:
```bash
sudo ln -s /etc/nginx/sites-available/kran-doc /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 4.6 Docker Stack starten

```bash
cd ~/Kran-doc/kran-tools

# .env konfigurieren
cp .env.example .env
nano .env

# Starten
docker-compose -f docker-compose.production.yml up -d
```

#### 4.7 Automatischer Start (Systemd)

```bash
sudo nano /etc/systemd/system/kran-doc.service
```

Inhalt:
```ini
[Unit]
Description=Kran-Doc Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/krandoc/Kran-doc/kran-tools
ExecStart=/usr/bin/docker-compose -f docker-compose.production.yml up -d
ExecStop=/usr/bin/docker-compose -f docker-compose.production.yml down
User=krandoc

[Install]
WantedBy=multi-user.target
```

Aktivieren:
```bash
sudo systemctl daemon-reload
sudo systemctl enable kran-doc
sudo systemctl start kran-doc
```

---

### Option 5: Offline-Installation (Werkstatt/Baustelle)

Für Umgebungen ohne Internet-Zugang.

#### 5.1 Vorbereitung (mit Internet)

```bash
# Alle Dependencies herunterladen
pip download -r requirements-minimal.txt -d packages/

# Docker Images speichern
docker save qdrant/qdrant:latest -o qdrant.tar
docker save python:3.11-slim -o python.tar

# ML-Modelle herunterladen
python scripts/download_models_offline.py
```

#### 5.2 Transfer zum Offline-System

```bash
# USB-Stick oder internes Netzwerk
# Kopiere:
# - Repository
# - packages/
# - *.tar Docker Images
# - models/
```

#### 5.3 Installation auf Offline-System

```bash
# Python-Packages installieren
pip install --no-index --find-links=packages/ -r requirements-minimal.txt

# Docker Images laden
docker load -i qdrant.tar
docker load -i python.tar

# Modelle kopieren
cp -r models/ ~/.cache/huggingface/
```

#### 5.4 Lokaler Modus (ohne Docker)

```bash
# Qdrant im Datei-Modus
export QDRANT_USE_LOCAL=true
export QDRANT_PATH=./data/qdrant

# App starten
python webapp/app.py
```

---

## 🔍 Verifizierung

### 1. Health Check

```bash
curl http://localhost:5002/health
```

Erwartete Antwort:
```json
{
  "status": "healthy",
  "version": "2.0",
  "database": "connected"
}
```

### 2. Qdrant Status

```bash
curl http://localhost:6333/collections
```

### 3. Web-Interface

Öffne Browser: `http://localhost:5002`

Prüfe:
- ✅ Startseite lädt
- ✅ Such-Funktion verfügbar
- ✅ Upload-Formular sichtbar

---

## 🛠️ Troubleshooting

### Problem: "ImportError: No module named 'qdrant_client'"

**Lösung:**
```bash
pip install qdrant-client
```

### Problem: Qdrant verbindet nicht

**Lösung:**
```bash
# Prüfe ob Qdrant läuft
docker ps | grep qdrant

# Starte Qdrant neu
docker restart kran-doc-qdrant

# Logs prüfen
docker logs kran-doc-qdrant
```

### Problem: OCR funktioniert nicht

**Lösung:**
```bash
# Tesseract prüfen
tesseract --version

# Installation (Ubuntu)
sudo apt-get install tesseract-ocr tesseract-ocr-deu

# Windows: PATH prüfen
echo $env:PATH
```

### Problem: Out of Memory

**Lösung:**
```bash
# Kleineres Embedding-Modell verwenden
export EMBEDDING_MODEL=all-MiniLM-L6-v2

# Batch-Size reduzieren
export BATCH_SIZE=16

# Swap aktivieren (Linux)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## 📊 Performance-Optimierung

### 1. GPU-Acceleration (CUDA)

```bash
# CUDA-fähiges PyTorch installieren
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# PaddleOCR GPU-Version
pip install paddlepaddle-gpu

# Aktivieren
export OCR_USE_GPU=true
export EMBEDDING_DEVICE=cuda
```

### 2. Memory-Optimierung

```yaml
# config/config.yaml
performance:
  max_workers: 2
  batch_size: 16
  embedding_cache: true
  lazy_loading: true
```

### 3. Caching

```bash
# Redis für Caching (optional)
docker run -d -p 6379:6379 redis:7-alpine

# In .env
REDIS_HOST=localhost
REDIS_PORT=6379
ENABLE_CACHING=true
```

---

## 🔄 Updates

### Lokal

```bash
cd Kran-doc/kran-tools
git pull
pip install -r requirements-full.txt --upgrade
```

### Docker

```bash
cd Kran-doc/kran-tools
git pull
docker-compose -f docker-compose.production.yml build --no-cache
docker-compose -f docker-compose.production.yml up -d
```

---

## 📚 Nächste Schritte

Nach erfolgreicher Installation:

1. **[User Guide](USER_GUIDE.md)** - Erste Schritte
2. **[API Documentation](API.md)** - REST API nutzen
3. **[Developer Guide](DEVELOPMENT.md)** - Entwicklung & Beiträge

---

## 💬 Support

- **GitHub Issues:** https://github.com/Gregorfun/Kran-doc/issues
- **Dokumentation:** https://github.com/Gregorfun/Kran-doc/docs
- **E-Mail:** gregorfun@users.noreply.github.com

---

**Version:** 2.0  
**Letzte Aktualisierung:** 16. Januar 2026
