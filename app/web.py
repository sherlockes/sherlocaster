import yaml
import shutil
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# --- Configuración Inicial ---

app = FastAPI(title="SherloCaster Web UI")

# Capturamos el momento en que arranca el proceso de la API
START_TIME = datetime.now(timezone.utc)

# Usando Path en lugar de os.path
LAST_CODE_UPDATE = datetime.fromtimestamp(Path(__file__).stat().st_mtime, tz=timezone.utc)

# Rutas de archivos
CONFIG_PATH = Path("config.yaml")
LOGS_DIR = Path("/data/logs")

# Montaje de archivos estáticos (CSS, etc)
app.mount("/static", StaticFiles(directory="/data/html"), name="static")

class ConfigPayload(BaseModel):
    content: str

# --- API Endpoints (Lógica) ---

@app.get("/api/system/status")
def get_system_status():
    return {
        "uptime": START_TIME.isoformat(),
        "build_date": LAST_CODE_UPDATE.isoformat(),
        "server_time": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/config")
def get_config():
    if not CONFIG_PATH.exists():
        return {"content": ""}
    return {"content": CONFIG_PATH.read_text(encoding="utf-8")}

@app.post("/api/config")
def save_config(payload: ConfigPayload):
    try:
        yaml.safe_load(payload.content)
        if CONFIG_PATH.exists():
            shutil.copy(CONFIG_PATH, CONFIG_PATH.with_suffix(".yaml.bak"))
        CONFIG_PATH.write_text(payload.content, encoding="utf-8")
        return {"status": "ok"}
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")

@app.get("/api/logs/last")
def get_last_log():
    if not LOGS_DIR.exists():
        return {"content": "No existe la carpeta de logs"}
    logs = sorted(LOGS_DIR.glob("*.log"), key=lambda p: p.name, reverse=True)
    if not logs:
        return {"content": "No hay logs disponibles"}

    last_log = logs[0]
    meta_path = last_log.with_suffix(".meta")
    meta = meta_path.read_text(encoding="utf-8", errors="ignore") if meta_path.exists() else None
    log_content = last_log.read_text(encoding="utf-8", errors="ignore")
    
    return {
        "filename": last_log.name,
        "content": log_content,
        "meta": meta,
        "episodes_added": log_content.count("Añadido")
    }

@app.get("/api/logs")
def list_logs():
    if not LOGS_DIR.exists(): return []
    logs = sorted(LOGS_DIR.glob("*.log"), key=lambda p: p.name, reverse=True)
    result = []
    for log in logs:
        content = log.read_text(encoding="utf-8", errors="ignore")
        result.append({
            "filename": log.name,
            "episodes_added": content.count("Añadido")
        })
    return result

@app.get("/api/feed/info")
def get_feed_info():
    xml_path = Path("/data/feed.xml")
    state_path = Path("/data/state.json")
    if not xml_path.exists():
        return {"error": "Feed no generado"}
    try:
        max_limit = 100
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r") as f:
                cfg = yaml.safe_load(f)
                max_limit = cfg.get("feed_limit", 100)
        tree = ET.parse(xml_path)
        channel = tree.getroot().find('channel')
        info = {
            "title": channel.findtext('title'),
            "episodes_count": len(channel.findall('item')),
            "max_limit": max_limit,
            "last_build": channel.findtext('lastBuildDate')
        }
        recent_episodes = []
        if state_path.exists():
            state = json.loads(state_path.read_text())
            recent_episodes = state.get("episodes", [])[-100:] 
            recent_episodes.reverse()
        return {"info": info, "recent": recent_episodes}
    except Exception as e:
        return {"error": str(e)}

# --- Page Endpoints (Rutas para el Navegador) ---

@app.get("/")
def index_page():
    return FileResponse("/data/html/index.html")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("/data/html/favicon.ico")

@app.get("/config")
def config_page():
    return FileResponse("/data/html/config.html")

@app.get("/logs")
def logs_page():
    return FileResponse("/data/html/last-log.html")

@app.get("/logs/list")
def logs_list_page():
    return FileResponse("/data/html/logs-list.html")

@app.get("/feed")
def feed_page():
    return FileResponse("/data/html/feed.html")

@app.get("/feed.xml")
def get_xml_file():
    return FileResponse("/data/feed.xml", media_type="application/xml")
