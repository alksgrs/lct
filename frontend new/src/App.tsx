import { useCallback, useEffect, useState } from "react";

import UploadPage from "./pages/UploadPage";
import ProcessingPage from "./pages/ProcessingPage";
import ResultPage from "./pages/ResultPage";

import {
  createJob,
  getJob,
  getResult,
} from "./services/api";

import type {
  Job,
  JobResult,
} from "./services/api";

type Screen =
  | "upload"
  | "processing"
  | "result";

export default function App() {
  const [screen, setScreen] =
    useState<Screen>("upload");

  const [job, setJob] =
    useState<Job | null>(null);

  const [result, setResult] =
    useState<JobResult | null>(null);

  const [error, setError] =
    useState<string | null>(null);

  const poll = useCallback(
    async (jobId: string) => {
      try {
        const next = await getJob(jobId);

        setJob(next);

        if (next.status === "FAILED") {
          setError(
            next.error ||
              "Во время расчёта произошла ошибка."
          );

          setScreen("processing");
          return;
        }

        if (next.status === "COMPLETED") {
          const finalResult =
            await getResult(jobId);

          setResult(finalResult);
          setScreen("result");

          return;
        }

        window.setTimeout(
          () => void poll(jobId),
          800
        );
      } catch (e) {
        setError(
          e instanceof Error
            ? e.message
            : "Ошибка расчёта"
        );
      }
    },
    []
  );

  const start = async (file: File) => {
    setError(null);

    try {
      const nextJob =
        await createJob(file);

      setJob(nextJob);
      setResult(null);
      setScreen("processing");

      void poll(nextJob.id);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Не удалось запустить расчёт"
      );
    }
  };

  const restart = () => {
    setError(null);
    setJob(null);
    setResult(null);
    setScreen("upload");
  };

  useEffect(() => {
    if (!error) {
      return;
    }

    const timer =
      window.setTimeout(
        () => setError(null),
        5000
      );

    return () =>
      window.clearTimeout(timer);
  }, [error]);

  return (
    <>
      {error && (
        <div
          className="toast-error"
          role="alert"
        >
          {error}
        </div>
      )}

      {screen === "upload" && (
        <UploadPage
          onStart={start}
        />
      )}

      {screen === "processing" && job && (
        <ProcessingPage
          job={job}
          onRestart={restart}
        />
      )}

      {screen === "result" && result && (
        <ResultPage
          result={result}
          onRestart={restart}
        />
      )}
    </>
  );
}
