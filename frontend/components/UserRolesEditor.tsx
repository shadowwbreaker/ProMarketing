"use client";

import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { Me } from "@/lib/api/auth";
import { apiFetch } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";
import { fieldErrors } from "@/lib/forms";
import { ROLE_LABELS } from "@/lib/roles";

export function UserRolesEditor({ userId, roles, onSaved }: {
  userId: string; roles: string[]; onSaved: (roles: string[]) => void;
}) {
  const { me, setMe } = useAuth();
  const [selected, setSelected] = useState(roles);
  const [error, setError] = useState("");
  const [result, setResult] = useState("");
  const [busy, setBusy] = useState(false);
  if (!me?.permissions.includes("user.manage_roles")) return null;

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setError("");
    setResult("");
    if (!selected.length) {
      setError("Выберите хотя бы одну роль.");
      return;
    }
    const form = event.currentTarget;
    const comment = String(new FormData(form).get("comment") ?? "");
    setBusy(true);
    try {
      const updated = await apiFetch<Me>("/staff/users/" + userId + "/roles", {
        method: "PUT", body: { roles: selected, comment },
      });
      setSelected(updated.roles);
      onSaved(updated.roles);
      if (me?.id === userId) setMe(updated);
      form.reset();
      setResult("Роли пользователя обновлены.");
    } catch (ex) {
      const errors = fieldErrors(ex);
      setError(errors.form ?? Object.values(errors.fields)[0] ?? "Не удалось изменить роли.");
    } finally { setBusy(false); }
  }

  return <Card>
    <h2 className="mb-2 text-lg font-bold">Управление ролями</h2>
    <p className="mb-4 text-sm text-muted">Отметьте роли, которые должны быть у пользователя. Чтобы снять роль, уберите отметку и сохраните изменения.</p>
    <form method="post" onSubmit={save} className="grid gap-4">
      <fieldset disabled={busy} className="grid gap-2 sm:grid-cols-2">
        <legend className="mb-2 text-sm font-semibold">Роли пользователя</legend>
        {Object.entries(ROLE_LABELS).map(([code, label]) => (
          <label key={code} className="flex min-h-10 items-center gap-3 rounded-lg border border-border px-3 py-2 text-sm">
            <input type="checkbox" name="roles" value={code} checked={selected.includes(code)}
              disabled={code === "super_admin" && me?.id === userId && roles.includes(code)}
              onChange={(event) => {
                setSelected((current) => event.target.checked ? [...current, code] : current.filter((role) => role !== code));
                setError(""); setResult("");
              }} />
            {label}
          </label>
        ))}
      </fieldset>
      <label className="grid gap-1 text-sm font-medium">Комментарий к изменению ролей (обязательно)
        <textarea name="comment" required minLength={3} maxLength={2000} rows={2} disabled={busy}
          className="rounded-lg border border-border bg-surface px-3 py-2 font-normal" />
      </label>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      {result && <p role="status" className="text-sm text-ok">{result}</p>}
      <Button type="submit" loading={busy} className="w-fit">Сохранить роли</Button>
    </form>
  </Card>;
}
