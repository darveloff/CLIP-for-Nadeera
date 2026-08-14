"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import {
  ChartBar,
  CheckCircle,
  MagnifyingGlass,
  SquaresFour,
} from "@phosphor-icons/react";
import { api } from "@/lib/api";
import type { Health, VocabCategory } from "@/lib/types";

const NAV = [
  { href: "/", label: "Search", icon: MagnifyingGlass },
  { href: "/browse", label: "Browse", icon: SquaresFour },
  { href: "/insights", label: "Insights", icon: ChartBar },
  { href: "/review", label: "Review", icon: CheckCircle },
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [health, setHealth] = useState<Health | null>(null);
  const [vocab, setVocab] = useState<VocabCategory[]>([]);
  const [openCat, setOpenCat] = useState<string | null>(null);
  const [incremental, setIncremental] = useState(true);
  const [rebuildLog, setRebuildLog] = useState<string | null>(null);
  const [rebuilding, setRebuilding] = useState(false);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    api.vocabulary().then((v) => setVocab(v.categories)).catch(() => setVocab([]));
  }, []);

  async function rebuild() {
    setRebuilding(true);
    setRebuildLog(null);
    try {
      const res = await api.rebuild(incremental);
      setRebuildLog((res.stdout || "") + (res.stderr || "") || `exit ${res.exit_code}`);
      const next = await api.health();
      setHealth(next);
    } catch (err) {
      setRebuildLog(err instanceof Error ? err.message : "Rebuild failed");
    } finally {
      setRebuilding(false);
    }
  }

  return (
    <div className="relative z-10 min-h-screen">
      <header className="border-b border-line bg-surface/80 backdrop-blur-[8px]">
        <div className="mx-auto flex max-w-6xl items-end justify-between px-6 py-8 md:px-10">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted">
              Marketing library
            </p>
            <h1
              className="mt-1 font-serif text-[40px] leading-[1.1] tracking-[-0.03em] text-ink"
            >
              Clipmarket
            </h1>
          </div>
          <div className="hidden text-right md:block">
            <p className="font-mono text-[11px] text-muted">
              {health
                ? `${health.assets} assets · ${health.clip_search ? "CLIP search" : "lexical fallback"}`
                : "API offline"}
            </p>
            {health && (
              <p className="mt-1 font-mono text-[11px] text-muted">
                {health.model}/{health.pretrained}
              </p>
            )}
          </div>
        </div>
        <nav className="mx-auto flex max-w-6xl gap-1 px-6 pb-0 md:px-10">
          {NAV.map((item) => {
            const active = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2 border-b-2 px-3 py-3 text-[13px] tracking-[-0.01em] transition-colors ${
                  active
                    ? "border-ink text-ink"
                    : "border-transparent text-muted hover:text-ink"
                }`}
              >
                <Icon weight="bold" size={16} />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </header>

      <div className="mx-auto grid max-w-6xl gap-10 px-6 py-12 md:grid-cols-[minmax(0,1fr)_280px] md:px-10 md:py-16">
        <main className="min-w-0">{children}</main>
        <aside className="space-y-10">
          <section>
            <h2 className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
              Vocabulary
            </h2>
            <p className="mt-2 text-[13px] text-muted">
              Closed tag list. Search never invents labels outside this set.
            </p>
            <div className="mt-4 divide-y divide-line border-y border-line">
              {vocab.map((cat) => (
                <div key={cat.id}>
                  <button
                    type="button"
                    onClick={() => setOpenCat(openCat === cat.id ? null : cat.id)}
                    className="flex w-full items-center justify-between py-3 text-left text-[14px] text-ink"
                  >
                    <span className="capitalize">{cat.label}</span>
                    <span className="font-mono text-[12px] text-muted">
                      {openCat === cat.id ? "−" : "+"}
                    </span>
                  </button>
                  {openCat === cat.id && (
                    <ul className="pb-4">
                      {cat.low_confidence && (
                        <li className="mb-2 text-[12px] text-muted">
                          CLIP is unreliable here; matches stay flagged for review.
                        </li>
                      )}
                      {cat.tags.map((t) => (
                        <li
                          key={t.name}
                          className="flex justify-between py-1 text-[13px] text-ink"
                        >
                          <span>{t.name}</span>
                          <span className="font-mono text-[11px] text-muted">
                            {t.confident_matches}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
              Maintenance
            </h2>
            <label className="mt-3 flex items-start gap-2 text-[13px] text-ink">
              <input
                type="checkbox"
                checked={incremental}
                onChange={(e) => setIncremental(e.target.checked)}
                className="mt-1 accent-[#2f3437]"
              />
              Skip unchanged images on rebuild
            </label>
            <button
              type="button"
              onClick={rebuild}
              disabled={rebuilding}
              className="mt-4 bg-[#111111] px-4 py-2 text-[13px] text-white transition-transform hover:bg-[#333333] active:scale-[0.98] disabled:opacity-50"
              style={{ borderRadius: 5 }}
            >
              {rebuilding ? "Rebuilding…" : "Rebuild index"}
            </button>
            {rebuildLog && (
              <pre className="mt-3 max-h-48 overflow-auto border border-line bg-surface p-3 font-mono text-[11px] text-muted">
                {rebuildLog}
              </pre>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
