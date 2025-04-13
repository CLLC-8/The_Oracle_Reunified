import os
import time
import json
import sys
import threading
import signal
import random
import logging

# === CONFIGURATION ===
COMMANDS_DIR = "/tmp/oracle_commands"
STATUS_DIR = "/tmp/oracle_status"
ENGAGEMENT_DIR = "/home/pi5/THE_ORACLE_REUNIFIED/phrases_engagement"
WELCOME_DIR = "/home/pi5/THE_ORACLE_REUNIFIED/phrases_bienvenue"
FAREWELL_DIR = "/home/pi5/THE_ORACLE_REUNIFIED/phrases_aurevoir"
ORACLE_MODULE_PATH = "/home/pi5/THE_ORACLE_UNIFIED"

# === LOGGING SETUP ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# === UTILITIES ===
def decode_filename(filename):
    if filename.endswith('.mp3'):
        filename = filename[:-4]
    if '_' in filename and filename.split('_')[0].isdigit():
        filename = filename[filename.index('_')+1:]

    special_codes = {
        "_DOT_": ".", "_COMMA_": ",", "_SEMICOLON_": ";", "_COLON_": ":",
        "_QUESTION_": "?", "_EXCLAMATION_": "!", "_APOSTROPHE_": "'", "_QUOTE_": '"',
        "_DASH_": "-", "_AT_": "@", "_AND_": "&", "_OPENPAR_": "(", "_CLOSEPAR_": ")",
        "_PERCENT_": "%", "_PLUS_": "+", "_EQUAL_": "=", "_SLASH_": "/",
        "_BACKSLASH_": "\\", "_STAR_": "*", "_TILDE_": "~", "_LESS_": "<",
        "_GREATER_": ">", "_OPENSQ_": "[", "_CLOSESQ_": "]", "_OPENCURL_": "{",
        "_CLOSECURL_": "}", "_PIPE_": "|", "_CARET_": "^", "_DOLLAR_": "$",
        "_HASH_": "#", "_BACKTICK_": "`"
    }

    for code, char in special_codes.items():
        filename = filename.replace(code, char)
    filename = filename.replace("_", " ")
    for p in ['.', ',', ';', ':', '!', '?']:
        filename = filename.replace(f" {p}", p)
    filename = filename.replace(" ' ", "'")
    return filename

def play_random_phrase(oracle, directory, tag="assistant"):
    files = [f for f in os.listdir(directory) if f.endswith(".mp3")]
    if not files:
        logging.warning(f"Aucun fichier trouvé dans {directory}")
        return
    random_file = random.choice(files)
    file_path = os.path.join(directory, random_file)
    decoded_text = decode_filename(random_file)
    oracle.process_response_async(decoded_text, file_path)
    oracle.conversation_history.append({"role": tag, "content": decoded_text})

# === ORACLE SERVER CLASS ===
class OracleServer:
    def __init__(self):
        self.conversation_thread = None
        self.should_stop = False

    def write_status(self, status):
        with open(os.path.join(STATUS_DIR, "status.json"), 'w') as f:
            json.dump({"status": status, "timestamp": time.time()}, f)

    def cleanup_on_startup(self):
        os.makedirs(COMMANDS_DIR, exist_ok=True)
        os.makedirs(STATUS_DIR, exist_ok=True)
        for cmd_file in os.listdir(COMMANDS_DIR):
            if cmd_file.endswith('.cmd'):
                os.remove(os.path.join(COMMANDS_DIR, cmd_file))
        self.write_status("idle")
        logging.info("Nettoyage au démarrage terminé")

    def run_conversation(self):
        self.should_stop = False
        sys.path.append(ORACLE_MODULE_PATH)
        import CONVERS

        try:
            oracle = CONVERS.OracleAssistant()
            oracle.send_to_server("info", "Un visiteur est entré en contact")
            play_random_phrase(oracle, ENGAGEMENT_DIR)

            while not self.should_stop:
                text = CONVERS.speech_to_text(oracle)
                if text:
                    oracle.send_to_server("user", text)
                    response = oracle.get_oracle_response(text)
                    logging.info(f"🔮 Réponse de l'Oracle : {response}")
                    audio_path = oracle.text_to_speech(response)
                    if audio_path:
                        oracle.process_response_async(response, audio_path)
                    else:
                        oracle.send_to_server("system", response)
        except Exception as e:
            logging.error(f"Erreur dans la conversation : {e}")

        self.write_status("idle")
        logging.info("Conversation terminée")

    def start_conversation(self):
        self.should_stop = False
        self.conversation_thread = threading.Thread(target=self.run_conversation)
        self.conversation_thread.daemon = True
        self.conversation_thread.start()
        logging.info("Conversation démarrée")

    def stop_conversation(self):
        self.should_stop = True
        if self.conversation_thread and self.conversation_thread.is_alive():
            self.conversation_thread.join(timeout=5)
            if self.conversation_thread.is_alive():
                logging.warning("Le thread de conversation ne répond pas.")

# === MAIN SERVER LOOP ===
server = OracleServer()
server.cleanup_on_startup()
logging.info("Serveur Oracle démarré. En attente de commandes...")


def signal_handler(sig, frame):
    logging.info("Signal reçu. Fermeture...")
    server.stop_conversation()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

while True:
    try:
        commands = [f for f in os.listdir(COMMANDS_DIR) if f.endswith(".cmd")]
        for cmd_file in commands:
            cmd_path = os.path.join(COMMANDS_DIR, cmd_file)
            with open(cmd_path, 'r') as f:
                cmd_data = json.load(f)
            command = cmd_data.get("command", "")

            import CONVERS
            oracle = CONVERS.OracleAssistant()

            if command == "start" and (not server.conversation_thread or not server.conversation_thread.is_alive()):
                server.write_status("starting")
                server.start_conversation()
                server.write_status("running")
            elif command == "stop" and server.conversation_thread and server.conversation_thread.is_alive():
                server.write_status("stopping")
                server.stop_conversation()
                server.write_status("idle")
            elif command == "engage":
                oracle.send_to_server("info", "Un visiteur approche")
                play_random_phrase(oracle, WELCOME_DIR)
            elif command == "departure":
                play_random_phrase(oracle, FAREWELL_DIR)
                oracle.send_to_server("info", "Le visiteur est parti")

            try:
                os.remove(cmd_path)
            except FileNotFoundError:
                pass

        time.sleep(0.2)

    except Exception as e:
        logging.error(f"Erreur dans la boucle principale: {e}")
        time.sleep(1)
