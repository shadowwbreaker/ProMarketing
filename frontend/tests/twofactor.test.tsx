import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { TwoFactorPanel } from "@/app/account/TwoFactorPanel";
import { confirm2fa, get2fa, setup2fa } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";

const toast = vi.hoisted(() => vi.fn());
vi.mock("@/components/ui/Toast", () => ({ useToast: () => toast }));
vi.mock("@/lib/api/auth", () => ({
  get2fa: vi.fn(), setup2fa: vi.fn(), confirm2fa: vi.fn(), disable2fa: vi.fn(),
}));

const secret = "JBSWY3DPEHPK3PXP";
const uri = "otpauth://totp/YourVideoTeam:test%40example.com?secret=" + secret + "&issuer=YourVideoTeam";
const qrName = "QR-код для подключения двухфакторной защиты";

beforeEach(() => {
  vi.mocked(get2fa).mockResolvedValue({ enabled: false, required: false });
  vi.mocked(setup2fa).mockResolvedValue({ secret, otpauth_url: uri });
});
afterEach(() => vi.resetAllMocks());

async function showSetup() {
  render(<TwoFactorPanel />);
  fireEvent.click(await screen.findByRole("button", { name: "Включить" }));
  return screen.findByRole("img", { name: qrName });
}

describe("TwoFactorPanel QR setup", () => {
  it("renders a local QR and keeps the matching manual key below it", async () => {
    const qr = await showSetup();
    expect(qr.tagName.toLowerCase()).toBe("svg");
    expect(qr.querySelectorAll("path").length).toBeGreaterThan(0);
    expect(qr.querySelector("image")).toBeNull();
    const manual = screen.getByText(secret);
    expect(qr.compareDocumentPosition(manual) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByRole("link", { name: "Открыть в приложении-аутентификаторе" })).toHaveAttribute("href", uri);
    const code = screen.getByLabelText("Шестизначный код из приложения");
    expect(code).toHaveAttribute("autoComplete", "one-time-code");
    expect(code).toHaveAttribute("pattern", "[0-9]{6}");
    expect(confirm2fa).not.toHaveBeenCalled();
  });

  it("retains the QR on a failed code and removes secrets only after confirmation", async () => {
    vi.mocked(confirm2fa).mockRejectedValueOnce(new ApiError(400, "invalid_otp", "Неверный код"));
    vi.mocked(confirm2fa).mockResolvedValueOnce({ enabled: true });
    await showSetup();
    fireEvent.change(screen.getByLabelText("Шестизначный код из приложения"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить" }));
    await waitFor(() => expect(toast).toHaveBeenCalledWith("Неверный код", "error"));
    expect(screen.getByRole("img", { name: qrName })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Отключить" })).toBeNull();
    await waitFor(() => expect(screen.getByRole("button", { name: "Подтвердить" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить" }));
    await screen.findByRole("button", { name: "Отключить" });
    expect(confirm2fa).toHaveBeenLastCalledWith("123456");
    expect(screen.queryByRole("img", { name: qrName })).toBeNull();
    expect(screen.queryByText(secret)).toBeNull();
  });

  it("does not replace the secret on repeated setup clicks", async () => {
    let finish!: (value: { secret: string; otpauth_url: string }) => void;
    vi.mocked(setup2fa).mockReturnValue(new Promise(resolve => { finish = resolve; }));
    render(<TwoFactorPanel />);
    const enable = await screen.findByRole("button", { name: "Включить" });
    fireEvent.click(enable);
    fireEvent.click(enable);
    expect(setup2fa).toHaveBeenCalledTimes(1);
    finish({ secret, otpauth_url: uri });
    await screen.findByRole("img", { name: qrName });
  });

  it("does not reveal provisioning information for an already enabled factor", async () => {
    vi.mocked(get2fa).mockResolvedValue({ enabled: true, required: false });
    render(<TwoFactorPanel />);
    await screen.findByRole("button", { name: "Отключить" });
    expect(setup2fa).not.toHaveBeenCalled();
    expect(screen.queryByRole("img", { name: qrName })).toBeNull();
    expect(screen.queryByText(secret)).toBeNull();
  });
});
