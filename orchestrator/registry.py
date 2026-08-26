from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]

def load_yaml(name: str) -> dict:
    with open(ROOT / "registry" / name, encoding="utf-8") as f:
        return yaml.safe_load(f)

def workflows() -> dict:
    return load_yaml("workflows.yaml")["workflows"]

def policies() -> dict:
    return load_yaml("policies.yaml")

def get_workflow(name: str) -> dict:
    data = workflows()
    if name not in data:
        raise KeyError(f"Workflow capability '{name}' is not registered")
    return data[name]
