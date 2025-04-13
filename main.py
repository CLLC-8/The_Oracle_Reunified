import serial
import binascii
from CalcLidarData import CalcLidarData
import matplotlib.pyplot as plt
import math
import numpy as np
import array
from ola.ClientWrapper import ClientWrapper
import json
import time
import os

# === Configuration de la figure avec thème sombre ===
fig = plt.figure(figsize=(8, 8), facecolor='black')
ax = fig.add_subplot(111, projection='polar', facecolor='black')
ax.set_title('Lidar Scan', fontsize=18, color='white')

# Paramètres visuels pour contraste élevé
ax.set_theta_offset(math.pi)
ax.set_theta_direction(-1)
ax.tick_params(colors='white')
ax.xaxis.label.set_color('white')
ax.yaxis.label.set_color('white')
ax.grid(color='gray')

# Limiter l'affichage du graphique à 60 unités
ax.set_rlim(0, 60)

# === Paramètres de configuration ===
ZONE_CONTACT_LIMIT = 2.0      # m
ZONE_APPROCHE_LIMIT = 5.0     # m
RGB_ZONE_MIN = 2.0            # m
RGB_ZONE_MAX = 5.0            # m
UV_ZONE_MIN = 1.0             # m
UV_ZONE_MAX = 3.0             # m

last_zone_change_time = 0
zone_stability_duration = 0.5  # en secondes (par exemple 1 seconde avant de valider un changement)


# Paramètres du corridor
corridor_width = 3.00
max_distance = 60
y_coords = np.linspace(0, max_distance, 100)
x_left = np.ones_like(y_coords) * -corridor_width
x_right = np.ones_like(y_coords) * corridor_width
r_left = np.sqrt(x_left**2 + y_coords**2)
theta_left = np.arctan2(y_coords, x_left)
r_right = np.sqrt(x_right**2 + y_coords**2)
theta_right = np.arctan2(y_coords, x_right)
ax.plot(theta_left, r_left, 'r-', linewidth=2)
ax.plot(theta_right, r_right, 'r-', linewidth=2)

min_distance_text = fig.text(0.5, 0.05, "Distance minimale: -- m", fontsize=14, color='white', ha='center', va='center', bbox=dict(facecolor='black', alpha=0.7))
current_zone_text = fig.text(0.5, 0.01, "Zone actuelle: --", fontsize=14, color='white', ha='center', va='center', bbox=dict(facecolor='black', alpha=0.7))
rgb_text = fig.text(0.95, 0.85, "RGB : -- %", fontsize=12, color='red', ha='right', va='center')
uv_text = fig.text(0.95, 0.80, "UV  : -- %", fontsize=12, color='deepskyblue', ha='right', va='center')

plt.connect('key_press_event', lambda event: exit(1) if event.key == 'e' else None)

# === Initialisation du port série ===
ser = serial.Serial('/dev/ttyAMA0', 230400, timeout=5.0, bytesize=8, parity='N', stopbits=1)

# === Initialisation DMX ===
dmx_data = array.array('B', [0] * 16)
wrapper = ClientWrapper()
client = wrapper.Client()

def send_dmx(rgb_percent, uv_percent):
    rgb_dmx = int(rgb_percent * 255 / 100)
    uv_dmx = int(uv_percent * 255 / 100)
    dmx_data[0] = rgb_dmx
    dmx_data[1] = 255
    dmx_data[2] = 0
    dmx_data[3] = 135
    dmx_data[7] = uv_dmx
    dmx_data[11:15] = array.array('B', [255] * 4)
    client.SendDmx(1, dmx_data, lambda state: None)




# === Commande Oracle ===
def send_oracle_command(command, params=None):
    try:
        commands_dir = "/tmp/oracle_commands"
        os.makedirs(commands_dir, exist_ok=True)
        cmd_id = int(time.time() * 1000)
        cmd_file = os.path.join(commands_dir, f"cmd_{cmd_id}.cmd")
        cmd_data = {"command": command, "timestamp": time.time()}
        if params:
            cmd_data["params"] = params
        with open(cmd_file, 'w') as f:
            json.dump(cmd_data, f)
        os.system(f"chmod 666 {cmd_file}")
        print(f"[Oracle] Commande envoyée: {command}")
    except Exception as e:
        print(f"[Oracle] Erreur d'envoi: {e}")

# === Zone actuelle ===
# === Zone actuelle et séquence ===
current_zone = None
previous_zone = None
zone_sequence = []

