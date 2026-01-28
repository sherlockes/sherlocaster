from app.core.config import load_config
from app.core.state import load_state, save_state
from app.core.rss import generate_feed
from app.uploader.rclone import upload_feed, rclone_cleanup, flush_pending_audio, upload_audio_dir
from pathlib import Path
from app.uploader.rclone import rclone_upload
from app.core.public import publish_status, publish_logs, archive_last_run
import sys
import shutil
import os
from datetime import datetime, timezone

start_time = datetime.now(timezone.utc)


class TeeLogger(object):
    def __init__(self, filepath):
        self.file = open(filepath, "w", buffering=1)
        self.stdout = sys.stdout
        self.stderr = sys.stderr   # para capturar stderr también

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



# Activamos el logger
tee = TeeLogger("/data/last_run.log")
sys.stdout = tee
sys.stderr = tee   # capturamos también stderr


def run():
    config = load_config()
    state = load_state()

    # Extraer variables de config.yaml
    rclone_cfg = config.get("rclone", {})
    remote = rclone_cfg.get("remote")
    remote_path = rclone_cfg.get("path", "")
    retention_days = rclone_cfg.get("retention_days", 0)
    storage_cfg = config.get("storage", {})
    base_path = storage_cfg.get("base_path","/data")
    audio_dir = storage_cfg.get("audio_dir","audio")


    src = config.get("sources", {})
    yt_cfg = src.get("youtube", {})
    yt_enabled = yt_cfg.get("enabled", True)
    tw_cfg = src.get("twitch", {})
    tw_enabled = tw_cfg.get("enabled", True)
    kc_cfg = src.get("kick", {})
    kc_enabled = kc_cfg.get("enabled", True)

    new_episodes = []

    # YouTube
    if yt_enabled:
        from app.downloader.youtube import process_youtube_source
        yt_eps = process_youtube_source(config, state)
        new_episodes.extend(yt_eps)
    else:
        print(f"[Yt] Disabled → saltando")

    # Twitch
    if tw_enabled:
        from app.downloader.twitch import process_twitch_source
        tw_eps = process_twitch_source(config, state)
        new_episodes.extend(tw_eps)
    else:
        print(f"[Tw] Disabled → saltando")

    # Kick
    if kc_enabled:
        from app.downloader.kick import process_kick_source
        kick_eps = process_kick_source(config, state)
        new_episodes.extend(kick_eps)
    else:
        print(f"[Kc] Disabled → saltando")


    # Añadir nuevos
    if new_episodes:
        if "episodes" not in state:
            state["episodes"] = []
        state["episodes"].extend(new_episodes)
        save_state(state)

    # Generar Feed
    generate_feed(config, state)
    print(f"[Fd] Feed ok con {len(state.get('episodes', []))} episodios")
    upload_feed(config)

    # Subir audios a remoto mediante Rclone
    upload_audio_dir(base_path, audio_dir, remote, remote_path)
                
    # Limpieza remota: borrar archivos antiguos si retention_days > 0
    rclone_cleanup(remote, remote_path, retention_days)

    # Guardar estadísticas
    end_time = datetime.now(timezone.utc)
    duration = end_time - start_time

    with open("/data/last_run.meta", "w") as meta:
        meta.write(f"timestamp={end_time.isoformat()}Z\n")
        meta.write(f"duration={duration.total_seconds():.2f}\n")


    # Cerrar TeeLogger antes de rotar logs
    sys.stdout.close()
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__

    # Publicar contenido en nginx
    archive_last_run()
    publish_status("Sherlocaster")
    publish_logs()


       
if __name__ == "__main__":
    run()
