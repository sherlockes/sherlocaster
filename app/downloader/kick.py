import datetime
import subprocess
import requests
import os
from curl_cffi import requests as cf


def fetch_vods(channel, limit=30, limit_days=0):
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
            print(f"[Kick] VOD {v.get('id')} sin m3u8, saltando")
            continue

        ts = v.get("start_time")
        if cutoff and ts:
            try:
                dt = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                if dt < cutoff:
                    continue
            except:
                pass

        results.append({
            "id": v.get("id"),
            "title": v.get("session_title") or v.get("slug") or str(v.get("id")),
            "date": ts,
            "m3u8": m3u8,
        })

    return results




def download_mp3(m3u8_url, output_path, bitrate="64k"):
    cmd = [
        "ffmpeg", "-y",
        "-i", m3u8_url,
        "-vn",
        "-acodec", "libmp3lame",
        "-b:a", bitrate,
        output_path
    ]
    print("[Kick] Ejecutando ffmpeg…")
    subprocess.run(cmd, check=True)


def process_kick_source(config, state):
    """
    Procesa VODs de Kick estilo Twitch
    """
    kick_cfg = config.get("sources", {}).get("kick", {})
    if not kick_cfg.get("enabled", True):
        print("[Kick] Disabled → saltando")
        return []

    channels = kick_cfg.get("channels", [])
    if not channels:
        print("[Kick] No hay canales definidos en config")
        return []

    limit_days = kick_cfg.get("limit_days", 0)
    limit = kick_cfg.get("limit", 10)
    bitrate = kick_cfg.get("audio_bitrate", "64k")

    # Estado tipo twitch/youtube
    downloaded_ids = {ep["id"] for ep in state.get("episodes", [])}

    new_episodes = []

    for ch in channels:
        channel = ch.get("channel")
        name = ch.get("name", channel)
        print(f"[Kick] Procesando canal: {name}")

        vods = fetch_vods(channel, limit=limit, limit_days=limit_days)

        for v in vods:
            vod_id = f"kick_{v['id']}"
            title = v.get("session_title") or v.get("slug") or f"VOD {v['id']}"
            created = v.get("created_at")

            if vod_id in downloaded_ids:
                print(f"[Kick] {vod_id} ya procesado")
                continue

            # Kick da directamente la URL del m3u8 en "source"
            m3u8_url = v.get("source")
            if not m3u8_url:
                print("[Kick] VOD sin source m3u8, saltando")
                continue

            # Prepara ruta de salida
            base_path = config.get("storage", {}).get("base_path", "/data")
            audio_dir = config.get("storage", {}).get("audio_dir", "audio")
            os.makedirs(os.path.join(base_path, audio_dir), exist_ok=True)

            filename = f"{vod_id}.mp3"
            output_path = os.path.join(base_path, audio_dir, filename)

            print(f"[Kick] Descargando audio → {filename}")
            try:
                download_mp3(m3u8_url, output_path, bitrate=bitrate)
            except Exception as e:
                print(f"[Kick] Error descargando {vod_id}: {e}")
                continue

            # Añadir al state
            entry = {
                "id": vod_id,
                "title": title,
                "date": created,
                "path": filename,
                "source": "kick",
                "channel": name
            }

            state.setdefault("episodes", []).append(entry)
            new_episodes.append(entry)

    return new_episodes