def get_zone(distance):
    global current_zone, previous_zone, current_zone_text, last_zone_change_time, zone_sequence
    new_zone = None
    label = "--"

    if distance < ZONE_CONTACT_LIMIT:
        new_zone = 0
        label = "Zone contact"
    elif distance < ZONE_APPROCHE_LIMIT:
        new_zone = 1
        label = "Zone approche"
    else:
        new_zone = None
        label = "Hors zone"

    current_time = time.time()
    current_zone_text.set_text(f"Zone actuelle: {label}")

    if new_zone != current_zone:
        if current_time - last_zone_change_time >= zone_stability_duration:
            # Met à jour la séquence
            if new_zone is not None and (not zone_sequence or zone_sequence[-1] != new_zone):
                zone_sequence.append(new_zone)
            elif new_zone is None and (not zone_sequence or zone_sequence[-1] is not None):
                zone_sequence.append(None)

            # Ne garde que les 3 dernières zones
            if len(zone_sequence) > 3:
                zone_sequence = zone_sequence[-3:]

            # Déclenche la commande seulement si la séquence 0 → 1 → None est atteinte
            if zone_sequence == [0, 1, None]:
                send_oracle_command("departure")
                zone_sequence.clear()

            # Commandes habituelles
            if current_zone is None and new_zone == 1:
                send_oracle_command("engage")
            elif current_zone == 0 and new_zone != 0:
                send_oracle_command("stop")
            elif new_zone == 0:
                send_oracle_command("start")

            previous_zone = current_zone
            current_zone = new_zone
            last_zone_change_time = current_time
    else:
        last_zone_change_time = current_time



# === Variables ===
tmpString = ""
angles = []
distances = []
confidences = []
i = 0

# === Paramètres de détection améliorés ===
MIN_CONFIDENCE = 10  # Seuil minimal de confiance
MIN_POINTS_CLUSTER = 3  # Nombre minimal de points pour considérer un cluster
BASE_DISTANCE_THRESHOLD = 0.5  # Seuil de base pour le clustering (en unités)
MIN_VALID_DISTANCE = 0.5  # Distance minimale valide (5cm en unités)

# Fonction pour regrouper les points en clusters avec adaptation à la distance
def cluster_points(points, distance_ranges):
    all_clusters = []
    
    # Traiter chaque plage de distance séparément
    for dist_min, dist_max in distance_ranges:
        # Filtrer les points dans cette plage
        range_points = [(d, a, c) for d, a, c in points if dist_min <= d < dist_max]
        if not range_points:
            continue
            
        # Calculer le facteur d'adaptation pour cette plage
        distance_factor = max(1.0, (dist_min + dist_max) / 20)  # Moyenne de la plage divisée par 2m
        
        # Ajuster les paramètres en fonction de la distance
        distance_threshold = BASE_DISTANCE_THRESHOLD * distance_factor
        min_points = max(2, int(MIN_POINTS_CLUSTER / (distance_factor**0.5)))
        
        # Trier par angle pour mieux regrouper les points voisins
        sorted_points = sorted(range_points, key=lambda x: x[1])
        
        clusters = []
        current_cluster = []
        
        for dist, angle, conf in sorted_points:
            if not current_cluster:
                current_cluster.append((dist, angle, conf))
            else:
                # Vérifier si ce point est proche d'un point du cluster courant
                close_to_cluster = False
                
                for cluster_dist, cluster_angle, _ in current_cluster:
                    # Pour les points lointains, utiliser une approche basée sur l'angle
                    if dist > 20:  # Au-delà de 2m
                        # Calculer la différence d'angle (en tenant compte de la circularité)
                        angle_diff = abs(angle - cluster_angle)
                        angle_diff = min(angle_diff, 2*math.pi - angle_diff)
                        
                        # Convertir en distance d'arc à la distance actuelle
                        arc_distance = angle_diff * dist
                        
                        if arc_distance < distance_threshold * 2:  # Plus tolérant pour les points lointains
                            close_to_cluster = True
                            break
                    else:
                        # Pour les points proches, utiliser la distance euclidienne standard
                        dx = dist * math.cos(angle) - cluster_dist * math.cos(cluster_angle)
                        dy = dist * math.sin(angle) - cluster_dist * math.sin(cluster_angle)
                        distance_between_points = math.sqrt(dx*dx + dy*dy)
                        
                        if distance_between_points < distance_threshold:
                            close_to_cluster = True
                            break
                
                if close_to_cluster:
                    current_cluster.append((dist, angle, conf))
                else:
                    if len(current_cluster) >= min_points:
                        clusters.append(current_cluster)
                    current_cluster = [(dist, angle, conf)]
        
        # Ne pas oublier le dernier cluster
        if current_cluster and len(current_cluster) >= min_points:
            clusters.append(current_cluster)
        
        all_clusters.extend(clusters)
    
    return all_clusters

