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
