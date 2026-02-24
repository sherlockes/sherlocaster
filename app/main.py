import sys
from datetime import datetime, timezone
from pathlib import Path

# Imports del núcleo
from app.core.config import load_config
from app.core.state import load_state, save_state
from app.core.rss import generate_feed
from app.core.public import archive_last_run

# Imports de subida y limpieza
from app.uploader.rclone import upload_feed, rclone_cleanup, upload_audio_dir

# Clase para duplicar la salida a consola y a archivo de log
class TeeLogger(object):
    def __init__(self, filepath):
        self.file = open(filepath, "w", buffering=1)
        self.stdout = sys.stdout
        self.stderr = sys.stderr

    def write(self, data):
        self.stdout.write(data)
        self.file.write(data)

    def flush(self):
        self.stdout.flush()
        self.file.flush()

    def close(self):
        try:
            self.flush()
            self.file.close()
        except:
            pass

def run():
    start_time = datetime.now(timezone.utc)
    
    # Activamos el logger inmediatamente
    tee = TeeLogger("/data/last_run.log")
    sys.stdout = tee
    sys.stderr = tee

    try:
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
            # Pasamos config para que respete el feed_limit que arreglamos
            save_state(state, config)

        # Generar XML local
        generate_feed(config, state)
        print(f"[Fd] Feed ok con {len(state.get('episodes', []))} episodios")
        
        # Subir XML
        upload_feed(config)

        # Subir audios nuevos y limpiar remotos
        upload_audio_dir(base_path, audio_dir, remote, remote_path)
        rclone_cleanup(remote, remote_path, retention_days)

        # --- Estadísticas Finales ---
        end_time = datetime.now(timezone.utc)
        duration = end_time - start_time

        with open("/data/last_run.meta", "w") as meta:
            meta.write(f"timestamp={end_time.isoformat()}Z\n")
            meta.write(f"duration={duration.total_seconds():.2f}\n")

        # Rotar logs al histórico
        archive_last_run()

    except Exception as e:
        print(f"\n[ERROR CRÍTICO] La ejecución ha fallado: {e}")
        raise e # Re-lanzamos para que Docker sepa que ha fallado
        
    finally:
        # Restauramos siempre los streams originales y cerramos archivo
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        tee.close()

if __name__ == "__main__":
    run()
