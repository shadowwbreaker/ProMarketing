import { ReactNode } from "react";
import { Spinner } from "./Button";

/** Skeleton rows instead of a bare spinner: the page keeps its shape while data loads. */
export function LoadingState({ text = "Загрузка…" }: { text?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-3 py-6">
      <span className="sr-only">{text}</span>
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex items-center gap-4" aria-hidden>
          <div className="skeleton h-10 w-10 shrink-0 rounded-[30%]" />
          <div className="flex-1 space-y-2">
            <div className="skeleton h-3.5" style={{ width: `${70 - i * 12}%` }} />
            <div className="skeleton h-3 w-1/3" />
          </div>
        </div>
      ))}
      {text !== "Загрузка…" && <p className="flex items-center gap-2 text-sm text-muted" aria-hidden><Spinner /> {text}</p>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-lg border border-danger/40 bg-danger/5 p-4 text-sm">
      <p className="font-semibold text-danger">Что-то пошло не так</p>
      <p className="mt-1 text-text">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 text-sm font-semibold underline">
          Повторить
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="page-enter rounded-2xl border border-dashed border-border p-8 text-center">
      <p className="font-semibold">{title}</p>
      {children && <div className="mt-2 text-sm text-muted">{children}</div>}
    </div>
  );
}
