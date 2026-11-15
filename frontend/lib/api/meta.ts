import { apiFetch } from "./client";

export type Meta = { beta: boolean; payment_provider: string; document_attachments?: boolean };
let cached: Promise<Meta> | null = null;

/** Public site flags (beta mode), fetched once per page load. */
export const getMeta = (): Promise<Meta> => (cached ??= apiFetch<Meta>("/meta").catch(() => ({ beta: false, payment_provider: "", document_attachments: false })));
