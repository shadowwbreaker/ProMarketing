import { StatusPanel } from "./StatusPanel";

export const metadata = { title: "Статус сервиса — ProMarketing" };

export default function StatusPage() {
  return (
    <div className="max-w-md">
      <h1 className="mb-4 text-2xl font-bold">Статус сервиса</h1>
      <StatusPanel />
    </div>
  );
}
