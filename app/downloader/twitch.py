import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os

def _run(cmd: list):
    """Ejecuta un comando y devuelve stdout como texto, lanza error si algo falla."""
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def _download_mkv(video_id: str, out_path: Path, token: str):
    """Descarga el audio_only de Twitch en MKV usando twitch-dl."""
    cmd = [
        "twitch-dl", "download", video_id,
        "-q", "audio_only",
        "--output", str(out_path),
        "--auth-token", token
    ]
    print(f"[Tw] Ejecutando: {' '.join(cmd)}")
    _run(cmd)


def _convert_to_mp3(mkv_path: Path, mp3_path: Path, bitrate: str):
    """Convierte MKV -> MP3 usando ffmpeg."""
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", str(mkv_path),
        "-ac", "1",
        "-acodec", "libmp3lame",
        "-b:a", bitrate,
        str(mp3_path)
    ]
    print(f"[Tw] Convirtiendo a MP3: {' '.join(ffmpeg_cmd)}")
    _run(ffmpeg_cmd)


def process_twitch_source(config: dict, state: dict) -> list:
    tw_cfg = config.get("sources", {}).get("twitch", {})
    if not tw_cfg.get("enabled", False):
        return []

    token = os.getenv("AUTH_TOKEN", "").strip()
    if not token:
        print("[Tw] ERROR: AUTH_TOKEN vacío → no se puede descargar VODs")
        return []

    # Leyendo variables de config.yaml
    limit_days = tw_cfg.get("limit_days")
    limit = tw_cfg.get("limit")
    min_minutes = tw_cfg.get("min_minutes", 0)
    bitrate = tw_cfg.get("audio_bitrate", "64k")
    channels = tw_cfg.get("channels", [])
    storage = config.get("storage", {})
    base_path = Path(storage.get("base_path", "/data"))
    audio_dir = base_path / storage.get("audio_dir", "audio")
    temp_dir = base_path / storage.get("temp_dir", "tmp")

    # Creando directorios si no existen
    audio_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Escaneando canales
    downloaded_ids = {ep["id"] for ep in state.get("episodes", [])}
    new_eps = []

    for ch in channels:
        name = ch.get("name") or ch.get("channel")
        channel = ch.get("channel")
        if not channel:
            print("[Tw] canal sin 'channel'")
            continue

        print(f"[Tw] Procesando canal: {name}")

        # obtenemos la lista de vídeos desde twitch-dl
        cmd = ["twitch-dl", "videos", channel, "--json"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except Exception as e:
            print(f"[Tw] Error listando videos: {e}")
            continue

        import json
        try:
            videos = json.loads(result.stdout)["videos"]
            # aplicar limite de vídeos
            if limit is not None:
                videos = videos[:limit]

        except Exception:
            print("[Tw] No se pudo parsear JSON")
            continue

        for v in videos:
            vid = v.get("id")
            if not vid:
                continue

            ep_id = f"twt_{vid}"

            # Obtener la hora de publicación
            published_str = v.get("publishedAt")
            now = datetime.now(timezone.utc)

            if published_str:
                try:
                    published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                except Exception:
                    published = now
            else:
                published = now

            # Descarta el episodio si ya está descargado
            if ep_id in downloaded_ids:
                print(f"[Tw] {ep_id} ya procesado")
                continue

            # Descarta el episodio si no está marcado como 'recorded'
            status = v.get("status", "").lower()
            if status != "recorded":
                print(f"[Tw] {ep_id} no finalizado, status={status!r}")
                continue

            # Descarta el episodio si se publicó hace menos de 3h
            if published + timedelta(hours=3) > now:
                print(f"[Tw] {ep_id} aún en emisión (pub={published.isoformat()})")
                continue

            # Descarta el episodio si tiene más de los días configurados
            if limit_days is not None:
                age_days = (now - published).days
                if age_days > limit_days:
                    print(f"[Tw] {ep_id} > {limit_days} días")
                    continue
          
            # Descarta el episodio si es corto
            duration_sec = v.get("lengthSeconds", 0)
            if duration_sec > 0:
                if duration_sec / 60 < min_minutes:
                    print(f"[Tw] {ep_id} < {min_minutes} min")
                    downloaded_ids.add(ep_id)
                    continue

            # Descargando audio
            print(f"[Tw] Bajando audio: {ep_id}")

            mkv_path = audio_dir / f"{ep_id}.mkv"
            mp3_path = audio_dir / f"{ep_id}.mp3"

            try:
                _download_mkv(vid, mkv_path, token)
                _convert_to_mp3(mkv_path, mp3_path, bitrate)
                mkv_path.unlink(missing_ok=True)
            except Exception as e:
                print(f"[Tw] Error descargando {ep_id}: {e}")
                continue

            episode = {
                "id": ep_id,
                "source": "twitch",
                "title": f"{name} — {v.get('title', 'Sin título')}",
                "channel": name,
                "original_url": f"https://www.twitch.tv/videos/{vid}",
                "published_at": published.isoformat().replace("+00:00", "Z"),
                "downloaded_at": datetime.utcnow().isoformat() + "Z",
                "file_path": str(mp3_path),
                "duration_sec": duration_sec,
            }

            new_eps.append(episode)
            downloaded_ids.add(ep_id)
            print(f"[Tw] Añadido: {episode['title']}")

    return new_eps
