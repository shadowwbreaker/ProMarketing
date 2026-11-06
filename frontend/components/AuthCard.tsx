import { ReactNode } from "react";
import { Card } from "@/components/ui/Card";

export function AuthCard({ title, children, footer }: { title: string; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="mx-auto max-w-md">
      <Card>
        <h1 className="mb-4 text-2xl font-bold">{title}</h1>
        {children}
      </Card>
      {footer && <div className="mt-4 text-center text-sm text-muted">{footer}</div>}
    </div>
  );
}

export function FormError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-lg bg-danger/10 p-3 text-sm text-danger">
      {message}
    </p>
  );
}
