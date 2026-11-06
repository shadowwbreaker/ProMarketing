"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, getHealth, HealthReady } from "@/lib/api/client";
import { Card } from "@/components/ui/Card";
import { ErrorState, LoadingState } from "@/components/ui/States";

export function StatusPanel() {
  const [state, setState] = useState<{ loading: boolean; data?: HealthReady; error?: string }>({ loading: true });

  const load = useCallback(() => {
    const ctrl = new AbortController();
    setState({ loading: true });
    getHealth(ctrl.signal)
      .then((data) => setState({ loading: false, data }))
      .catch((e: unknown) =>
        setState({ loading: false, error: e instanceof ApiError ? e.message : "Неизвестная ошибка" }),
      );
    return () => ctrl.abort();
  }, []);

  useEffect(() => load(), [load]);

  if (state.loading) return <LoadingState text="Проверяем сервисы…" />;
  if (state.error) return <ErrorState message={state.error} onRetry={load} />;
  return (
    <Card>
      <p className="font-semibold">
        Статус: {state.data!.status === "ok" ? <span className="text-ok">работает</span> : <span className="text-warn">частично</span>}
      </p>
      <ul className="mt-2 text-sm">
        {Object.entries(state.data!.checks).map(([k, v]) => (
          <li key={k}>
            {k}: <span className={v === "ok" ? "text-ok" : "text-danger"}>{v}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
