import os
import datetime
import subprocess
from curl_cffi import requests as cf


def fetch_vods(channel: str, limit: int = 30, limit_days: int = 0):
    """
    Obtiene la lista de VODs de un canal de Kick.

    Devuelve una lista de dicts:
    {
        "id": ...,
        "title": ...,
        "date": ...,
        "m3u8": ...
    }
    """
    url = f"https://kick.com/api/v2/channels/{channel}/videos?limit={limit}"

    headers = {
        "accept": "application/json",
        "referer": f"https://kick.com/{channel}/videos",
        "sec-ch-ua": '"Chromium";v="120", "Not=A?Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Linux"',
    }

    r = cf.get(url, headers=headers, impersonate="chrome120")
    if r.status_code != 200:
        print(f"[Kick] HTTP {r.status_code}: {r.text[:200]}")
        return []

    vods = r.json()
    results = []

    cutoff = None
    if limit_days > 0:
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=limit_days)

    for v in vods:
        m3u8 = v.get("source")
        if not m3u8:
            # sin stream source, no podemos descargar
            continue

        title = v.get("session_title") or v.get("slug") or str(v.get("id"))
        date = v.get("start_time")
        vid = v.get("id")

        if cutoff and date:
            # API suele devolver "YYYY-MM-DD HH:MM:SS"
            try:
                dt = datetime.datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
                if dt < cutoff:
                    continue
            except Exception:
                # si no cuadra el formato, no filtramos por fecha
                pass

        results.append(
            {
                "id": vid,
                "title": title,
                "date": date,
                "m3u8": m3u8,
            }
        )

    return results


def _build_variant_m3u8(master_url: str, text: str) -> str:
    """
    Dado el master.m3u8 y su contenido, elige una variante "pequeña"
    (por ejemplo 160p) y construye la URL absoluta.

    Basado en el script m3u8.py proporcionado por ti.
    """
    variant = None
    for line in text.splitlines():
        if "160p" in line and line.strip().endswith("playlist.m3u8"):
            variant = line.strip()
            break

    # fallback genérico
    if not variant:
        variant = "playlist.m3u8"

    base = master_url.rsplit("/", 1)[0]
    return f"{base}/{variant}"


def download_kick_audio(m3u8_master_url: str, output_path: str, audio_bitrate: str = "64k") -> bool:
    """
    Descarga el audio desde un master.m3u8 de Kick y lo convierte a MP3
    usando ffmpeg. Devuelve True si todo va bien.
    """
    try:
        r = cf.get(m3u8_master_url, impersonate="chrome120")
        if r.status_code != 200:
            print(f"[Kick] Error al obtener master.m3u8 ({r.status_code})")
            return False

        text = r.text
        variant_url = _build_variant_m3u8(m3u8_master_url, text)
        print(f"[Kick] Descargando audio desde: {variant_url}")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-headers",
            "User-Agent: Mozilla/5.0",
            "-i",
            variant_url,
            "-map",
            "-ac", "1",
            "0:a:0",
            "-acodec",
            "libmp3lame",
            "-b:a",
            audio_bitrate,
            output_path,
        ]

        res = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if res.returncode != 0:
            print(f"[Kick] ffmpeg falló con código {res.returncode}")
            return False

        return True
    except Exception as e:
        print(f"[Kick] Excepción en download_kick_audio: {e}")
        return False


