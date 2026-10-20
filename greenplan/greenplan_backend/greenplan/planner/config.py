import yaml


def load_planting_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    result = {}
    for species_type, config in data.get("planting", {}).items():
        result[species_type] = {key: float(value) for key, value in config.items()}
    return result
