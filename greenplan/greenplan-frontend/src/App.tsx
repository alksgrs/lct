import { useCallback, useEffect, useRef, useState } from "react";

import { assignLayers, createRun, fetchJob, fetchResult } from "./api";
import ProcessingScreen from "./screens/ProcessingScreen";
import ResultScreen from "./screens/ResultScreen";
import UploadScreen from "./screens/UploadScreen";
import type { Job, PlanResult } from "./types";

const POLL_MS = 700;

export default function App() {
  const [job, setJob] = useState<Job | null>(null);
  const [result, setResult] = useState<PlanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const timer = useRef<number | undefined>(undefined);
  const generation = useRef(0);

  const poll = useCallback(async (id: string, ticket: number) => {
    if (ticket !== generation.current) return;
    try {
      const next = await fetchJob(id);
      if (ticket !== generation.current) return;
      setJob(next);
      if (next.status === "completed") {
        const data = await fetchResult(id);
        if (ticket !== generation.current) return;
        setResult(data);
        setVersion((v) => v + 1);
        setBusy(false);
        return;
      }
      if (next.status === "failed") {
        setBusy(false);
        return;
      }
      timer.current = window.setTimeout(() => void poll(id, ticket), POLL_MS);
    } catch (e) {
      setBusy(false);
      setError(e instanceof Error ? e.message : "Ошибка связи с сервером");
    }
  }, []);

  const follow = useCallback(
    (next: Job) => {
      window.clearTimeout(timer.current);
      generation.current += 1;
      setJob(next);
      setResult(null);
      void poll(next.id, generation.current);
    },
    [poll],
  );

  const start = async (file: File) => {
    setError(null);
    setBusy(true);
    try {
      follow(await createRun(file));
    } catch (e) {
      setBusy(false);
      setError(e instanceof Error ? e.message : "Не удалось загрузить файл");
    }
  };

  const applyLayers = async (overrides: Record<string, string>, boundaryLayer: string | null) => {
    if (!job) return;
    setError(null);
    setBusy(true);
    try {
      follow(await assignLayers(job.id, overrides, boundaryLayer));
    } catch (e) {
      setBusy(false);
      setError(e instanceof Error ? e.message : "Не удалось пересчитать");
    }
  };

  const restart = () => {
    window.clearTimeout(timer.current);
    generation.current += 1;
    setJob(null);
    setResult(null);
    setError(null);
    setBusy(false);
  };

  useEffect(() => () => window.clearTimeout(timer.current), []);

  useEffect(() => {
    if (!error) return;
    const id = window.setTimeout(() => setError(null), 7000);
    return () => window.clearTimeout(id);
  }, [error]);

  return (
    <>
      {error && (
        <div className="toast" role="alert">
          {error}
        </div>
      )}
      {!job && <UploadScreen busy={busy} onStart={start} />}
      {job && !result && <ProcessingScreen job={job} busy={busy} onApplyLayers={applyLayers} onRestart={restart} />}
      {job && result && (
        <ResultScreen key={version} result={result} busy={busy} onApplyLayers={applyLayers} onRestart={restart} />
      )}
    </>
  );
}
