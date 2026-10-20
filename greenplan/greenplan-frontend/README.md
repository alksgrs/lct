# Зелёный план, интерфейс

React 19, TypeScript, Vite. 2D‑план на Canvas, 3D на three.js.

```bash
npm ci
npm run dev        # http://localhost:5173, API по адресу VITE_API_URL
npm run build      # сборка в dist/
```

`VITE_API_URL` по умолчанию `http://127.0.0.1:8000`; в Docker‑сборке `/api` (проксирует nginx).
