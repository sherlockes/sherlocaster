import json
from pathlib import Path
from datetime import datetime


STATE_FILE = Path("/data/state.json")


def load_state() -> dict:
    """
    Carga el estado desde state.json.
    Si no existe, devuelve un estado inicial válido.
    """
    if not STATE_FILE.exists():
        return {"episodes": []}

    try:
        with STATE_FILE.open("r") as f:
            return json.load(f)
    except Exception:
        return {"episodes": []}


def save_state(state: dict, config=None):
    # Intentamos leer feed_limit, si no retention.max_items, si no 100
    max_items = 100
    if config:
        # Buscamos primero feed_limit que es lo que quieres usar
        max_items = config.get("feed_limit", config.get("retention", {}).get("max_items", 100))

    episodes = state.get("episodes", [])
    if len(episodes) > max_items:
        episodes = episodes[-max_items:]
    
    state["episodes"] = episodes

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open("w") as f:
        json.dump(state, f, indent=2)

