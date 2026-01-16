import os
from pathlib import Path
from datetime import datetime, timezone


STATUS_DIR = "/data/html"
LAST_RUN = "/data/last_run.log"
META = "/data/last_run.meta"

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
