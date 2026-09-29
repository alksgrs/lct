import {
  AlertCircle,
  Leaf,
  LoaderCircle
} from "lucide-react";

import Layout from "../components/Layout";
import ProgressSteps from "../components/ProgressSteps";
import type { Job } from "../services/api";

export default function ProcessingPage({
  job,
  onRestart
}: {
  job: Job;
  onRestart: () => void;
}) {
  const failed =
    job.status === "FAILED";

  return (
    <Layout>
      <div className="center-page">
        <div className="processing-card">
          {failed ? (
            <AlertCircle
              className="failed-icon"
              size={48}
            />
          ) : (
            <LoaderCircle
              className="spin"
              size={48}
            />
          )}

          <span className="eyebrow">
            {failed
              ? "Расчёт остановлен"
              : "Зелёный План выполняет расчёт"}
          </span>

          <h1>
            {failed
              ? "Не удалось обработать файл"
              : "Формируем готовый план"}
          </h1>

          <p>
            {failed
              ? job.error
              : "Сервис анализирует участок и формирует план озеленения."}
          </p>

          {!failed && (
            <div className="automatic-message">
              <Leaf size={17} />

              <span>
                Сервис самостоятельно анализирует
                участок, коммуникации и нормативные
                ограничения.
              </span>
            </div>
          )}

          <ProgressSteps
            stage={job.stage}
            progress={job.progress}
          />

          {failed && (
            <>
              <div className="error-box">
                {job.error ??
                  "Неизвестная ошибка."}
              </div>

              <button
                className="secondary-button restart-button"
                onClick={onRestart}
              >
                Вернуться к загрузке
              </button>
            </>
          )}
        </div>
      </div>
    </Layout>
  );
}
