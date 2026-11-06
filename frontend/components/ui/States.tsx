import { ReactNode } from "react";
import { Spinner } from "./Button";

export function LoadingState({ text = "Загрузка…" }: { text?: string }) {
  return (
    <div className="flex items-center gap-2 py-8 text-muted">
      <Spinner /> {text}
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
    <div className="rounded-lg border border-dashed border-border p-8 text-center">
      <p className="font-semibold">{title}</p>
      {children && <div className="mt-2 text-sm text-muted">{children}</div>}
    </div>
  );
}
