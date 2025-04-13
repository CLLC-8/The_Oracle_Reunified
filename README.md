# Oracle Lidar System

## Description
Le système Oracle Lidar est une installation interactive qui utilise un capteur Lidar pour détecter la présence humaine dans l'espace, déclencher des effets lumineux via DMX, et interagir avec les visiteurs par le biais d'une interface vocale pilotée par GPT-4.

## Fonctionnalités
- Détection de présence par Lidar avec visualisation en temps réel
- Interface vocale conversationnelle avec personnalité "Oracle des Dimensions"
- Contrôle d'éclairage DMX réagissant à la distance des visiteurs
- Définition de zones d'interaction (approche et contact)
- Synthèse vocale pour les réponses de l'Oracle

## Prérequis matériels
- Raspberry Pi (version 4 ou 5 recommandée)
- Capteur Lidar compatible (connecté via UART)
- Interface DMX USB (compatible OLA)
- Microphone USB
- Haut-parleurs
- Éclairages DMX RGB et UV

## Installation

### 1. Cloner le dépôt
```bash
git clone https://github.com/VOTRE_USERNAME/oracle-lidar-system.git
cd oracle-lidar-system
```

### 2. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 3. Configuration de l'API OpenAI
Créez un fichier `.secrets/.api_config.json` avec la structure suivante:
```json
{
  "openai_api_key": "VOTRE_CLE_API_OPENAI",
  "cloudinary_cloud_name": "VOTRE_CLOUD_NAME",
  "cloudinary_api_key": "VOTRE_API_KEY",
  "cloudinary_api_secret": "VOTRE_API_SECRET"
}
```

### 4. Configurer Open Lighting Architecture (OLA)
```bash
sudo apt-get install ola
sudo systemctl enable olad
sudo systemctl start olad
```

### 5. Créer les répertoires pour les phrases préenregistrées
```bash
mkdir -p /home/pi5/THE_ORACLE_REUNIFIED/phrases_engagement
mkdir -p /home/pi5/THE_ORACLE_REUNIFIED/phrases_bienvenue
mkdir -p /home/pi5/THE_ORACLE_REUNIFIED/phrases_aurevoir
```

### 6. Configurer les permissions UART
```bash
sudo usermod -a -G dialout $USER
sudo chmod 666 /dev/ttyAMA0
```

## Structure du projet
- `main.py` - Script principal pour la détection Lidar et l'envoi de commandes
- `CONVERS.py` - Module d'interface vocale avec GPT-4
- `Convers_Server.py` - Serveur d'orchestration des commandes et réponses
- `CalcLidarData.py` - Utilitaire de traitement des données Lidar

## Configuration

### Paramètres du Lidar (dans main.py)
```python
ZONE_CONTACT_LIMIT = 2.0      # Distance en mètres pour la zone de contact
ZONE_APPROCHE_LIMIT = 5.0     # Distance en mètres pour la zone d'approche
RGB_ZONE_MIN = 2.0            # Distance min pour l'éclairage RGB
RGB_ZONE_MAX = 5.0            # Distance max pour l'éclairage RGB
UV_ZONE_MIN = 1.0             # Distance min pour l'éclairage UV
UV_ZONE_MAX = 3.0             # Distance max pour l'éclairage UV
corridor_width = 3.00         # Largeur du corridor de détection
```

### Modèle GPT (dans CONVERS.py)
Le système utilise par défaut `gpt-4-0125-preview`. Vous pouvez modifier ce paramètre selon vos besoins.

## Exécution

### 1. Démarrer le serveur de conversation
```bash
python Convers_Server.py
```

### 2. Démarrer le système de détection Lidar
```bash
python main.py
```

## Commandes
Le système utilise des fichiers de commande dans le répertoire `/tmp/oracle_commands/` pour contrôler l'état de l'Oracle:
- `start` - Démarre une conversation 
- `stop` - Arrête une conversation en cours
- `engage` - Joue une phrase d'accueil
- `departure` - Joue une phrase d'au revoir

## Personnalisation de l'Oracle
La personnalité et le comportement de l'Oracle sont définis dans le système de prompt de CONVERS.py. Vous pouvez modifier le contenu du prompt pour ajuster le style de communication.

## Dépannage
- Si le Lidar n'est pas détecté, vérifiez les permissions du port série et l'accès à `/dev/ttyAMA0`
- Pour les problèmes liés à l'API OpenAI, vérifiez la validité de votre clé API
- Les erreurs DMX peuvent être dues à une mauvaise configuration d'OLA

## Licence
[Insérer votre type de licence ici]

## Contact
[Vos informations de contact]
