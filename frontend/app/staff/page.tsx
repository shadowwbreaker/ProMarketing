"use client";

import Link from "next/link";

export default function StaffHome() {
  return (
    <div>
      <h1 className="text-2xl font-bold">Служебный раздел</h1>
      <p className="mt-2 text-sm text-muted">Начните с <Link href="/staff/disputes" className="text-accent">очереди споров</Link> или <Link href="/staff/tickets" className="text-accent">обращений</Link>.</p>
    </div>
  );
}