# === Boucle principale ===
while True:
    loopFlag = True
    flag2c = False
    if (i % 40 == 39):
        if 'line' in locals():
            line.remove()
        filtered_angles = []
        filtered_distances = []
        filtered_confidences = []
        for angle, distance, confidence in zip(angles, distances, confidences):
            angle_deg = (angle * 180 / math.pi) % 360
            if 0 <= angle_deg <= 180:
                distance_perpendiculaire = abs(distance * math.cos(angle))
                if (distance_perpendiculaire <= corridor_width and 
                    MIN_VALID_DISTANCE <= distance <= 60 and 
                    confidence >= MIN_CONFIDENCE):
                    filtered_angles.append(angle)
                    filtered_distances.append(distance)
                    filtered_confidences.append(confidence)
        
        # Visualiser les points filtrés
        line = ax.scatter(filtered_angles, filtered_distances, c='deepskyblue', s=5, alpha=0.8)
        
        # Analyser les clusters
        min_distance = float('inf')
        if filtered_distances:
            # Préparer les points pour le clustering
            points = list(zip(filtered_distances, filtered_angles, filtered_confidences))
            
            # Définir des plages de distance pour adapter l'algorithme
            distance_ranges = [(0.5, 10), (10, 20), (20, 30), (30, 60)]
            
            # Appliquer l'algorithme de clustering amélioré
            clusters = cluster_points(points, distance_ranges)
            
            if clusters:
                # Calculer la distance minimale de chaque cluster
                cluster_min_distances = []
                for cluster in clusters:
                    # Utiliser la moyenne des 3 points les plus proches pour plus de stabilité
                    cluster_distances = [point[0] for point in cluster]
                    cluster_distances.sort()  # Trier par distance croissante
                    n_points = min(3, len(cluster_distances))
                    avg_distance = sum(cluster_distances[:n_points]) / n_points
                    
                    if avg_distance >= MIN_VALID_DISTANCE:
                        cluster_min_distances.append(avg_distance)
                
                if cluster_min_distances:
                    min_distance = min(cluster_min_distances)
                    min_distance_meters = min_distance / 10
                    
                    # Affichage de la distance minimale
                    min_distance_text.set_text(f"Distance minimale: {min_distance_meters:.2f} m")
                    
                    # Calculer les pourcentages pour DMX
                    rgb_percent = max(0, min(100, (min_distance_meters - RGB_ZONE_MIN) / 
                                            (RGB_ZONE_MAX - RGB_ZONE_MIN) * 100))
                    uv_percent = max(0, min(100, (UV_ZONE_MAX - min_distance_meters) / 
                                          (UV_ZONE_MAX - UV_ZONE_MIN) * 100))
                    rgb_text.set_text(f"RGB : {int(rgb_percent)} %")
                    uv_text.set_text(f"UV  : {int(uv_percent)} %")

                    
                    # Envoyer les commandes DMX
                    send_dmx(rgb_percent, uv_percent)
                    
                    # Gérer les zones
                    get_zone(min_distance_meters)
                else:
                    min_distance_text.set_text("Aucune personne détectée (>5cm)")
                    send_dmx(100, 0)
            else:
                min_distance_text.set_text("Aucune personne détectée")
                get_zone(float('inf'))  # Met à jour la zone comme "hors zone"
                send_dmx(100, 0)
        else:
            min_distance_text.set_text("Aucune personne détectée")
            get_zone(float('inf'))  # Met à jour la zone comme "hors zone"
            send_dmx(100, 0)
        
        plt.pause(0.01)
        angles.clear()
        distances.clear()
        confidences.clear()
        i = 0
    
    while loopFlag:
        b = ser.read()
        tmpInt = int.from_bytes(b, 'big')
        if tmpInt == 0x54:
            tmpString += b.hex() + " "
            flag2c = True
            continue
        elif tmpInt == 0x2c and flag2c:
            tmpString += b.hex()
            if len(tmpString[0:-5].replace(' ', '')) != 90:
                tmpString = ""
                loopFlag = False
                flag2c = False
                continue
            lidarData = CalcLidarData(tmpString[0:-5])
            angles.extend(lidarData.Angle_i)
            distances.extend(lidarData.Distance_i)
            confidences.extend(lidarData.Confidence_i)
            tmpString = ""
            loopFlag = False
        else:
            tmpString += b.hex() + " "
        flag2c = False
    i += 1

ser.close()