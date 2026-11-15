import type { ReactNode } from "react";
import Link from "next/link";

type LegalSection = { id: string; title: string; body: ReactNode };

export const legalLink = "font-medium text-accent underline underline-offset-2";
const email = "yourvideoteam.agency@gmail.com";

export function LegalDocument({ title, intro, sections }: {
  title: string;
  intro: string;
  sections: LegalSection[];
}) {
  return (
    <article className="mx-auto max-w-3xl space-y-7">
      <header>
        <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">{title}</h1>
        <p className="mt-3 text-muted">{intro}</p>
      </header>
      <nav aria-label="Разделы документа" className="flex flex-wrap gap-2">
        {sections.map(({ id, title }) => (
          <a key={id} href={`#${id}`} className="rounded-lg border border-border px-3 py-2.5 text-sm font-medium text-accent hover:bg-bg">
            {title}
          </a>
        ))}
      </nav>
      {sections.map(({ id, title, body }) => (
        <section key={id} id={id} className="scroll-mt-24 border-t border-border pt-5">
          <h2 className="text-xl font-bold">{title}</h2>
          <div className="mt-3 space-y-3 leading-relaxed">{body}</div>
        </section>
      ))}
    </article>
  );
}

export function LegalContact() {
  return (
    <p>
      Для связи с командой беты напишите на <a className={`${legalLink} break-words`} href={`mailto:${email}`}>{email}</a>.
      Из своей учётной записи также можно отправить <Link className={legalLink} href="/support">обращение в поддержку</Link>.
    </p>
  );
}
