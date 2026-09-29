import {
  ArrowRight,
  CheckCircle2,
  Leaf
} from "lucide-react";

import { useState } from "react";

import Layout from "../components/Layout";
import UploadDropzone from "../components/UploadDropzone";

export default function UploadPage({
  onStart
}: {
  onStart: (file: File) => Promise<void>;
}) {
  const [file, setFile] =
    useState<File | null>(null);

  const [loading, setLoading] =
    useState(false);

  const start = async () => {
    if (!file) return;

    setLoading(true);

    try {
      await onStart(file);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <section className="hero hero-centered">
        <span className="eyebrow">
          Зелёный План · автоматический расчёт
        </span>

        <h1>
          Загрузите участок — получите
          готовый план озеленения
        </h1>
      </section>

      <section className="upload-workspace">
        <div className="upload-main panel">
          <div className="panel-heading">
            <div className="step-number">
              1
            </div>

            <div>
              <h2>Загрузите DXF</h2>

              <p>
                Исходная геометрия участка
                и его объекты
              </p>
            </div>
          </div>

          <UploadDropzone
            file={file}
            onChange={setFile}
          />

          <div className="upload-action">
            <button
              className="primary-button primary-large full"
              onClick={start}
              disabled={!file || loading}
            >
              <Leaf size={19} />

              {loading
                ? "Запуск расчёта…"
                : "Рассчитать"}

              {!loading && (
                <ArrowRight size={19} />
              )}
            </button>

            {!file && (
              <span className="action-hint">
                Сначала выберите DXF-файл
              </span>
            )}

            {file && (
              <span className="action-hint success">
                <CheckCircle2 size={14} />
                Файл готов к расчёту
              </span>
            )}
          </div>
        </div>
      </section>

      <section className="info-strip">
        <strong>
          Сценарий работы
        </strong>

        <span>
          DXF → анализ → допустимые зоны
          → посадки → проверка → готовый план
        </span>
      </section>
    </Layout>
  );
}