import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ApiError } from "@/lib/api/client";
import { fieldErrors } from "@/lib/forms";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: push }), useSearchParams: () => new URLSearchParams() }));

import LoginPage from "@/app/login/page";
import { AuthProvider } from "@/lib/auth/AuthProvider";

afterEach(() => vi.restoreAllMocks());

describe("fieldErrors", () => {
  it("maps validation details to fields", () => {
    const e = new ApiError(400, "validation_error", "Ошибка валидации", { email: ["Неверный email"], non_field_errors: ["Общая"] });
    expect(fieldErrors(e)).toEqual({ form: "Общая", fields: { email: "Неверный email" } });
  });
  it("uses message for domain errors", () => {
    expect(fieldErrors(new ApiError(400, "invalid_credentials", "Неверный email или пароль")).form).toBe("Неверный email или пароль");
  });
});

describe("LoginPage", () => {
  it("shows backend error on wrong credentials", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async (url) => {
      const u = String(url);
      if (u.endsWith("/auth/session")) return new Response(JSON.stringify({ user: null }));
      return new Response(JSON.stringify({ error: { code: "invalid_credentials", message: "Неверный email или пароль", details: {} } }), { status: 400 });
    });
    render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>,
    );
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "a@b.ru" } });
    fireEvent.change(screen.getByLabelText("Пароль"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Войти" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Неверный email или пароль"));
    expect(push).not.toHaveBeenCalled();
  });
});
