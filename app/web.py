from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import yaml
from pathlib import Path
from fastapi.responses import FileResponse
import shutil


app = FastAPI()

CONFIG_PATH = Path("config.yaml")


class ConfigPayload(BaseModel):
    content: str


@app.get("/api/config")
def get_config():
    if not CONFIG_PATH.exists():
        return {"content": ""}

    return {
        "content": CONFIG_PATH.read_text(encoding="utf-8")
    }


@app.post("/api/config")
def save_config(payload: ConfigPayload):
    try:
        yaml.safe_load(payload.content)

        # Backup antes de guardar
        if CONFIG_PATH.exists():
            shutil.copy(CONFIG_PATH, CONFIG_PATH.with_suffix(".yaml.bak"))

        CONFIG_PATH.write_text(payload.content, encoding="utf-8")

        return {"status": "ok"}

    except yaml.YAMLError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid YAML: {str(e)}"
        )


@app.get("/config")
def config_page():
    return FileResponse("/data/html/config.html")

LOGS_DIR = Path("/data/logs")

@app.get("/api/logs/last")
def get_last_log():
    if not LOGS_DIR.exists():
        return {"content": "No existe la carpeta de logs"}

    logs = sorted(
        LOGS_DIR.glob("*.log"),
        key=lambda p: p.name,
        reverse=True
    )

    if not logs:
        return {"content": "No hay logs disponibles"}

    last_log = logs[0]

    meta_path = last_log.with_suffix(".meta")

    meta = None
    if meta_path.exists():
        meta = meta_path.read_text(encoding="utf-8", errors="ignore")

    log_content = last_log.read_text(encoding="utf-8", errors="ignore")
    episodes_added = log_content.count("Añadido")


    return {
        "filename": last_log.name,
        "content": last_log.read_text(encoding="utf-8", errors="ignore"),
        "meta": meta,
        "episodes_added": episodes_added
    }



@app.get("/logs")
def logs_page():
    return FileResponse("/data/html/last-log.html")

@app.get("/api/logs")
def list_logs():
    if not LOGS_DIR.exists():
        return []

    logs = sorted(
        LOGS_DIR.glob("*.log"),
        key=lambda p: p.name,
        reverse=True
    )

    result = []

    for log in logs:
        name = log.stem  # sin .log → YYYYMMDD-HHMMSS

        date = None
        time = None

        try:
            date_part, time_part = name.split("-")
            date = f"{date_part[0:4]}-{date_part[4:6]}-{date_part[6:8]}"
            time = f"{time_part[0:2]}:{time_part[2:4]}:{time_part[4:6]}"
        except Exception:
            pass

        content = log.read_text(encoding="utf-8", errors="ignore")
        episodes_added = content.count("Añadido")

        result.append({
            "filename": log.name,
            "date": date,
            "time": time,
            "episodes_added": episodes_added
        })

    return result

@app.get("/logs/list")
def logs_list_page():
    return FileResponse("/data/html/logs-list.html")


@app.get("/api/logs/{filename}")
def get_log_by_name(filename: str):
    log_path = LOGS_DIR / filename

    if not log_path.exists() or not log_path.suffix == ".log":
        return {"content": "Log no encontrado"}

    meta_path = log_path.with_suffix(".meta")
    meta = None
    if meta_path.exists():
        meta = meta_path.read_text(encoding="utf-8", errors="ignore")

    content = log_path.read_text(encoding="utf-8", errors="ignore")
    episodes_added = content.count("Añadido")

    return {
        "filename": log_path.name,
        "content": content,
        "meta": meta,
        "episodes_added": episodes_added
    }
