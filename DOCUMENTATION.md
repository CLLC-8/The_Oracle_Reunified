# Documentation technique

## Architecture du système

Le système Oracle Lidar est composé de plusieurs modules interconnectés:

```
           +---------------+
           |               |
           |  main.py      |
           | (Lidar & DMX) |
           |               |
           +-------+-------+
                   |
                   | Envoi de commandes
                   | (fichiers .cmd)
                   v
           +-------+-------+
           |               |
           |Convers_Server |
           | (Orchestration)|
           |               |
           +-------+-------+
                   |
                   | Appels de fonction
                   |
                   v
           +-------+-------+
           |               |
           |  CONVERS.py   |
           |(Module Oracle)|
           |               |
           +---------------+
                   |
                   | Utilise
                   |
                   v
           +-------+-------+
           |               |
           |CalcLidarData.py|
           | (Parsing UART) |
           |               |
           +---------------+
```

## Flux de données

1. **Acquisition des données Lidar**:
   - Le capteur Lidar envoie des données via UART
   - `main.py` utilise `CalcLidarData.py` pour interpréter les données
   - Les données sont visualisées en temps réel avec Matplotlib

2. **Détection de présence**:
   - Les points Lidar sont regroupés en clusters
   - La distance minimale est calculée
   - Les zones d'interaction sont déterminées en fonction de cette distance

3. **Contrôle DMX**:
   - Les intensités RGB et UV sont calculées en fonction de la distance
   - Les données DMX sont envoyées via OLA

4. **Interaction avec l'Oracle**:
   - Des commandes sont générées par `main.py` sous forme de fichiers JSON
   - `Convers_Server.py` surveille ces fichiers et déclenche les actions appropriées
   - `CONVERS.py` gère la reconnaissance vocale, l'IA et la synthèse vocale

## Description détaillée des modules

### main.py

Ce module est responsable de la détection Lidar et du contrôle DMX.

**Fonctions clés**:
- `cluster_points()`: Regroupe les points Lidar en clusters
- `send_dmx()`: Envoie les données DMX
- `send_oracle_command()`: Crée les fichiers de commande
- `get_zone()`: Détermine la zone d'interaction

**Variables importantes**:
- `ZONE_CONTACT_LIMIT`: Distance maximale pour la zone de contact
- `ZONE_APPROCHE_LIMIT`: Distance maximale pour la zone d'approche
- `corridor_width`: Largeur du corridor de détection

### CalcLidarData.py

Module utilitaire qui interprète les données brutes du Lidar.

**Classes**:
- `LidarData`: Structure de données pour stocker les informations du Lidar

**Fonctions**:
- `CalcLidarData()`: Analyse les chaînes hexadécimales du Lidar

### CONVERS.py

Module qui gère l'interface vocale avec GPT-4.

**Classes**:
- `OracleAssistant`: Gère la conversation, les appels API et la synthèse vocale

**Méthodes principales**:
- `get_oracle_response()`: Obtient une réponse de GPT-4
- `text_to_speech()`: Convertit le texte en audio
- `speech_to_text()`: Convertit l'audio en texte

### Convers_Server.py

Serveur d'orchestration qui gère le cycle de vie des conversations.

**Classes**:
- `OracleServer`: Gère le cycle de vie des conversations

**Méthodes principales**:
- `run_conversation()`: Boucle principale de conversation
- `start_conversation()`: Démarre une nouvelle conversation
- `stop_conversation()`: Arrête une conversation en cours

## Formats de communication

### Commandes Oracle

Les commandes sont stockées dans des fichiers JSON dans `/tmp/oracle_commands/`:

```json
{
  "command": "start|stop|engage|departure",
  "timestamp": 1713111889.123,
  "params": {}
}
```

### Données Lidar

Les données Lidar sont transmises via UART sous forme de chaînes hexadécimales avec ce format:
- 2 octets: Vitesse
- 2 octets: Angle de début (FSA)
- 12 paquets de données (72 octets)
- 2 octets: Angle de fin (LSA)
- 2 octets: Timestamp
- 1 octet: Checksum

Chaque paquet de données contient:
- 2 octets: Distance
- 1 octet: Confiance

## Personnalisation

### Prompt de l'Oracle

Le comportement de l'Oracle est défini par le prompt système dans `CONVERS.py`:

```python
"content": """Tu es l'Oracle des Dimensions, une entité sage qui sait aussi être accessible et naturelle.

Personnalité :
● Tu es une oracle au charisme théâtral et prophétique
● Garde ton côté mystique mais sois plus décontractée
...
"""
```

### Paramètres de détection

Les paramètres suivants peuvent être ajustés dans `main.py`:

```python
MIN_CONFIDENCE = 10
MIN_POINTS_CLUSTER = 3
BASE_DISTANCE_THRESHOLD = 0.5
MIN_VALID_DISTANCE = 0.5
```

## Optimisation et performances

### Traitement Lidar

Le système utilise un algorithme de clustering adaptatif:
- Plages de distance avec paramètres adaptés
- Facteur d'adaptation basé sur la distance
- Utilisation de l'angle ou de la distance euclidienne selon la proximité

### Gestion de la mémoire

- Limitation de l'historique de conversation à 7 messages
- Stockage des sons en local avant upload

## Dépannage avancé

### Problèmes Lidar

Si les données Lidar sont incohérentes:
1. Vérifiez le brochage UART
2. Utilisez `stty -F /dev/ttyAMA0 230400` pour confirmer la vitesse
3. Surveillez les données brutes: `cat /dev/ttyAMA0 | hexdump -C`

### Problèmes audio

Si la reconnaissance vocale échoue:
1. Vérifiez le périphérique audio avec `arecord -l`
2. Testez l'enregistrement: `arecord -d 5 test.wav`
3. Ajustez les niveaux: `alsamixer`

### Problèmes DMX

Si l'éclairage DMX ne répond pas:
1. Vérifiez l'interface dans `ola_dev_info`
2. Testez avec `ola_set_dmx -u 1 -d 1,255,0,0,0,0,0,0`
3. Vérifiez l'adressage des fixtures
