import sys
import os
import fcntl
import re
from datetime import datetime, timezone
from pathlib import Path

# Imports del núcleo
from app.core.config import load_config
from app.core.state import load_state, save_state
from app.core.rss import generate_feed
from app.core.public import archive_last_run
from app.core.notifications import send_telegram_msg
from app.core.static_gen import StaticGenerator

# Imports de subida y limpieza
from app.uploader.rclone import upload_feed, rclone_cleanup, upload_audio_dir

# Clase para duplicar la salida a consola y a archivo de log
class TeeLogger(object):
    def __init__(self, filepath):
        self.file = open(filepath, "w", buffering=1, encoding="utf-8")
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        # Detecta códigos de escape ANSI (colores y barras de progreso)
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def write(self, data):
        self.stdout.write(data)
        # Limpiamos los códigos antes de escribir al archivo .log
        clean_data = self.ansi_escape.sub('', data)
        self.file.write(clean_data)

    def flush(self):
        self.stdout.flush()
        self.file.flush()

    def close(self):
        self.file.close()

def run():
    # --- BLOQUEO DE SEGURIDAD (LOCK) ---
    lock_file_path = "/data/sherlocaster.lock"
    # Abrimos (o creamos) el archivo de lock
    lock_file = open(lock_file_path, "w")
    
    try:
        # Intentamos obtener un bloqueo exclusivo sin esperar (LOCK_NB)
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        # Si falla, es que otro proceso ya tiene el cerrojo
        print(f"[{datetime.now().strftime('%H:%M:%S')}] AVISO: SherloCaster ya está en ejecución. Abortando instancia duplicada.")
        sys.exit(0)

    # --- INICIO NORMAL DEL SCRIPT ---
    start_time = datetime.now(timezone.utc)
    
    # Activamos el logger mejorado
    log_path = "/data/last_run.log"
    tee = TeeLogger(log_path)
    sys.stdout = tee
    sys.stderr = tee

    try:
        print(f"=== Inicio de ejecución: {start_time} ===")
        
        config = load_config()
        state = load_state()

        # Configuración de rutas y rclone
        rclone_cfg = config.get("rclone", {})
        storage_cfg = config.get("storage", {})
        src = config.get("sources", {})

        remote = rclone_cfg.get("remote")
        remote_path = rclone_cfg.get("path", "")
        retention_days = rclone_cfg.get("retention_days", 0)
        
        base_path = storage_cfg.get("base_path", "/data")
        audio_dir = storage_cfg.get("audio_dir", "audio")

        # --- NUEVO: Contadores para el informe ---
        stats = {"youtube": 0, "twitch": 0, "kick": 0}
        
        new_episodes = []

        # --- Procesamiento de Fuentes ---

        # YouTube
        if src.get("youtube", {}).get("enabled", True):
            from app.downloader.youtube import process_youtube_source
            new_episodes.extend(process_youtube_source(config, state))
        else:
            print("[Yt] Disabled → saltando")

        # Twitch
        if src.get("twitch", {}).get("enabled", True):
            from app.downloader.twitch import process_twitch_source
            new_episodes.extend(process_twitch_source(config, state))
        else:
            print("[Tw] Disabled → saltando")

        # Kick
        if src.get("kick", {}).get("enabled", True):
            from app.downloader.kick import process_kick_source
            new_episodes.extend(process_kick_source(config, state))
        else:
            print("[Kc] Disabled → saltando")

        # --- Guardado y Generación ---

        if new_episodes:
            if "episodes" not in state:
                state["episodes"] = []
            state["episodes"].extend(new_episodes)

        # ¡CRÍTICO: Fuera del if! Guardamos siempre para conservar los "ignorados"
        save_state(state, config)

        # Generar XML local
        generate_feed(config, state)
        print(f"[Fd] Feed ok con {len(state.get('episodes', []))} episodios")

        # --- EL MAYORDOMO INFORMA (Novedades) ---
        if len(new_episodes) > 0:
            print(f"[Tg] Intentando enviar notificación de {len(new_episodes)} episodios...")
            msg = f"🎙 <b>SherloCaster: ¡Novedades!</b>\n\n"
            msg += f"✅ Se han añadido <b>{len(new_episodes)}</b> episodios nuevos.\n"
            msg += f"\nÚltimo: <i>{new_episodes[-1]['title']}</i>"
            
            send_telegram_msg(msg)
            print("[Tg] Notificación enviada.")
        else:
            print("[Tg] No hay episodios nuevos. El Mayordomo guarda silencio.")
        
        # Subir XML
        upload_feed(config)

        # Subir audios nuevos y limpiar remotos
        upload_audio_dir(base_path, audio_dir, remote, remote_path)
        rclone_cleanup(remote, remote_path, retention_days)

        # Generar el sitio estático
        gen = StaticGenerator()
        gen.run()

        # --- Estadísticas Finales ---
        end_time = datetime.now(timezone.utc)
        duration = end_time - start_time

        with open("/data/last_run.meta", "w") as meta:
            meta.write(f"timestamp={end_time.isoformat()}Z\n")
            meta.write(f"duration={duration.total_seconds():.2f}\n")

        # Rotar logs al histórico
        archive_last_run()

        print("Ejecución finalizada con éxito.")

    except Exception as e:
        # 1. Avisamos en el log de forma clara
        print(f"\n[!] ERROR CRÍTICO durante la ejecución: {e}")

        # AVISO DE ERROR
        send_telegram_msg(f"⚠️ <b>SherloCaster Error</b>\nHubo un fallo crítico: <code>{str(e)}</code>")
        
        # 2. Relanzamos el error para ver el "Traceback" (el rastro del error)
        # Esto es lo que permite que veas en qué línea exacta falló.
        raise e 

    finally:
        print("Limpiando recursos y liberando bloqueo...")
        
        # 1. DEVOLVER LAS SALIDAS ORIGINALES (Vital para evitar el error)
        # tee.stdout y tee.stderr guardan los valores originales de la consola
        sys.stdout = tee.stdout
        sys.stderr = tee.stderr
        
        # 2. LIBERAR EL BLOQUEO
        try:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()
        except Exception as e:
            print(f"No se pudo liberar el archivo de lock: {e}")

        # 3. CERRAR EL LOGGER (Ahora que ya no es la salida principal)
        tee.close()
        
        print("Cierre de proceso limpio.")

if __name__ == "__main__":
    run()
