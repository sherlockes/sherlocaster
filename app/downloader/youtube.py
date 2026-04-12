from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
from yt_dlp import YoutubeDL


def _get_bitrate_kbps(bitrate_str: str) -> str:
    if not bitrate_str:
        return "64"
    return ''.join(ch for ch in bitrate_str if ch.isdigit()) or "64"


def _convert_mp3_to_mono_old(src: Path, bitrate: str):
    tmp_path = src.with_suffix(".mono_tmp.mp3")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-ac", "1",                # mono
        "-acodec", "libmp3lame",
        "-b:a", bitrate,
        str(tmp_path)
    ]

    print(f"[Yt] Convirtiendo a mono: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    # reemplazar archivo original
    src.unlink()
    tmp_path.rename(src)

def _convert_mp3_to_mono(src: Path, bitrate: str, speed: float = 1.0):
    tmp_path = src.with_suffix(".mono_tmp.mp3")
    bitrate_ffmpeg = f"{bitrate}k" if not str(bitrate).endswith('k') else bitrate

    # Construimos el comando base
    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-ac", "1",                # mono
        "-acodec", "libmp3lame",
    "-b:a", bitrate_ffmpeg
    ]

    # SI la velocidad es distinta a 1.0, añadimos el filtro atempo
    if speed != 1.0:
        # Nota: atempo soporta de 0.5 a 2.0. 
        cmd.extend(["-af", f"atempo={speed}"])

    cmd.append(str(tmp_path))

    print(f"[Yt] Procesando audio (bitrate: {bitrate}, speed: {speed}x): {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    src.unlink()
    tmp_path.rename(src)



def fetch_videos(channel_url: str, limit: int) -> list:
    """
    Lista los últimos 'limit' vídeos del canal (metadatos planos).
    """
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,
        "playlistend": limit,
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)

    return info.get("entries", [])[:limit]


def fetch_video_details_bak(video_url: str) -> dict | None:
    """
    Extrae metadata completa de un vídeo individual (timestamp real, duración, etc.).
    """
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
        return info
    except Exception as e:
        print(f"[Yt] Error metadata {video_url}: {e}")
        return None

def fetch_video_details(video_url: str) -> dict | None:
    """
    Extrae metadata completa de un vídeo individual.
    """
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "no_warnings": True, # Esto ayuda a callar un poco a yt-dlp
    }

    # Quitamos el try/except para que el error suba al bucle principal
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
    return info


def download_audio(video_url: str, video_id: str, audio_dir: Path, bitrate: str, speed: float = 1.0) -> Path | None:
    """
    Descarga el audio del vídeo como mp3.
    """
    audio_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(audio_dir / f"yt_{video_id}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "quiet": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": _get_bitrate_kbps(bitrate),
            }
        ],
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
        final_path = Path(ydl.prepare_filename(info)).with_suffix(".mp3")
        if final_path.exists():
            _convert_mp3_to_mono(final_path, bitrate, speed)
            return final_path
                
        return None
            
    except Exception as e:
        print(f"[Yt] Error descargando {video_url}: {e}")
        return None


def build_episode(entry: dict, channel_name: str, audio_path: Path, published_dt: datetime | None) -> dict:
    """
    Construye el diccionario episodio para YouTube.
    """
    title = entry.get("title") or "Sin título"
    vid_id = entry.get("id")
    url = entry.get("url") or entry.get("webpage_url") or f"https://www.youtube.com/watch?v={vid_id}"

    downloaded_dt = datetime.utcnow().replace(tzinfo=timezone.utc)

    # Si no hay fecha de publicación fiable, usamos la de descarga como fallback.
    if published_dt is None:
        published_dt = downloaded_dt

    return {
        "id": audio_path.stem,  # ej: yt_xxxxx
        "source": "youtube",
        "title": f"{channel_name} — {title}",
        "channel": channel_name,
        "original_url": url,
        "published_at": published_dt.isoformat().replace("+00:00", "Z"),
        "downloaded_at": downloaded_dt.isoformat().replace("+00:00", "Z"),
        "file_path": str(audio_path),
        "duration_sec": entry.get("duration", 0),
    }


def _get_published_datetime(details: dict) -> datetime | None:
    """
    Intenta obtener la fecha real de publicación a partir de la metadata completa del vídeo.
    """
    ts = details.get("timestamp")
    rs = details.get("release_timestamp")
    ud = details.get("upload_date")

    dt = None
    if ts:
        dt = datetime.fromtimestamp(ts, timezone.utc)
    elif rs:
        dt = datetime.fromtimestamp(rs, timezone.utc)
    elif ud:
        try:
            dt = datetime.strptime(ud, "%Y%m%d").replace(tzinfo=timezone.utc)
        except Exception:
            dt = None

    return dt


