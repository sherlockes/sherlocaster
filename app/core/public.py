import os
from pathlib import Path
from datetime import datetime, timezone
import shutil


STATUS_DIR = "/data/html"
LAST_RUN = "/data/last_run.log"
META = "/data/last_run.meta"
LOG_DIR = "/data/logs"
MAX_LOGS = 10

def _parse_log_timestamp(name: str) -> str:
    """
    Convierte 'YYYYMMDD-HHMMSS' a 'YYYY-MM-DD HH:MM:SS'
    """
    try:
        base = name.replace(".log", "")
        dt = datetime.strptime(base, "%Y%m%d-%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return name


def _format_timestamp(ts: str) -> str:
    try:
        # Caso ISO con Z (RFC-like)
        if ts.endswith("Z"):
            dt = datetime.fromisoformat(ts[:-1]).replace(tzinfo=timezone.utc)
        else:
            # Caso ISO estándar aware o naive
            dt = datetime.fromisoformat(ts)

            # Si es naive -> asignar UTC por defecto
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

        dt = dt.astimezone()  # convierte UTC → local
        return dt.strftime("%Y-%m-%d a las %H:%M")

    except Exception:
        return ts  # fallback si algo no cuadra

def rotate_logs():
    os.makedirs(LOG_DIR, exist_ok=True)

    logs = [f for f in os.listdir(LOG_DIR) if f.endswith(".log")]
    logs.sort(reverse=True)  # por timestamp lexicográfico = por fecha

    for old in logs[MAX_LOGS:]:
        base = old.replace(".log", "")
        os.remove(os.path.join(LOG_DIR, old))
        meta = os.path.join(LOG_DIR, f"{base}.meta")
        if os.path.exists(meta):
            os.remove(meta)


def archive_last_run():
    os.makedirs(LOG_DIR, exist_ok=True)

    if not os.path.isfile(LAST_RUN):
        return

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_dst = os.path.join(LOG_DIR, f"{ts}.log")
    meta_dst = os.path.join(LOG_DIR, f"{ts}.meta")

    # copiar el log actual
    shutil.copyfile(LAST_RUN, log_dst)

    # copiar metadata
    if os.path.isfile(META):
        shutil.copyfile(META, meta_dst)

    # truncar last_run.log para el próximo run
    open(LAST_RUN, "w").close()

    rotate_logs()



def publish_logs(title="Histórico de logs"):
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(STATUS_DIR, exist_ok=True)

    logs = [f for f in os.listdir(LOG_DIR) if f.endswith(".log")]
    logs.sort(reverse=True)

    # ==========================
    # 1. Generar logs.html (índice)
    # ==========================
    if not logs:
        index_html = "<h1>No hay logs disponibles</h1>"
        with open(os.path.join(STATUS_DIR, "logs.html"), "w") as f:
            f.write(index_html)
        return

    # Para el índice necesitamos contar episodios para cada log
    items = []
    for log in logs:
        base = log.replace(".log", "")
        meta_file = os.path.join(LOG_DIR, f"{base}.meta")

        # leer duración si existe
        duration = "N/D"
        if os.path.isfile(meta_file):
            with open(meta_file) as meta:
                for line in meta:
                    if line.startswith("duration="):
                        s = float(line.split("=",1)[1].strip())
                        duration = f"{s:.1f} s"

        # leer log para contar episodios
        with open(os.path.join(LOG_DIR, log)) as f:
            content = f.read()

        episodios = sum(
            content.count(tag) for tag in ("[Yt] Añadido:", "[Tw] Añadido:")
        )

        # construir texto del enlace
        ts = _parse_log_timestamp(log).rsplit(":", 1)[0]

        dur = duration
        try:
            dur_val = float(duration.replace(" s",""))
            dur = f"{int(dur_val)} s"
        except:
            pass

        txt = f"{ts} - {dur}"

        
        if episodios > 0:
            txt += f" — {episodios} new"

        items.append(f"<li><a href='logs_{base}.html'>{txt}</a></li>")

    links = "\n".join(items)

    index_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{
    font-family: Arial, sans-serif;
    padding: 20px;
}}
ul {{
    list-style-type: none;
    padding: 0;
}}
li {{
    margin: 6px 0;
}}
</style>
</head>
<body>
<h1>{title}</h1>
<a href="index.html">← Volver al estado actual</a>
<ul>
{links}
</ul>
</body>
</html>
"""

    with open(os.path.join(STATUS_DIR, "logs.html"), "w") as f:
        f.write(index_html)

    # ==========================
    # 2. Generar logs individuales
    # ==========================

    for log in logs:
        with open(os.path.join(LOG_DIR, log)) as f:
            log_content = f.read()

        base = log.replace(".log", "")
        meta_file = os.path.join(LOG_DIR, f"{base}.meta")

        ts = _parse_log_timestamp(log)
        duration = "N/D"

        if os.path.isfile(meta_file):
            with open(meta_file) as meta:
                for line in meta:
                    if line.startswith("duration="):
                        s = float(line.split("=",1)[1].strip())
                        duration = f"{s:.1f} s"

        episodios = sum(
            log_content.count(tag) for tag in ("[Yt] Añadido:", "[Tw] Añadido:")
        )

        extra = f" — {episodios} new" if episodios > 0 else ""

        html_log = (
            log_content
            .replace("\n", "<br>")
            .replace("[Error]", "<span class='err'>[Error]</span>")
            .replace("[ERROR]", "<span class='err'>[ERROR]</span>")
            .replace("[Warn]", "<span class='warn'>[Warn]</span>")
            .replace("[WARNING]", "<span class='warn'>[WARNING]</span>")
        )

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>

body {{
    font-family: Arial, sans-serif;
    padding: 20px;
}}
pre {{
    white-space: pre-wrap;
    background: #f4f4f4;
    padding: 10px;
    border-radius: 5px;
    font-size: 14px;
}}
.err {{ color: red; font-weight: bold; }}
.warn {{ color: orange; font-weight: bold; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div><b>Fecha:</b> {ts}</div>
<div><b>Duración:</b> {duration}{extra}</div>

<h2>Log</h2>
<pre>{html_log}</pre>

<a href="logs.html">Volver al histórico</a>
</body>
</html>
"""

        with open(os.path.join(STATUS_DIR, f"logs_{base}.html"), "w") as f:
            f.write(html)


