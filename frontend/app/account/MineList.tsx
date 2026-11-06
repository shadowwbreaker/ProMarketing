"use client";

import { ReactNode, useEffect, useState } from "react";
import { listMine, Page } from "@/lib/api/auth";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { fieldErrors } from "@/lib/forms";

export function MineList<T extends { id: string }>({
  path,
  empty,
  render,
}: {
  path: string;
  empty: string;
  render: (item: T) => ReactNode;
}) {
  const [state, setState] = useState<{ loading: boolean; data?: Page<T>; error?: string }>({ loading: true });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let alive = true;
    setState({ loading: true });
    listMine<T>(path)
      .then((data) => alive && setState({ loading: false, data }))
      .catch((e) => alive && setState({ loading: false, error: fieldErrors(e).form }));
    return () => {
      alive = false;
    };
  }, [path, nonce]);

  if (state.loading) return <LoadingState />;
  if (state.error) return <ErrorState message={state.error} onRetry={() => setNonce((n) => n + 1)} />;
  if (!state.data!.results.length) return <EmptyState title={empty} />;
  return (
    <ul className="divide-y divide-border rounded-xl border border-border bg-surface">
      {state.data!.results.map((it) => (
        <li key={it.id} className="p-4 text-sm">
          {render(it)}
        </li>
      ))}
    </ul>
  );
}
