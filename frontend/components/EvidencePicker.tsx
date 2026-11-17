"use client";

import { useEffect, useState } from "react";
import { useToast } from "@/components/ui/Toast";
import { uploadFile } from "@/lib/api/chat";
import type { Evidence } from "@/lib/api/disputes";
import { getMeta } from "@/lib/api/meta";
import { fieldErrors } from "@/lib/forms";

export function EvidencePicker({ value, onChange }: { value: Evidence[]; onChange: (e: Evidence[]) => void }) {
  const toast = useToast();
  const [documentAttachments, setDocumentAttachments] = useState(false);
  useEffect(() => { void getMeta().then((meta) => setDocumentAttachments(Boolean(meta.document_attachments))).catch(() => {}); }, []);
  return (
    <div className="flex flex-col gap-1 text-xs">
      <label className="cursor-pointer text-accent">
        {documentAttachments ? "+ Скриншот, видео или PDF" : "+ Скриншот"}
        <input type="file" className="hidden" accept={documentAttachments ? "image/png,image/jpeg,image/gif,image/webp,application/pdf,video/mp4" : "image/png,image/jpeg,image/gif,image/webp"} onChange={async (e) => {
          const f = e.target.files?.[0];
          if (!f) return;
          try {
            const up = await uploadFile(f);
            onChange([...value, { attachment: up.id, description: up.name }]);
          } catch (ex) { toast(fieldErrors(ex).form ?? "Ошибка загрузки", "error"); }
        }} />
      </label>
      <button type="button" className="self-start text-accent" onClick={() => {
        const url = prompt("Ссылка-доказательство");
        if (url) onChange([...value, { url, description: "ссылка" }]);
      }}>+ Ссылка</button>
      {value.map((e, i) => <span key={i} className="text-muted">📎 {e.description || e.url}</span>)}
    </div>
  );
}
