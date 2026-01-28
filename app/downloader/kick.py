import datetime
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
            continue

        title = v.get("session_title") or v.get("slug") or str(v.get("id"))
        date = v.get("start_time")
        vid = v.get("id")

        if cutoff and date:
            try:
                dt = datetime.datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
                if dt < cutoff:
                    continue
            except:
                pass

        results.append({
            "id": vid,
            "title": title,
            "date": date,
            "m3u8": m3u8,
        })

    return results


def process_kick_source(config: dict, state: dict) -> dict:
    """
    Firma CORRECTA, igual que youtube.py y twitch.py
    Por ahora solo imprime la lista de VODs sin modificar el state.
    """

    kick_cfg = config.get("sources", {}).get("kick", {})
    if not kick_cfg.get("enabled", False):
        print("[Kick] Disabled → saltando")
        return state

    channels = kick_cfg.get("channels", [])
    content = kick_cfg.get("content", "vods")
    limit_days = kick_cfg.get("limit_days", 0)
    limit = kick_cfg.get("limit", 30)

    print(f"[Kick] Config → content={content}, limit={limit}, limit_days={limit_days}")

    if not channels:
        print("[Kick] No hay canales definidos en config")
        return state

    for ch in channels:
        # Soporta tanto string como dict con keys
        if isinstance(ch, str):
            channel = ch
            name = ch
        elif isinstance(ch, dict):
            channel = ch.get("channel") or ch.get("name")
            name = ch.get("name", channel)
        else:
            print("[Kick] Entrada no válida en channels:", ch)
            continue

        print(f"[Kick] Listando VODs → {name} ({channel})")

        vods = fetch_vods(channel, limit=limit, limit_days=limit_days)
        for v in vods:
            print(f"  - {v['id']} | {v['title']} | {v['date']}")
            print(f"    m3u8: {v['m3u8']}")

    return state
