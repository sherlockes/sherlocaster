import subprocess
from pathlib import Path
import os
import glob
import shutil

CONFIG_PATH = "/app/config/rclone.conf"

def upload_audio_dir(base_path: str, audio_dir: str, remote: str, remote_path: str) -> bool:
    """
    Sube de una sola vez todos los .mp3 de la carpeta /audio al remoto usando rclone.
    - base_path: por ejemplo "/data"
    - audio_dir: por ejemplo "audio"
    - remote: nombre del remoto en rclone.conf (p.ej. "gdrive")
    - remote_path: ruta remota (directorio), p.ej. "podcasts/sherlocaster"
    """
    audio_path = Path(base_path) / audio_dir

    if not audio_path.is_dir():
        print(f"[Rc] {audio_path} no existe o no es un directorio")
        return False

    print(f"[Rc] Subiendo todos los .mp3 desde {audio_path} → {remote}:{remote_path}")

    cmd = [
        "rclone",
        "--config", CONFIG_PATH,
        "copy",                       # copia el contenido del dir
        str(audio_path),
        f"{remote}:{remote_path}",
        "--include", "*.mp3",         # solo mp3
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0:
        print("[Rc] Error subiendo carpeta audio:")
        print(proc.stderr)
        return False

    print("[Rc] Subida de carpeta audio OK")
    shutil.rmtree(os.path.join(base_path, audio_dir))
    os.makedirs(os.path.join(base_path, audio_dir), exist_ok=True)
    return True


def rclone_upload(mp3_path: Path, remote: str, remote_path: str):
    mp3_path = Path(mp3_path)
    target = f"{remote}:{remote_path}"
    cmd = [
    "rclone",
    "--config", CONFIG_PATH,
    "copy",
    str(mp3_path),
    f"{remote}:{remote_path}"
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[Rc] Error subiendo {mp3_path.name}: {proc.stderr}")
        return False
    print(f"[Rc] Subido: {mp3_path.name}")
    return True

def upload_feed(config):
    remote = config['rclone']['remote']
    remote_path = config['rclone']['path']
    feed_path = Path("/data/feed.xml")

    cmd = [
        "rclone",
        "--config", CONFIG_PATH,
        "copy",
        str(feed_path),
        f"{remote}:{remote_path}"
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        print("[Rc] Feed subido")
    else:
        print("[Rc] Error subiendo feed:", proc.stderr)

def rclone_cleanup(remote: str, remote_path: str, retention_days: int):
    """
    Borra archivos del remoto más antiguos que retention_days usando rclone.
    Si retention_days == 0 no hace nada (modo desactivado).
    """
    if not retention_days or retention_days <= 0:
        print("[Rc] Limpieza remota desactivada (retention_days <= 0)")
        return

    print(f"[Rc] Borrando > {retention_days} días")
    cmd = [
        "rclone",
        "--config", "/app/config/rclone.conf",
        "delete",
        f"{remote}:{remote_path}",
        "--min-age", f"{retention_days}d"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("[Rc] Error limpieza remota:")
        print(result.stderr)
    else:
        print("[Rc] Limpieza remota OK")

def flush_pending_audio(base_path, audio_dir, remote, remote_path):
    """
    Sube archivos *.mp3 pendientes en la carpeta audio y luego la limpia.
    """
    audio_path = os.path.join(base_path, audio_dir)

    if not os.path.isdir(audio_path):
        print(f"[Rc] {audio_path} no existe")
        return

    # Buscar mp3 en la carpeta
    mp3_files = glob.glob(os.path.join(audio_path, "*.mp3"))

    if mp3_files:
        print(f"[Rc] {len(mp3_files)} pendiente en {audio_path}")

        for mp3 in mp3_files:
            fname = os.path.basename(mp3)
            remote_dest = f"{remote_path}/{fname}"

            print(f"[Rc] Subiendo → {fname} → {remote}:{remote_dest}")

            try:
                rclone_upload(mp3, remote, remote_dest)
                print(f"[Rc] Subido {fname}")
            except Exception as e:
                print(f"[Rc][Error] Falló subida de {fname}: {e}")
    else:
        print(f"[Rc] No hay pendientes en {audio_path}")

    # Limpiar carpeta audio
    try:
        shutil.rmtree(audio_path)
        os.makedirs(audio_path, exist_ok=True)
        print(f"[Rc][Clean] Carpeta {audio_path} limpiada.")
    except Exception as e:
        print(f"[Rc][Error] Error al limpiar {audio_path}: {e}")

