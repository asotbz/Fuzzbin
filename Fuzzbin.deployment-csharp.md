# Fuzzbin C# - Single Container Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the C# version of Fuzzbin as a single, self-contained Docker container optimized for self-hosting scenarios.

## Table of Contents
1. [Quick Start](#quick-start)
2. [Deployment Options](#deployment-options)
3. [Configuration](#configuration)
4. [Production Deployment](#production-deployment)
5. [Monitoring & Maintenance](#monitoring--maintenance)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites
- Docker 20.10+ or Podman 4.0+
- 1GB free RAM
- 10GB free disk space
- Linux, Windows, or macOS

### 1-Minute Deployment

```bash
# Pull and run the container (no API keys needed!)
docker run -d \
  --name fuzzbin \
  -p 8080:8080 \
  -v fuzzbin_data:/data \
  -v fuzzbin_media:/media \
  ghcr.io/yourusername/fuzzbin:latest

# Access the application
# First run: http://localhost:8080/setup (complete setup wizard)
# After setup: http://localhost:8080
```

### Docker Compose Deployment

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  fuzzbin:
    image: ghcr.io/yourusername/fuzzbin:latest
    container_name: fuzzbin
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ./data:/data     # SQLite database and application data
      - ./media:/media   # Video storage
    # No environment variables needed - all config stored in database!
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:8080/health"]
      interval: 30s
      timeout: 3s
      retries: 3
      start_period: 10s
```

Deploy (no .env file needed):

```bash
docker-compose up -d
```

---

## Deployment Options

### Option 1: Docker (Recommended)

#### Building from Source

```bash
# Clone repository
git clone https://github.com/yourusername/fuzzbin-csharp.git
cd fuzzbin-csharp

# Build Docker image
docker build -t fuzzbin:latest .

# Run container (no environment variables!)
docker run -d \
  --name fuzzbin \
  -p 8080:8080 \
  -v $(pwd)/data:/data \
  -v $(pwd)/media:/media \
  fuzzbin:latest

# On first run, navigate to http://localhost:8080/setup
```

#### Using Pre-built Image

```bash
# Pull latest image
docker pull ghcr.io/yourusername/fuzzbin:latest

# Run with persistent data
docker run -d \
  --name fuzzbin \
  -p 8080:8080 \
  -v $(pwd)/data:/data \
  -v $(pwd)/media:/media \
  ghcr.io/yourusername/fuzzbin:latest
```

### Option 2: Standalone Executable

#### Linux Deployment

```bash
# Download release
wget https://github.com/yourusername/fuzzbin/releases/latest/download/fuzzbin-linux-x64.tar.gz
tar -xzf fuzzbin-linux-x64.tar.gz

# Make executable
chmod +x Fuzzbin

# Create directories
mkdir -p data media config

# Run application
./Fuzzbin --urls=http://0.0.0.0:8080
```

#### Windows Deployment

```powershell
# Download release
Invoke-WebRequest -Uri "https://github.com/yourusername/fuzzbin/releases/latest/download/fuzzbin-win-x64.zip" -OutFile "fuzzbin.zip"
Expand-Archive -Path "fuzzbin.zip" -DestinationPath "."

# Create directories
New-Item -ItemType Directory -Path "data", "media", "config"

# Run application
.\Fuzzbin.exe --urls=http://0.0.0.0:8080
```

#### macOS Deployment

```bash
# Download release
curl -L https://github.com/yourusername/fuzzbin/releases/latest/download/fuzzbin-osx-x64.tar.gz -o fuzzbin.tar.gz
tar -xzf fuzzbin.tar.gz

# Make executable
chmod +x Fuzzbin

# Create directories
mkdir -p data media config

# Run application
./Fuzzbin --urls=http://0.0.0.0:8080
```

### Option 3: Systemd Service (Linux)

Create `/etc/systemd/system/fuzzbin.service`:

```ini
[Unit]
Description=Fuzzbin Music Video Management
After=network.target

[Service]
Type=simple
User=fuzzbin
Group=fuzzbin
WorkingDirectory=/opt/fuzzbin
ExecStart=/opt/fuzzbin/Fuzzbin
Restart=always
RestartSec=10
KillSignal=SIGINT
SyslogIdentifier=fuzzbin
Environment="ASPNETCORE_ENVIRONMENT=Production"
Environment="ASPNETCORE_URLS=http://0.0.0.0:8080"

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/fuzzbin/data /opt/fuzzbin/media

[Install]
WantedBy=multi-user.target
```

Install and start:

```bash
# Create user
sudo useradd -r -s /bin/false fuzzbin

# Create directories
sudo mkdir -p /opt/fuzzbin/{data,media,config}
sudo chown -R fuzzbin:fuzzbin /opt/fuzzbin

# Copy application
sudo cp -r ./publish/* /opt/fuzzbin/

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable fuzzbin
sudo systemctl start fuzzbin

# Check status
sudo systemctl status fuzzbin
```

### Option 4: Windows Service

```powershell
# Install as Windows Service
sc.exe create Fuzzbin binPath="C:\Fuzzbin\Fuzzbin.exe" start=auto

# Configure service
sc.exe config Fuzzbin DisplayName="Fuzzbin" 
sc.exe description Fuzzbin "Music Video Management System"

# Start service
sc.exe start Fuzzbin
```

### Option 5: Kubernetes Deployment

Create `fuzzbin-k8s.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: fuzzbin
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: fuzzbin-data
  namespace: fuzzbin
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: fuzzbin-media
  namespace: fuzzbin
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Gi
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: fuzzbin-config
  namespace: fuzzbin
data:
  appsettings.Production.json: |
    {
      "Storage": {
        "MediaPath": "/media",
        "DataPath": "/data"
      }
    }
---
apiVersion: v1
kind: Secret
metadata:
  name: fuzzbin-secrets
  namespace: fuzzbin
type: Opaque
stringData:
  imvdb-api-key: "your-imvdb-api-key"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fuzzbin
  namespace: fuzzbin
spec:
  replicas: 1
  selector:
    matchLabels:
      app: fuzzbin
  template:
    metadata:
      labels:
        app: fuzzbin
    spec:
      containers:
      - name: fuzzbin
        image: ghcr.io/yourusername/fuzzbin:latest
        ports:
        - containerPort: 8080
        env:
        - name: ASPNETCORE_ENVIRONMENT
          value: "Production"
        - name: ApiKeys__ImvdbApiKey
          valueFrom:
            secretKeyRef:
              name: fuzzbin-secrets
              key: imvdb-api-key
        volumeMounts:
        - name: data
          mountPath: /data
        - name: media
          mountPath: /media
        - name: config
          mountPath: /app/appsettings.Production.json
          subPath: appsettings.Production.json
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 10
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: fuzzbin-data
      - name: media
        persistentVolumeClaim:
          claimName: fuzzbin-media
      - name: config
        configMap:
          name: fuzzbin-config
---
apiVersion: v1
kind: Service
metadata:
  name: fuzzbin
  namespace: fuzzbin
spec:
  selector:
    app: fuzzbin
  ports:
  - port: 80
    targetPort: 8080
  type: LoadBalancer
```

Deploy:

```bash
kubectl apply -f fuzzbin-k8s.yaml
kubectl get pods -n fuzzbin
kubectl get svc -n fuzzbin
```

---

## Configuration

### Database-Driven Configuration

Fuzzbin stores all configuration in the SQLite database. On first run, you'll be prompted to complete a setup wizard at `/setup` that will:

1. Create an admin account
2. Configure storage paths
3. Optionally set API keys (can be added later)
4. Initialize the system

After initial setup, all configuration can be managed through the Settings page in the web UI (admin only).

### First-Run Setup

When you first access Fuzzbin, you'll see the setup wizard:

```bash
# 1. Start the container
docker run -d \
  --name fuzzbin \
  -p 8080:8080 \
  -v fuzzbin_data:/data \
  -v fuzzbin_media:/media \
  ghcr.io/yourusername/fuzzbin:latest

# 2. Open browser to http://localhost:8080
# 3. Complete the setup wizard:
#    - Enter admin email and password
#    - Configure storage paths (or use defaults)
#    - Optionally add API keys
#    - Click "Complete Setup"

# 4. System is ready to use!
```

### Configuration Management

All settings are managed through the web UI after initial setup:

- **Settings Page** (`/settings` - admin only):
  - API Keys (IMVDb) - encrypted in database
  - Storage configuration
  - Download preferences
  - Security settings
  - User management
  - System features

### Minimal appsettings.json

Only needed for overriding default behaviors:

```json
{
  "ConnectionStrings": {
    "DefaultConnection": "Data Source=/data/fuzzbin.db"
  },
  "DataProtection": {
    "KeysPath": "/data/keys"
  },
  "Logging": {
    "LogLevel": {
      "Default": "Information"
    }
  }
}
```

---

## Production Deployment

### Reverse Proxy Setup

#### Nginx Configuration

```nginx
server {
    listen 80;
    server_name fuzzbin.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name fuzzbin.example.com;

    ssl_certificate /etc/ssl/certs/fuzzbin.crt;
    ssl_certificate_key /etc/ssl/private/fuzzbin.key;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    location / {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache_bypass $http_upgrade;
        
        # WebSocket support for SignalR
        proxy_read_timeout 86400;
    }

    # Static files
    location /media {
        alias /var/fuzzbin/media;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}

map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}
```

#### Traefik Configuration

```yaml
# docker-compose with Traefik
version: '3.8'

services:
  traefik:
    image: traefik:v2.10
    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.myresolver.acme.tlschallenge=true"
      - "--certificatesresolvers.myresolver.acme.email=admin@example.com"
      - "--certificatesresolvers.myresolver.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./letsencrypt:/letsencrypt

  fuzzbin:
    image: ghcr.io/yourusername/fuzzbin:latest
    container_name: fuzzbin
    restart: unless-stopped
    volumes:
      - ./data:/data
      - ./media:/media
    # Configuration stored in database - no environment variables needed
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.fuzzbin.rule=Host(`fuzzbin.example.com`)"
      - "traefik.http.routers.fuzzbin.entrypoints=websecure"
      - "traefik.http.routers.fuzzbin.tls.certresolver=myresolver"
      - "traefik.http.services.fuzzbin.loadbalancer.server.port=8080"
```

### SSL/TLS Setup

#### Let's Encrypt with Certbot

```bash
# Install certbot
sudo apt-get update
sudo apt-get install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d fuzzbin.example.com

# Auto-renewal
sudo certbot renew --dry-run
```

#### Self-Signed Certificate

```bash
# Generate self-signed certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout fuzzbin.key \
  -out fuzzbin.crt \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=fuzzbin.local"

# Configure in appsettings
{
  "Kestrel": {
    "Endpoints": {
      "Https": {
        "Url": "https://+:8443",
        "Certificate": {
          "Path": "/config/fuzzbin.crt",
          "KeyPath": "/config/fuzzbin.key"
        }
      }
    }
  }
}
```

### Database Backup

#### Automated Backup Script

```bash
#!/bin/bash
# backup-fuzzbin.sh

BACKUP_DIR="/backups/fuzzbin"
DATA_DIR="/var/fuzzbin/data"
MEDIA_DIR="/var/fuzzbin/media"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup database
docker exec fuzzbin sqlite3 /data/fuzzbin.db ".backup /data/backup.db"
docker cp fuzzbin:/data/backup.db "$BACKUP_DIR/db_$DATE.db"

# Backup configuration
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" -C /var/fuzzbin config/

# Optional: Backup media (large!)
# tar -czf "$BACKUP_DIR/media_$DATE.tar.gz" -C /var/fuzzbin media/

# Keep only last 7 days
find "$BACKUP_DIR" -type f -mtime +7 -delete

echo "Backup completed: $DATE"
```

#### Cron Schedule

```bash
# Add to crontab
0 2 * * * /usr/local/bin/backup-fuzzbin.sh >> /var/log/fuzzbin-backup.log 2>&1
```

### Monitoring Setup

#### Health Check Endpoint

The application provides a health check endpoint at `/health`:

```json
{
  "status": "Healthy",
  "totalDuration": "00:00:00.0123456",
  "entries": {
    "database": {
      "status": "Healthy",
      "duration": "00:00:00.0012345"
    },
    "storage": {
      "status": "Healthy",
      "duration": "00:00:00.0001234",
      "data": {
        "freeSpaceGB": 450.2,
        "usedSpaceGB": 49.8
      }
    }
  }
}
```

#### Prometheus Metrics

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'fuzzbin'
    static_configs:
      - targets: ['fuzzbin:8080']
    metrics_path: '/metrics'
```

#### Grafana Dashboard

Import the Fuzzbin dashboard with ID: `VJ-001` or create custom:

```json
{
  "dashboard": {
    "title": "Fuzzbin Monitoring",
    "panels": [
      {
        "title": "Active Downloads",
        "targets": [
          {
            "expr": "fuzzbin_downloads_active"
          }
        ]
      },
      {
        "title": "Queue Size",
        "targets": [
          {
            "expr": "fuzzbin_queue_size"
          }
        ]
      },
      {
        "title": "Storage Usage",
        "targets": [
          {
            "expr": "fuzzbin_storage_used_bytes / 1073741824"
          }
        ]
      }
    ]
  }
}
```

---

## Monitoring & Maintenance

### Log Management

#### View Logs

```bash
# Docker logs
docker logs -f fuzzbin

# Last 100 lines
docker logs --tail 100 fuzzbin

# Since timestamp
docker logs --since 2024-01-01T00:00:00 fuzzbin
```

#### Log Rotation

```json
// appsettings.json
{
  "Serilog": {
    "WriteTo": [
      {
        "Name": "File",
        "Args": {
          "path": "/data/logs/fuzzbin-.log",
          "rollingInterval": "Day",
          "retainedFileCountLimit": 7,
          "fileSizeLimitBytes": 10485760,
          "rollOnFileSizeLimit": true
        }
      }
    ]
  }
}
```

### Performance Tuning

#### Memory Optimization

```bash
# Limit container memory
docker run -d \
  --name fuzzbin \
  --memory="512m" \
  --memory-swap="1g" \
  --cpus="1.0" \
  fuzzbin:latest
```

#### Application Settings

```json
{
  "Performance": {
    "MaxConcurrentRequests": 100,
    "RequestQueueLimit": 1000,
    "EnableResponseCompression": true,
    "EnableResponseCaching": true,
    "CacheDurationSeconds": 300
  }
}
```

### Update Process

#### Docker Update

```bash
# Pull new image
docker pull ghcr.io/yourusername/fuzzbin:latest

# Stop current container
docker stop fuzzbin

# Backup data
docker run --rm -v fuzzbin_data:/data -v $(pwd):/backup alpine tar czf /backup/backup.tar.gz /data

# Remove old container
docker rm fuzzbin

# Start new container
docker run -d \
  --name fuzzbin \
  -p 8080:8080 \
  -v fuzzbin_data:/data \
  -v fuzzbin_media:/media \
  ghcr.io/yourusername/fuzzbin:latest
```

#### Zero-Downtime Update

```bash
# Using Docker Compose
docker-compose pull
docker-compose up -d --no-deps --build fuzzbin
```

---

## Troubleshooting

### Common Issues

#### Container Won't Start

```bash
# Check logs
docker logs fuzzbin

# Check container status
docker inspect fuzzbin

# Verify volumes
docker volume ls
docker volume inspect fuzzbin_data

# Test with minimal config
docker run --rm -it ghcr.io/yourusername/fuzzbin:latest
```

#### Database Issues

```bash
# Check database integrity
docker exec fuzzbin sqlite3 /data/fuzzbin.db "PRAGMA integrity_check"

# Repair database
docker exec fuzzbin sqlite3 /data/fuzzbin.db "VACUUM"

# Export and reimport
docker exec fuzzbin sqlite3 /data/fuzzbin.db ".dump" > backup.sql
docker exec -i fuzzbin sqlite3 /data/fuzzbin_new.db < backup.sql
```

#### Permission Issues

```bash
# Fix volume permissions
docker exec fuzzbin chown -R 1000:1000 /data /media

# Run with specific user
docker run -d \
  --user 1000:1000 \
  --name fuzzbin \
  fuzzbin:latest
```

#### Memory Issues

```bash
# Check memory usage
docker stats fuzzbin

# Increase memory limit
docker update --memory="1g" --memory-swap="2g" fuzzbin

# Check for memory leaks
docker exec fuzzbin dotnet-dump collect -p 1
docker exec fuzzbin dotnet-dump analyze core_file
```

### Debug Mode

```bash
# Run in debug mode
docker run -it \
  --rm \
  -e ASPNETCORE_ENVIRONMENT=Development \
  -e Logging__LogLevel__Default=Debug \
  -p 8080:8080 \
  fuzzbin:latest
```

### Health Check Failed

```bash
# Manual health check
curl http://localhost:8080/health

# Check with verbose output
curl -v http://localhost:8080/health

# Check from inside container
docker exec fuzzbin wget -O- http://localhost:8080/health
```

### Reset Application

```bash
# Complete reset (WARNING: Deletes all data)
docker stop fuzzbin
docker rm fuzzbin
docker volume rm fuzzbin_data fuzzbin_media
docker run -d \
  --name fuzzbin \
  -p 8080:8080 \
  -v fuzzbin_data:/data \
  -v fuzzbin_media:/media \
  fuzzbin:latest
```

---

## Security Best Practices

### Container Security

```yaml
# Secure docker-compose.yml
version: '3.8'

services:
  fuzzbin:
    image: ghcr.io/yourusername/fuzzbin:latest
    container_name: fuzzbin
    restart: unless-stopped
    user: "1000:1000"
    read_only: true
    tmpfs:
      - /tmp
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - SETUID
      - SETGID
    ports:
      - "127.0.0.1:8080:8080"
    volumes:
      - ./data:/data:rw
      - ./media:/media:rw
      - ./config:/config:ro
    environment:
      - ASPNETCORE_ENVIRONMENT=Production
```

### Network Security

```bash
# Create isolated network
docker network create --driver bridge fuzzbin-net

# Run with custom network
docker run -d \
  --name fuzzbin \
  --network fuzzbin-net \
  fuzzbin:latest
```

### Secrets Management

All secrets (API keys, JWT secret) are stored encrypted in the SQLite database using ASP.NET Core Data Protection API. No Docker secrets or environment variables needed for sensitive data.

To manage secrets:
1. Login as admin
2. Navigate to Settings
3. Update API keys or other sensitive configuration
4. Changes are encrypted and saved to database

The encryption keys are stored in `/data/keys` and should be backed up along with the database.

---

## Support

### Getting Help

1. Check the [Documentation](https://github.com/yourusername/fuzzbin/wiki)
2. Search [Issues](https://github.com/yourusername/fuzzbin/issues)
3. Join [Discord Community](https://discord.gg/fuzzbin)
4. Email: support@fuzzbin.app

### Reporting Issues

When reporting issues, include:
- Docker version: `docker --version`
- Container logs: `docker logs fuzzbin`
- Configuration (without secrets)
- Steps to reproduce

### Contributing

See [CONTRIBUTING.md](https://github.com/yourusername/fuzzbin/blob/main/CONTRIBUTING.md) for guidelines.

---

## Appendix

### Minimum System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 1 core | 2+ cores |
| RAM | 512MB | 1GB |
| Storage | 10GB | 100GB+ |
| Docker | 20.10 | Latest stable |
| Network | 10 Mbps | 100+ Mbps |

### Port Reference

| Port | Service | Description |
|------|---------|-------------|
| 8080 | HTTP | Web interface |
| 8443 | HTTPS | Secure web (optional) |

### Volume Reference

| Path | Purpose | Persistent |
|------|---------|------------|
| /data | Database, logs | Yes |
| /media | Video files | Yes |
| /config | Configuration | Yes |
| /tmp | Temporary files | No |

---

This deployment guide provides everything needed to successfully deploy and maintain Fuzzbin in production environments.