def process_youtube_source(config: dict, state: dict) -> list:
    """
    Pipeline YouTube:
    - Lista vídeos recientes por canal
    - Extrae metadata completa sólo mientras tenga sentido
    - Aplica límite por días y por número de episodios
    - Evita duplicados
    - Descarga audio y construye episodios nuevos
    """
    yt_cfg = config.get("sources", {}).get("youtube", {})
    if not yt_cfg.get("enabled", False):
        return []

    channels = yt_cfg.get("channels", [])
    limit_items = yt_cfg.get("limit", 2)  # máx episodios nuevos por canal
    limit_days = yt_cfg.get("limit_days")  # puede ser None si no se quiere límite temporal
    bitrate = yt_cfg.get("audio_bitrate", "64k")
    min_minutes = yt_cfg.get("min_minutes", "15")
    
    data_dir = Path("/data")
    audio_dir = data_dir / "audio"

    # Combinamos IDs de episodios descargados e IDs de vídeos ya ignorados
    downloaded_ids = {e["id"] for e in state.get("episodes", [])}
    if "ignored" in state:
        downloaded_ids.update(state["ignored"])
    
    new_episodes = []

    cutoff = None
    if limit_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=limit_days)

    for ch in channels:
        name = ch.get("name", "Canal")
        url = ch.get("url")
        ch_min_minutes = ch.get("min_minutes", min_minutes)

        # --- NUEVO: Mueve la lógica de configuración aquí dentro ---
        global_settings = config.get("settings", {})
        
        # Prioridad: 1. Canal -> 2. Fuente YouTube -> 3. Global -> 4. "64k"
        bitrate_str = (ch.get("audio_bitrate") or 
                       yt_cfg.get("audio_bitrate") or 
                       global_settings.get("audio_bitrate") or 
                       "64k")
        bitrate = _get_bitrate_kbps(bitrate_str)

        # Prioridad: 1. Canal -> 2. Global -> 3. 1.0
        speed = float(ch.get("speed") or global_settings.get("speed") or 1.0)
        # ----------------------------------------------------------
    
        if not url:
            continue

        try:
            print(f"[Yt] Canal: {name} (Min: {ch_min_minutes}m)")
            entries = fetch_videos(url, limit=limit_items * 5 or 10)  # escaneamos algo más de margen

            added_for_channel = 0

            for entry in entries:
                vid_id = entry.get("id") or entry.get("url")
                if not vid_id:
                    continue

                ep_id = f"yt_{vid_id}"
                if ep_id in downloaded_ids:
                    print(f"[Yt] {ep_id} ya procesado")
                    continue

                # Si ya hemos añadido suficientes episodios de este canal, paramos.
                if added_for_channel >= limit_items:
                    print(f"[Yt] Ya {limit_items} episodios {name}, stop")
                    break

                video_url = entry.get("url") or entry.get("webpage_url") or f"https://www.youtube.com/watch?v={vid_id}"

                # Metadata completa del vídeo
                #details = fetch_video_details(video_url)
                #if not details:
                #    print(f"[Yt] {ep_id} sin datos, saltando")
                #    downloaded_ids.add(ep_id)  # lo marcamos como visto para no insistir
                #    continue

                # --- NUEVO BLOQUE DE METADATA CON GESTIÓN DE MIEMBROS ---
                try:
                    details = fetch_video_details(video_url)
                except Exception as e:
                    error_msg = str(e)
                    # Si el error es de contenido para miembros, lo metemos en ignorados
                    if "members-only" in error_msg.lower():
                        print(f"[Yt] {ep_id} es solo para miembros. Ignorando para siempre...")
                        if "ignored" not in state:
                            state["ignored"] = []
                        if ep_id not in state["ignored"]:
                            state["ignored"].append(ep_id)
                        
                        downloaded_ids.add(ep_id)
                        continue
                    else:
                        print(f"[Yt] Error metadata {video_url}: {e}")
                        downloaded_ids.add(ep_id)
                        continue

                # Si no dio error pero tampoco devolvió detalles
                if not details:
                    print(f"[Yt] {ep_id} sin datos, saltando")
                    downloaded_ids.add(ep_id)
                    continue
                # --------------------------------------------------------

                published_dt = _get_published_datetime(details)

                # Límite temporal: si hay cutoff y la fecha es anterior → marcar visto y detener escaneo en este canal
                if cutoff is not None and published_dt is not None:
                    if published_dt < cutoff:
                        print(f"[Yt] {ep_id} más de {limit_days} días")
                        downloaded_ids.add(ep_id)
                        break

                # Sin fecha fiable y hay límite de días: lo marcamos como visto y seguimos con el siguiente
                if cutoff is not None and published_dt is None:
                    print(f"[Yt] {ep_id} sin fecha")
                    downloaded_ids.add(ep_id)
                    continue

                # Filtro por duración
                duration_sec = details.get("duration") or entry.get("duration") or 0
                duration_sec = int(duration_sec)

                # Convertimos el umbral de este canal a segundos
                min_seconds_threshold = int(ch_min_minutes) * 60

                #if duration_sec < min_seconds_threshold:
                if duration_sec < min_seconds_threshold:
                    print(f"[Yt] {ep_id} descartado: {duration_sec//60}m < {ch_min_minutes}m")
                    if "ignored" not in state:
                        state["ignored"] = []
                        
                    if ep_id not in state["ignored"]:
                        state["ignored"].append(ep_id)
                    
                    downloaded_ids.add(ep_id) 
                    continue

                # Descarga de audio
                audio_path = download_audio(video_url, vid_id, audio_dir, bitrate, speed)
                if not audio_path:
                    print(f"[Yt] Error descargando {ep_id}")
                    downloaded_ids.add(ep_id)
                    continue

                episode = build_episode(entry, name, audio_path, published_dt)
                new_episodes.append(episode)
                downloaded_ids.add(ep_id)
                added_for_channel += 1

                print(f"[Yt] Añadido: {episode['title']}")
        except Exception as e:
            # Capturamos cualquier error en este canal específico
            print(f"!!! [Yt] ERROR CRÍTICO procesando canal '{name}': {e}")
            # Al no hacer 'raise', el bucle for sigue con el siguiente 'ch'
            continue

    return new_episodes