def publish_status(title="Sherlocaster"):
    os.makedirs(STATUS_DIR, exist_ok=True)

    # Leer el log
    if os.path.isfile(LAST_RUN):
        with open(LAST_RUN, "r") as f:
            log_content = f.read()
    else:
        log_content = "Sin log disponible."

    # Contar episodios añadidos en esta ejecución
    episodios = sum(
        log_content.count(tag) for tag in ("[Yt] Añadido:", "[Tw] Añadido:")
    )

    # Construir parte opcional
    extra = f" - {episodios} episodios añadidos" if episodios > 0 else ""


    # Leer metadata
    timestamp = "N/D"
    duration = "N/D"

    if os.path.isfile(META):
        with open(META, "r") as meta:
            for line in meta:
                if line.startswith("timestamp="):
                    timestamp = line.split("=",1)[1].strip()
                elif line.startswith("duration="):
                    s = float(line.split("=",1)[1].strip())
                    duration = f"{s:.1f} s"

    if timestamp not in ("N/D", None):
        timestamp = _format_timestamp(timestamp)


    # Resaltar errores y warnings
    html_log = (
        log_content
        .replace("\n", "<br>")
        .replace("[Error]", "<span class='err'>[Error]</span>")
        .replace("[ERROR]", "<span class='err'>[ERROR]</span>")
        .replace("[Warn]", "<span class='warn'>[Warn]</span>")
        .replace("[WARNING]", "<span class='warn'>[WARNING]</span>")
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{
    font-family: Arial, sans-serif;
    padding: 20px;
}}
pre {{
    white-space: pre-wrap;
    background: #f4f4f4;
    padding: 10px;
    border-radius: 5px;
    font-size: 14px;
}}
.metric {{
    margin: 10px 0;
}}
.err {{
    color: red;
    font-weight: bold;
}}
.warn {{
    color: orange;
    font-weight: bold;
}}
</style>
</head>
<body>
<h1>{title}</h1>

<div class="metric"><b>Última ejecución:</b> {timestamp} ({duration}{extra})</div>

<h2>Log <small><a href="logs.html">(Últimas ejecuciones)</a></small></h2>
<pre>{html_log}</pre>

</body>
</html>
"""

    with open(os.path.join(STATUS_DIR, "index.html"), "w") as f:
        f.write(html)

    print("[Pb] index.html actualizado")
