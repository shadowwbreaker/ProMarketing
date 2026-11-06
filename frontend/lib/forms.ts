import { ApiError } from "@/lib/api/client";

/** Map backend validation details {field: [messages]} to {field: message}. */
export function fieldErrors(e: unknown): { form?: string; fields: Record<string, string> } {
  if (!(e instanceof ApiError)) return { form: "Неизвестная ошибка", fields: {} };
  const fields: Record<string, string> = {};
  let form: string | undefined;
  if (e.code === "validation_error") {
    for (const [k, v] of Object.entries(e.details ?? {})) {
      const msg = Array.isArray(v) ? String(v[0]) : String(v);
      if (k === "non_field_errors" || k === "__all__") form = msg;
      else fields[k] = msg;
    }
    if (!form && Object.keys(fields).length === 0) form = e.message;
  } else {
    form = e.message;
  }
  return { form, fields };
}
