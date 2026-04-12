import yaml
from pathlib import Path

CONFIG_FILE = Path("/app/config.yaml")

def load_config():
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f)
