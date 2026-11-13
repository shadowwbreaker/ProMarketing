import { apiFetch } from "./client";

export type Meta = { beta: boolean; payment_provider: string };
let cached: Promise<Meta> | null = null;

/** Public site flags (beta mode), fetched once per page load. */
export const getMeta = () => (cached ??= apiFetch<Meta>("/meta").catch(() => ({ beta: false, payment_provider: "" })));
