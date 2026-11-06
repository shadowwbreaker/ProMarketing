import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { apiFetch, ApiError } from "@/lib/api/client";
import { formatMoney } from "@/lib/format";
import { StatusPanel } from "@/app/status/StatusPanel";
import { Button } from "@/components/ui/Button";

afterEach(() => vi.restoreAllMocks());

describe("apiFetch", () => {
  it("parses unified backend error format", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "rate_limited", message: "Слишком часто", details: {}, request_id: "r1" } }), {
        status: 429,
      }),
    );
    await expect(apiFetch("/x")).rejects.toMatchObject({ status: 429, code: "rate_limited", requestId: "r1" });
  });

  it("maps network failures", async () => {
    vi.spyOn(global, "fetch").mockRejectedValue(new TypeError("fail"));
    const err = (await apiFetch("/x").catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("network_error");
  });
});

describe("format", () => {
  it("formats kopecks as rubles", () => {
    expect(formatMoney(150000).replace(/\s/g, " ")).toContain("1 500");
  });
});

describe("StatusPanel", () => {
  it("shows loading then backend status", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ status: "ok", checks: { database: "ok", cache: "ok" } }), { status: 200 }),
    );
    render(<StatusPanel />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("работает")).toBeInTheDocument());
  });

  it("shows error state with retry", async () => {
    vi.spyOn(global, "fetch").mockRejectedValue(new TypeError("down"));
    render(<StatusPanel />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Нет связи с сервером"));
    expect(screen.getByText("Повторить")).toBeInTheDocument();
  });
});

describe("Button", () => {
  it("is disabled while loading", () => {
    render(<Button loading>Сохранить</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
