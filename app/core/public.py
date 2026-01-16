import os
from pathlib import Path
from datetime import datetime, timezone


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

    # generar nombre timestampado basado en hora actual
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_dst = os.path.join(LOG_DIR, f"{ts}.log")
    meta_dst = os.path.join(LOG_DIR, f"{ts}.meta")

    # copiar
    Path(LAST_RUN).replace(log_dst)
    Path(META).replace(meta_dst)

    # regenerar last_run.log y last_run.meta para compatibilidad
    # recreate legacy last_run.log symlink
    if os.path.lexists(LAST_RUN):
        Path(LAST_RUN).unlink()

    Path(LAST_RUN).symlink_to(log_dst)

    
    with open(meta_dst, "r") as f:
        with open(META, "w") as out:
            out.write(f.read())

    rotate_logs()

def publish_logs(title="Histórico de ejecuciones", selected=None):
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(STATUS_DIR, exist_ok=True)

    logs = [f for f in os.listdir(LOG_DIR) if f.endswith(".log")]
    logs.sort(reverse=True)

    if not logs:
        html = "<h1>No hay logs disponibles</h1>"
        with open(os.path.join(STATUS_DIR, "logs.html"), "w") as f:
            f.write(html)
        return

    if selected not in logs:
        selected = logs[0]

    # cargar contenido log
    with open(os.path.join(LOG_DIR, selected)) as f:
        log_content = f.read()

    # cargar meta asociada si existe
    base = selected.replace(".log", "")
    meta_file = os.path.join(LOG_DIR, f"{base}.meta")
    ts = _parse_log_timestamp(selected)
    duration = "N/D"

    if os.path.isfile(meta_file):
        with open(meta_file) as meta:
            for line in meta:
                if line.startswith("duration="):
                    s = float(line.split("=",1)[1].strip())
                    duration = f"{s:.1f} s"

    # preparar select
    options = "\n".join(
        f"<option value='{log}' {'selected' if log==selected else ''}>{_parse_log_timestamp(log)}</option>"
        for log in logs
    )

    # colorear errores y warnings al igual que en index
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
.metric {{ margin: 10px 0; }}
.err {{ color: red; font-weight: bold; }}
.warn {{ color: orange; font-weight: bold; }}
</style>
</head>
<body>
<h1>{title}</h1>

<form>
<select name="file" onchange="this.form.submit()">
{options}
</select>
</form>

<div class="metric"><b>Fecha:</b> {ts}</div>
<div class="metric"><b>Duración:</b> {duration}</div>

<h2>Log</h2>
<pre>{html_log}</pre>

</body>
</html>
"""

    with open(os.path.join(STATUS_DIR, "logs.html"), "w") as f:
        f.write(html)


def publish_status(title="Sherlocaster"):
    os.makedirs(STATUS_DIR, exist_ok=True)

    # Leer el log
    if os.path.isfile(LAST_RUN):
        with open(LAST_RUN, "r") as f:
            log_content = f.read()
    else:
        log_content = "Sin log disponible."

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

<div class="metric"><b>Última ejecución:</b> {timestamp} ({duration})</div>

<h2>Log</h2>
<pre>{html_log}</pre>

</body>
</html>
"""

    with open(os.path.join(STATUS_DIR, "index.html"), "w") as f:
        f.write(html)

    print("[Pb] index.html actualizado")
