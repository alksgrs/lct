# GreenPlan, бэкенд

Расчёт плана озеленения, HTTP API и командная строка. Общее описание, алгоритм и ограничения — в README в корне репозитория.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn api:app --port 8000          # API, Swagger на /docs
python -m greenplan.cli plan.dxf --species all --output out.dxf
pytest
```

Справочник норм — `data/rules/regulations.yaml`, параметры посадки — `data/rules/planting.yaml`, шаблоны слоёв — `data/config/layers.yaml`. Отчёт о распознавании слоёв конкретного файла: `python -m greenplan.config.layer_matcher plan.dxf`.
