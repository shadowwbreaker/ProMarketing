"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AuthCard } from "@/components/AuthCard";
import { LoadingState } from "@/components/ui/States";
import { verifyEmail } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";

function Verify() {
  const token = useSearchParams().get("token") ?? "";
  const { refresh } = useAuth();
  const [state, setState] = useState<"loading" | "ok" | string>("loading");

  useEffect(() => {
    verifyEmail(token)
      .then(() => {
        setState("ok");
        void refresh();
      })
      .catch((e) => setState(fieldErrors(e).form ?? "Ошибка"));
  }, [token, refresh]);

  if (state === "loading") return <LoadingState text="Проверяем ссылку…" />;
  if (state === "ok")
    return (
      <p className="text-sm">
        Email подтверждён. <Link className="font-semibold text-accent" href="/account">Перейти в кабинет</Link>
      </p>
    );
  return <p role="alert" className="text-sm text-danger">{state}</p>;
}

export default function VerifyEmailPage() {
  return (
    <AuthCard title="Подтверждение email">
      <Suspense>
        <Verify />
      </Suspense>
    </AuthCard>
  );
}
