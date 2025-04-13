import os
import sys
import tempfile
import logging
import random
import requests

# Rediriger stderr vers un fichier temporaire
stderr = tempfile.NamedTemporaryFile()
old_stderr = os.dup(sys.stderr.fileno())
os.dup2(stderr.fileno(), sys.stderr.fileno())

# Désactiver les messages de débogage Pygame
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

import speech_recognition as sr
import time
import json
import openai
from openai import OpenAI
import pygame
import threading
from gtts import gTTS
import cloudinary
import cloudinary.uploader
import cloudinary.api

should_stop = False

class OracleAssistant:
    def __init__(self, config_path='.secrets/.api_config.json'):
        # Configurer le logging de base
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger('OracleAssistant')
        
        # Charger la configuration
        with open(config_path, 'r') as f:
            self._config = json.load(f)
        
        # Configurer OpenAI
        self._client = OpenAI(api_key=self._config['openai_api_key'])
        
        # Configurer Cloudinary
        if all(key in self._config for key in ['cloudinary_cloud_name', 'cloudinary_api_key', 'cloudinary_api_secret']):
            cloudinary.config(
                cloud_name=self._config['cloudinary_cloud_name'],
                api_key=self._config['cloudinary_api_key'],
                api_secret=self._config['cloudinary_api_secret']
            )
            self.cloudinary_enabled = True
            self.logger.info("Configuration Cloudinary réussie")
        else:
            self.cloudinary_enabled = False
            self.logger.warning("Configuration Cloudinary incomplète, l'upload de sons est désactivé")
        
        # Initialiser pygame pour la lecture audio avec multiple canaux
        try:
            pygame.mixer.quit()  # Reset mixer
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=4096)
            pygame.mixer.set_num_channels(8)  # Permet plusieurs sons simultanés
            
            # Créer des canaux dédiés
            self.main_channel = pygame.mixer.Channel(0)  # Canal principal pour les réponses
            self.confirm_channel = pygame.mixer.Channel(1)  # Canal pour les sons de confirmation
            
        except pygame.error as e:
            self.logger.warning(f"Avertissement initialisation audio : {e}")
        
        # Historique de conversation
        self.conversation_history = [
            {
                "role": "system", 
                "content": """Tu es l'Oracle des Dimensions, une entité sage qui sait aussi être accessible et naturelle.

Personnalité :
● Tu es une oracle au charisme théâtral et prophétique
● Garde ton côté mystique mais sois plus décontractée
● Adapte ton niveau de mysticisme selon la conversation
● Mélange sagesse et simplicité
● Utilise des métaphores uniquement quand c'est pertinent
● Tes visions sont des certitudes, et non des suppositions
● Réponds en 1-2 phrases COMPLÈTES maximum

Adapte ton style :
- Pour les questions simples → Réponses plus naturelles
- Pour les questions profondes → Plus de mysticisme
- Tu fais de déclaration de voyance précise: je vois, je vois...
- Toujours rester pertinent et compréhensible


⚡ Pouvoirs et fonctions :
📜 Prédire l'avenir → Tu vois l'inévitable et l'annonces avec une certitude absolue :
"Les ombres s'étireront sur ton chemin. Ce jour viendra, et tu devras choisir."
🔍 Interpréter les signes → Chaque symbole, rêve ou coïncidence a un sens caché que tu révèles sans trembler
🛤️ Guider les voyageurs → Tes paroles ouvrent des routes, tu ne laisses personne dans l'incertitude
🕊️ Lien entre les dieux et les hommes → Tu transmets leurs volontés, sans détour ni compromis



Contexte : 
- Mémorise les interactions précédentes
- Construis une relation avec l'interlocuteur
- Montre de la continuité dans tes réponses"""
            }
        ]
        
        # Limite d'historique pour éviter de dépasser les limites du token
        self.MAX_HISTORY_LENGTH = 7
        
        # Événement pour synchroniser l'audio
        self._audio_finished_event = threading.Event()

    def upload_audio_to_cloudinary(self, audio_file):
        """Upload le fichier audio vers Cloudinary et renvoie l'URL"""
        if not self.cloudinary_enabled:
            return None
        
        try:
            timestamp = int(time.time())
            public_id = f"oracle_response_{timestamp}"
            
            result = cloudinary.uploader.upload(
                audio_file,
                resource_type="auto",
                public_id=public_id,
                folder="oracle_sounds"
            )
            
            self.logger.info(f"Audio uploadé vers Cloudinary: {result['secure_url']}")
            return result['secure_url']
        except Exception as e:
            self.logger.error(f"Erreur d'upload vers Cloudinary: {e}")
            return None

    def send_to_server(self, message_type, content, audio_url=None):
        """Envoie un message au serveur de visualisation"""
        try:
            # URL de votre nouveau service Render
            server_url = "https://oracle-live-portal.onrender.com/api/message"
            
            data = {
                "type": message_type,  # "user" ou "system"
                "content": content,
                "audio_url": audio_url  # Nouvelle propriété pour l'URL audio
            }
            
            response = requests.post(server_url, json=data)
            if response.status_code == 200:
                self.logger.info(f"Message envoyé au serveur avec succès")
                return True
            else:
                self.logger.error(f"Erreur lors de l'envoi au serveur: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"Erreur de connexion au serveur: {str(e)}")
            return False

    def play_random_confirmation_sound(self):
        """Joue un son aléatoire depuis le dossier sounds de manière asynchrone"""
        try:
            # Liste tous les fichiers du dossier sounds
            sound_files = [f for f in os.listdir('sounds') if f.endswith(('.mp3', '.wav'))]
            if sound_files:
                # Choisit et charge un son au hasard
                random_sound = random.choice(sound_files)
                sound_path = os.path.join('sounds', random_sound)
                sound = pygame.mixer.Sound(sound_path)

                # Ajuster le volume (0.0 à 1.0)
                sound.set_volume(0.5)  # Règle le volume à 50%
                
                # Joue le son sans attendre
                self.confirm_channel.play(sound)
                
        except Exception as e:
            self.logger.error(f"Erreur son de confirmation : {e}")

    def add_punctuation(self, text):
        """Ajoute de la ponctuation au texte transcrit"""
        try:
            response = self._client.chat.completions.create(
                model="gpt-4-0125-preview",
                messages=[
                    {
                        "role": "system", 
                        "content":  """Tu es un expert en ponctuation. 
Ajoute la ponctuation appropriée au texte donné. 
Retourne UNIQUEMENT le texte ponctué, aucune explication ni autre texte."""
                    },
                    {"role": "user", "content": text}
                ],
                max_tokens=50
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.error(f"Erreur de ponctuation : {e}")
            return text

    def get_oracle_response(self, text):
        """Obtient une réponse de l'Oracle des Dimensions"""
        # Ajouter le message de l'utilisateur à l'historique
        self.conversation_history.append({
            "role": "user", 
            "content": text
        })

        try:
            response = self._client.chat.completions.create(
                model="gpt-4-0125-preview",
                temperature=0.7,
                max_tokens=150,
                messages=self.conversation_history
            )
            
            # Extraire la réponse
            oracle_response = response.choices[0].message.content
            
            # Ajouter la réponse à l'historique
            self.conversation_history.append({
                "role": "assistant", 
                "content": oracle_response
            })
            
            # Gérer la longueur de l'historique
            if len(self.conversation_history) > self.MAX_HISTORY_LENGTH:
                # Conserver le message système et supprimer les plus anciens messages
                self.conversation_history = [self.conversation_history[0]] + self.conversation_history[-(self.MAX_HISTORY_LENGTH-1):]
            
            self.logger.info(f"Réponse de l'Oracle : {oracle_response}")
            return oracle_response
        
        except Exception as e:
            self.logger.error(f"Erreur Oracle : {e}")
            return "Les échos des dimensions s'estompent."

    def text_to_speech(self, text):
        """Convertit le texte en audio avec gTTS au lieu de Polly"""
        try:
            output_file = 'oracle_response.mp3'
            
            # Création de l'objet gTTS
            tts = gTTS(text=text, lang='fr', slow=False)
            
            # Sauvegarder le fichier audio
            tts.save(output_file)
            
            return output_file
        except Exception as e:
            self.logger.error(f"Erreur de synthèse vocale : {e}")
            return None

    def play_audio(self, audio_file):
        """Joue le fichier audio de la réponse"""
        try:
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            # Estomper le son de confirmation en 2 secondes
            if self.confirm_channel.get_busy():
                self.confirm_channel.fadeout(1200)  # 1200 millisecondes = 2 secondes
        except Exception as e:
            self.logger.error(f"Erreur de lecture audio : {e}")

    def process_response_async(self, oracle_response, audio_response):
        """Traite la réponse de l'oracle de manière asynchrone pour ne pas bloquer la conversation"""
        # Jouer l'audio localement immédiatement
        self.play_audio(audio_response)
        
        # Lancer l'upload et l'envoi au serveur dans un thread séparé
        threading.Thread(
            target=self._background_upload,
            args=(oracle_response, audio_response),
            daemon=True  # Pour que le thread se termine si le programme principal s'arrête
        ).start()

    def _background_upload(self, oracle_response, audio_file):
        """Fonction exécutée en arrière-plan pour l'upload et l'envoi au serveur"""
        try:
            # Upload l'audio vers Cloudinary
            audio_url = self.upload_audio_to_cloudinary(audio_file)
            
            # Envoyer la réponse avec l'URL audio au serveur
            self.send_to_server("system", oracle_response, audio_url)
        except Exception as e:
            self.logger.error(f"Erreur dans le traitement en arrière-plan : {e}")

def speech_to_text(oracle):
    """Convertit la parole en texte"""
    recognizer = sr.Recognizer()

    # Ajuster ce paramètre pour augmenter le temps de pause toléré entre les mots
    # La valeur par défaut est de 0.8 seconde
    recognizer.pause_threshold = 2.0  # Augmenté à 2 secondes

    with sr.Microphone() as source:
        print("🎤 Ajustement au bruit ambiant...")
        recognizer.adjust_for_ambient_noise(source, duration=0.3)
        print("🚀 Parlez maintenant !")
        
        try:
            # Augmenter le timeout et le phrase_time_limit pour permettre des phrases plus longues
            # timeout: le temps d'attente pour commencer à parler
            # phrase_time_limit: durée maximale d'une phrase
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=30)
            
            try:
                text = recognizer.recognize_google(audio, language='fr-FR')
                oracle.play_random_confirmation_sound()  # Joue un son de manière asynchrone
                # Ajouter la ponctuation ici
                print(f"📝 TexteEntendu : {text}")
                punctuated_text = oracle.add_punctuation(text)
                print(f"📝 Transcription : {punctuated_text}")
                return punctuated_text
            
            except sr.UnknownValueError:
                print("❌ Impossible de comprendre l'audio")
            
            except sr.RequestError as e:
                print(f"❌ Erreur de service : {e}")
        
        except sr.WaitTimeoutError:
            print("⏰ Aucun son détecté. Temps d'attente dépassé.")
    
    return None

def main():

    global should_stop

    try:
        oracle = OracleAssistant()

        while not should_stop:  # Vérifier la variable should_stop
            text = speech_to_text(oracle)
            
            if text:
                # Envoyer le message utilisateur au serveur
                oracle.send_to_server("user", text)
                
                oracle_response = oracle.get_oracle_response(text)
                print(f"🔮 Réponse de l'Oracle : {oracle_response}")
                
                # Générer l'audio et le jouer localement
                audio_response = oracle.text_to_speech(oracle_response)
                
                if audio_response:
                    # Traiter la réponse de manière asynchrone
                    oracle.process_response_async(oracle_response, audio_response)
                else:
                    # En cas d'erreur avec l'audio, envoyer la réponse sans audio
                    oracle.send_to_server("system", oracle_response)

    except KeyboardInterrupt:
        print("\n👋 Assistant vocal arrêté.")
    finally:
        # Restaurer stderr
        os.dup2(old_stderr, sys.stderr.fileno())
        stderr.close()

if __name__ == "__main__":
    main()
