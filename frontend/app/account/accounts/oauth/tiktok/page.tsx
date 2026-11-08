"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { LoadingState } from "@/components/ui/States";
import { finishTikTokOAuth } from "@/lib/api/social";
import { fieldErrors } from "@/lib/forms";

function Callback() {
  const q = useSearchParams();
  const router = useRouter();
  const [err, setErr] = useState<string>();
  const done = useRef(false);

  useEffect(() => {
    if (done.current) return;
    done.current = true;
    const code = q.get("code");
    const state = q.get("state");
    if (!code || !state) {
      setErr(q.get("error_description") ?? "Авторизация отменена");
      return;
    }
    finishTikTokOAuth(code, state)
      .then((acc) => router.replace(`/account/accounts/new?account=${acc.id}`))
      .catch((e) => setErr(fieldErrors(e).form));
  }, [q, router]);

  return err ? <p role="alert" className="text-danger">{err}</p> : <LoadingState text="Подключаем канал TikTok…" />;
}

export default function TikTokOAuthPage() {
  return (
    <Suspense>
      <Callback />
    </Suspense>
  );
}
