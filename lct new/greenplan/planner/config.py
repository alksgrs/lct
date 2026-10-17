import yaml


def load_planting_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    planting = data.get("planting", {})

    result = {}

    for species_type, config in planting.items():
        result[species_type] = {
            "grid_spacing_m": float(
                config["grid_spacing_m"]
            ),
            "min_spacing_m": float(
                config["min_spacing_m"]
            )
        }

        if species_type == "tree" and "bin_offset_m" in config:
            result[species_type]["bin_offset_m"] = float(
                config["bin_offset_m"]
            )

    return result

