import Link from "next/link";
import { FEATURES, GROUP_COLOR, GROUP_LABEL } from "@/lib/features";

export default function Home() {
  return (
    <div className="mx-auto max-w-5xl p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-neutral-900 dark:text-neutral-50">
          ICALORA<span className="text-rose-600">-</span>LABS
        </h1>
        <p className="mt-1 text-neutral-500 dark:text-neutral-400">
          Toolkit integritas akademik oleh MRH INNOVEX — 13 fitur dalam satu platform.
        </p>
      </header>

      <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((f) => (
          <Link
            key={f.slug}
            href={`/features/${f.slug}`}
            className="group rounded-xl border border-neutral-200 p-4 transition hover:border-neutral-900 hover:shadow-sm dark:border-neutral-800 dark:hover:border-neutral-500"
          >
            <div className="mb-2 flex items-center gap-2">
              <span className={`h-2 w-2 rounded-full ${GROUP_COLOR[f.group]}`} />
              <span className="text-[11px] uppercase tracking-wide text-neutral-400 dark:text-neutral-500">
                {GROUP_LABEL[f.group]}
              </span>
            </div>
            <div className="font-semibold text-neutral-800 group-hover:text-neutral-900 dark:text-neutral-200 dark:group-hover:text-white">
              {f.name}
            </div>
            <div className="mt-1 text-xs text-neutral-400 dark:text-neutral-500">
              Fase {f.phase} · {f.status === "active" ? "Aktif" : "Direncanakan"}
            </div>
          </Link>
        ))}
      </section>
    </div>
  );
}
