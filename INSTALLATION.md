# Guide d'installation détaillé

Ce guide vous accompagne dans l'installation et la configuration complète du système Oracle Lidar.

## Configuration du Raspberry Pi

### 1. Installation du système d'exploitation
Nous recommandons d'utiliser Raspberry Pi OS (64-bit) pour de meilleures performances.

```bash
# Mettre à jour le système
sudo apt update
sudo apt upgrade -y
```

### 2. Configuration des interfaces
Activez l'interface UART:
1. Ouvrez la configuration
```bash
sudo raspi-config
```
2. Sélectionnez "Interface Options" > "Serial Port"
3. Désactivez le login shell sur le port série
4. Activez l'interface matérielle série
5. Redémarrez le Raspberry Pi

### 3. Configuration audio
```bash
# Installer les outils audio
sudo apt install -y pulseaudio alsa-utils

# Vérifier les périphériques audio
arecord -l
aplay -l

# Si nécessaire, définir la carte son par défaut en créant/modifiant ce fichier
sudo nano /etc/asound.conf
```
Contenu possible du fichier /etc/asound.conf:
```
pcm.!default {
  type hw
  card 1  # Remplacer par l'index de votre carte son
}

ctl.!default {
  type hw
  card 1  # Remplacer par l'index de votre carte son
}
```

## Installation des dépendances logicielles

### 1. Python et bibliothèques
```bash
# Installer pip si nécessaire
sudo apt install -y python3-pip

# Installer les dépendances système
sudo apt install -y python3-dev libatlas-base-dev portaudio19-dev libportaudio2 libasound2-dev

# Installer les packages Python requis
pip install -r requirements.txt
```

### 2. Configuration OLA (Open Lighting Architecture)
```bash
sudo apt-get install -y ola

# Activer le service OLA au démarrage
sudo systemctl enable olad
sudo systemctl start olad

# Vérifier le statut
sudo systemctl status olad
```

Configurez OLA via l'interface web disponible sur `http://localhost:9090` ou l'IP de votre Raspberry Pi sur le port 9090.

## Configuration du système Oracle

### 1. Création des répertoires nécessaires
```bash
# Créer les répertoires pour les commandes et statuts
sudo mkdir -p /tmp/oracle_commands
sudo mkdir -p /tmp/oracle_status
sudo chmod 777 /tmp/oracle_commands
sudo chmod 777 /tmp/oracle_status

# Créer les répertoires pour les phrases préenregistrées
mkdir -p ~/THE_ORACLE_REUNIFIED/phrases_engagement
mkdir -p ~/THE_ORACLE_REUNIFIED/phrases_bienvenue
mkdir -p ~/THE_ORACLE_REUNIFIED/phrases_aurevoir
```

### 2. Configuration de l'API OpenAI
Créez le répertoire et le fichier de configuration:
```bash
mkdir -p .secrets
touch .secrets/.api_config.json
nano .secrets/.api_config.json
```

Insérez le contenu suivant en remplaçant par vos propres informations:
```json
{
  "openai_api_key": "VOTRE_CLE_API_OPENAI",
  "cloudinary_cloud_name": "VOTRE_CLOUD_NAME",
  "cloudinary_api_key": "VOTRE_API_KEY",
  "cloudinary_api_secret": "VOTRE_API_SECRET"
}
```

### 3. Réglage des permissions
```bash
# Permissions pour le port série
sudo usermod -a -G dialout $USER
sudo chmod 666 /dev/ttyAMA0

# Permissions pour les fichiers Python
chmod +x main.py
chmod +x CONVERS.py
chmod +x Convers_Server.py
```

## Préparation des sons préenregistrés

### 1. Format des fichiers sons
1. Placez des fichiers MP3 dans les dossiers:
   - `~/THE_ORACLE_REUNIFIED/phrases_engagement/` (pour les sons d'engagement)
   - `~/THE_ORACLE_REUNIFIED/phrases_bienvenue/` (pour les sons de bienvenue)
   - `~/THE_ORACLE_REUNIFIED/phrases_aurevoir/` (pour les sons d'au revoir)

2. Nommez les fichiers selon ce format: `N_TEXTE.mp3` où:
   - N est un numéro d'ordre (1, 2, 3...)
   - TEXTE correspond au contenu vocal avec les caractères spéciaux remplacés par des codes:
     - Point: `_DOT_`
     - Virgule: `_COMMA_`
     - Espace: `_`
     - etc.

Exemple: `1_Bienvenue_COMMA__voyageur_DOT_.mp3` pour "Bienvenue, voyageur."

## Configuration du matériel

### 1. Branchement du Lidar
Le capteur Lidar doit être connecté aux broches UART du Raspberry Pi:
- Broche RX du Lidar → Broche TX du Raspberry Pi (pin 8)
- Broche TX du Lidar → Broche RX du Raspberry Pi (pin 10)
- GND du Lidar → GND du Raspberry Pi
- VCC du Lidar → 5V du Raspberry Pi (ou alimentation externe selon le modèle)

### 2. Configuration DMX
1. Connectez votre interface DMX USB
2. Dans l'interface web OLA (port 9090), configurez votre interface
3. Créez un univers DMX avec l'ID 1
4. Le programme utilise les canaux suivants:
   - Canal 1: Intensité RGB (0-255)
   - Canal 2: Toujours à 255
   - Canal 3: Toujours à 0
   - Canal 4: Toujours à 135
   - Canal 8: Intensité UV (0-255)
   - Canaux 12-15: Toujours à 255

## Lancer le système

### 1. Démarrage automatique (optionnel)
Pour démarrer les services au démarrage, créez des services systemd:

```bash
# Service pour le serveur de conversation
sudo nano /etc/systemd/system/oracle-server.service
```

Contenu:
```
[Unit]
Description=Oracle Conversation Server
After=network.target

[Service]
ExecStart=/usr/bin/python3 /chemin/vers/Convers_Server.py
WorkingDirectory=/chemin/vers/dossier
StandardOutput=inherit
StandardError=inherit
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

```bash
# Service pour la détection Lidar
sudo nano /etc/systemd/system/oracle-lidar.service
```

Contenu:
```
[Unit]
Description=Oracle Lidar Detection
After=network.target oracle-server.service
Requires=oracle-server.service

[Service]
ExecStart=/usr/bin/python3 /chemin/vers/main.py
WorkingDirectory=/chemin/vers/dossier
StandardOutput=inherit
StandardError=inherit
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

Activer les services:
```bash
sudo systemctl enable oracle-server.service
sudo systemctl enable oracle-lidar.service
sudo systemctl start oracle-server.service
sudo systemctl start oracle-lidar.service
```

### 2. Démarrage manuel
Dans deux terminaux distincts:

```bash
# Terminal 1
python Convers_Server.py

# Terminal 2
python main.py
```

## Vérification
- La visualisation Lidar devrait apparaître dans une fenêtre graphique
- Les sons devraient se déclencher quand une personne entre dans les zones définies
- L'éclairage DMX devrait réagir en fonction de la distance
