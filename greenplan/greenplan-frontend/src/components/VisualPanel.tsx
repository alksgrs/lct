import { Download, ImageIcon, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { fetchVisualStatus, visualize } from "../api";
import { num } from "../format";
import type { ImageProvider, Season, VisualStatus, Visualization } from "../types";

interface Props {
  runId: string;
  filename: string | null;
  onClose: () => void;
}

const SEASONS: [Season, string][] = [
  ["summer", "Лето"],
  ["autumn", "Осень"],
  ["winter", "Зима"],
];

const PROVIDERS: Record<ImageProvider, string> = {
  yandexart: "YandexART",
  gigachat: "GigaChat",
  kandinsky: "Kandinsky",
  pollinations: "Pollinations",
};

const EXTENSIONS: Record<string, string> = {
  "image/png": "png",
  "image/webp": "webp",
};

export default function VisualPanel({ runId, filename, onClose }: Props) {
  const [status, setStatus] = useState<VisualStatus | null>(null);
  const [season, setSeason] = useState<Season>("summer");
  const [provider, setProvider] = useState<ImageProvider | null>(null);
  const [picture, setPicture] = useState<Visualization | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => {
    fetchVisualStatus()
      .then(setStatus)
      .catch((e: Error) => setStatus({ available: false, provider: null, providers: [], message: e.message }));
    return () => controller.current?.abort();
  }, []);

  useEffect(() => {
    if (!busy) return;
    const started = Date.now();
    const timer = window.setInterval(() => setElapsed((Date.now() - started) / 1000), 250);
    return () => window.clearInterval(timer);
  }, [busy]);

  const run = async () => {
    controller.current?.abort();
    controller.current = new AbortController();
    setBusy(true);
    setError(null);
    setElapsed(0);
    try {
      setPicture(await visualize(runId, season, provider, controller.current.signal));
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setError(e instanceof Error ? e.message : "Не удалось получить изображение");
    } finally {
      setBusy(false);
    }
  };

  const save = () => {
    if (!picture) return;
    const mime = picture.image.slice(5, picture.image.indexOf(";"));
    const link = document.createElement("a");
    link.href = picture.image;
    const stem = (filename ?? "plan").replace(/\.dxf$/i, "");
    link.download = `${stem}_визуализация_${picture.season}.${EXTENSIONS[mime] ?? "jpg"}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  const chain = status?.providers ?? [];

  return (
    <section className="visual-panel" aria-label="ИИ-визуализация">
      <header className="visual-head">
        <h3>ИИ-визуализация</h3>
        <button type="button" className="icon-button" title="Закрыть" onClick={onClose}>
          <X size={16} />
        </button>
      </header>

      {status && !status.available ? (
        <div className="visual-off">
          <p>Генератор изображений не подключён.</p>
          <p className="muted small">{status.message}</p>
          <p className="muted small">
            Ключи задаются в переменных окружения API, подробнее — в README. Точная трёхмерная модель участка доступна и без
            ключа: это вид, который сейчас под панелью.
          </p>
        </div>
      ) : (
        <>
          <div className="visual-controls">
            <div className="segmented" aria-label="Сезон">
              {SEASONS.map(([value, label]) => (
                <button key={value} type="button" className={season === value ? "on" : ""} onClick={() => setSeason(value)} disabled={busy}>
                  {label}
                </button>
              ))}
            </div>
            {chain.length > 1 && (
              <label className="visual-provider">
                <span className="muted small">Генератор</span>
                <select
                  value={provider ?? ""}
                  onChange={(event) => setProvider((event.target.value || null) as ImageProvider | null)}
                  disabled={busy}
                >
                  <option value="">по очереди</option>
                  {chain.map((name) => (
                    <option key={name} value={name}>
                      {PROVIDERS[name] ?? name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <button type="button" className="primary-button" onClick={run} disabled={busy || !status}>
              <ImageIcon size={15} />
              {busy ? `Генерация… ${num(elapsed, 0)} с` : picture ? "Ещё вариант" : "Сгенерировать"}
            </button>
          </div>

          {status?.message && <p className="muted small">{status.message}</p>}
          {!provider && chain.length > 1 && (
            <p className="muted small">
              Сначала {PROVIDERS[chain[0]]}, если не ответит — {chain.slice(1).map((name) => PROVIDERS[name]).join(", затем ")}.
            </p>
          )}

          {error && <p className="verdict tone-stop visual-error">{error}</p>}

          {picture ? (
            <figure className={`visual-figure ${busy ? "is-stale" : ""}`}>
              <img src={picture.image} alt="Иллюстрация озеленения участка по параметрам плана" />
              <figcaption>
                <span>
                  Иллюстрация по параметрам плана, не точная расстановка. {picture.provider_name ?? PROVIDERS[picture.provider]},{" "}
                  {num(picture.elapsed_s, 0)} с.
                </span>
                <button type="button" className="ghost-button" onClick={save}>
                  <Download size={15} />
                  Скачать
                </button>
              </figcaption>
              {picture.skipped.length > 0 && (
                <details className="visual-prompt">
                  <summary>Не сработали: {picture.skipped.map((line) => line.split(":")[0]).join(", ")}</summary>
                  <p className="visual-error">{picture.skipped.join("\n")}</p>
                </details>
              )}
              <details className="visual-prompt">
                <summary>Описание, отправленное генератору</summary>
                <p>{picture.prompt}</p>
              </details>
            </figure>
          ) : (
            !busy && (
              <p className="muted small">
                Изображение строится по рассчитанному плану: площадь, число деревьев и кустарников, объекты на участке. Генерация
                занимает 15–60 секунд.
              </p>
            )
          )}
        </>
      )}
    </section>
  );
}