def get_audio_duration_sec(path: str) -> int:
    """
    Usa ffprobe para obtener la duración del audio en segundos (entero).
    Si falla, devuelve 0.
    """
    try:
        cmd = [
            "ffprobe",
            "-i",
            path,
            "-show_entries",
            "format=duration",
            "-v",
            "quiet",
            "-of",
            "csv=p=0",
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
        if not out:
            return 0
        return int(float(out))
    except Exception:
        return 0


def _normalize_kick_date(date_str: str | None) -> str | None:
    """
    Convierte 'YYYY-MM-DD HH:MM:SS' → 'YYYY-MM-DDTHH:MM:SSZ'
    Si falla o viene None, devuelve tal cual.
    """
    if not date_str:
        return None
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        return dt.isoformat() + "Z"
    except Exception:
        return date_str


def process_kick_source(config: dict, state: dict) -> dict:
    """
    Función principal que espera main.py (misma firma que youtube/twitch).

    - Lee la configuración de Kick en config['sources']['kick'].
    - Lista VODs de los canales.
    - Descarga el audio completo de cada VOD (si no existe ya).
    - Genera episodios en state['episodes'] con el mismo esquema que YouTube/Twitch.
    """

    kick_cfg = config.get("sources", {}).get("kick", {})
    if not kick_cfg.get("enabled", False):
        print("[Kick] Disabled → saltando")
        return state

    channels_cfg = kick_cfg.get("channels", [])
    content = kick_cfg.get("content", "vods")
    limit_days = kick_cfg.get("limit_days", 0)
    limit = kick_cfg.get("limit", 30)
    audio_bitrate = kick_cfg.get("audio_bitrate", "64k")
    fmt = kick_cfg.get("format", "mp3")

    if fmt != "mp3":
        print(f"[Kc] Aviso: formato '{fmt}' no soportado, usando mp3 igualmente")

    if not channels_cfg:
        print("[Kc] No hay canales definidos en config")
        return state

    print(
        f"[Kc] Config → content={content}, limit={limit}, "
        f"limit_days={limit_days}, audio_bitrate={audio_bitrate}"
    )

    # aseguramos estructura de state
    episodes = state.setdefault("episodes", [])

    # conjunto de IDs ya descargados para evitar duplicados
    existing_ids = {
        ep.get("id")
        for ep in episodes
        if isinstance(ep, dict) and "id" in ep
    }

    new_eps = []

    for ch in channels_cfg:
        # soporta tanto string como dict
        if isinstance(ch, str):
            channel_slug = ch
            channel_name = ch
        elif isinstance(ch, dict):
            channel_slug = ch.get("channel") or ch.get("name")
            channel_name = ch.get("name", channel_slug)
        else:
            print("[Kc] Entrada inválida en 'channels':", ch)
            continue

        if not channel_slug:
            print("[Kc] Canal sin 'channel' ni 'name', saltando:", ch)
            continue

        print(f"[Kc] Procesando canal: {channel_name} ({channel_slug})")

        vods = fetch_vods(channel_slug, limit=limit, limit_days=limit_days)
        if not vods:
            print(f"[Kick] Sin VODs para {channel_slug}")
            continue

        for v in vods:
            raw_id = v.get("id")
            if raw_id is None:
                continue

            episode_id = f"kck_{raw_id}"
            if episode_id in existing_ids:
                print(f"[Kc] Ya existe episodio {episode_id}, saltando")
                continue

            m3u8_url = v.get("m3u8")
            if not m3u8_url:
                continue

            # nombre de archivo y ruta
            filename = f"{episode_id}.mp3"
            file_path = os.path.join("/data/audio", filename)

            # descargar audio
            ok = download_kick_audio(m3u8_url, file_path, audio_bitrate=audio_bitrate)
            if not ok:
                print(f"[Kick] No se pudo descargar {episode_id}")
                continue

            duration_sec = get_audio_duration_sec(file_path)
            published_at = _normalize_kick_date(v.get("date"))
            downloaded_at = datetime.datetime.utcnow().isoformat() + "Z"

            # URL del VOD en Kick (forma estándar)
            original_url = f"https://kick.com/video/{raw_id}"

            title = f"{channel_name} — {v.get('title')}"
            episode = {
                "id": episode_id,
                "source": "kick",
                "title": title,
                "channel": channel_name,
                "original_url": original_url,
                "published_at": published_at,
                "downloaded_at": downloaded_at,
                "file_path": file_path,
                "duration_sec": duration_sec,
            }

            episodes.append(episode)
            existing_ids.add(episode_id)
            new_eps.append(episode)
            print(f"[Kick] Añadido episodio: {episode_id}")

    return new_eps
