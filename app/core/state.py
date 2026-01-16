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
    """
    Guarda el estado y aplica retención.
    """
    max_items = 100
    if config:
        max_items = config.get("max_items", max_items)

    # aplicar retención
    episodes = state.get("episodes", [])
    episodes = episodes[-max_items:]
    state["episodes"] = episodes

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with STATE_FILE.open("w") as f:
        json.dump(state, f, indent=2)

