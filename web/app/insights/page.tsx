"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { InsightCategory } from "@/lib/types";

export default function InsightsPage() {
  const [cats, setCats] = useState<InsightCategory[]>([]);
  const [dupes, setDupes] = useState<{ id: string; filename: string; of: string }[]>([]);
  const [meta, setMeta] = useState({ assets: 0, images: 0, keyframes: 0 });
  const [report, setReport] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .insights()
      .then((res) => {
        setCats(res.by_category);
        setDupes(res.duplicates);
        setReport(res.report_markdown);
        setMeta({
          assets: res.asset_count,
          images: res.image_count,
          keyframes: res.keyframe_count,
        });
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
  }, []);

  return (
    <div className="reveal">
      <h2 className="font-serif text-[32px] leading-[1.1] tracking-[-0.03em]">
        Content mix
      </h2>
      <p className="mt-3 max-w-xl text-[14px] text-muted">
        {meta.assets} indexed files ({meta.images} stills, {meta.keyframes} video
        keyframes). Counts use confident tags only.
      </p>

      {error && (
        <p className="mt-6 border border-line bg-[color:var(--pale-red)] px-3 py-2 text-[13px] text-[color:var(--pale-red-ink)]">
          {error}
        </p>
      )}

      <div className="mt-10 grid gap-4 md:grid-cols-2">
        {cats.map((cat, i) => {
          const max = Math.max(1, ...cat.rows.map((r) => r.count));
          return (
            <section
              key={cat.id}
              className="hairline bg-surface p-6 reveal"
              style={{ borderRadius: 12, animationDelay: `${i * 80}ms` }}
            >
              <h3 className="capitalize font-serif text-[22px] tracking-[-0.03em]">
                {cat.label}
              </h3>
              <ul className="mt-5 space-y-3">
                {cat.rows.map((row) => (
                  <li key={row.tag}>
                    <div className="flex justify-between text-[13px]">
                      <span>{row.tag}</span>
                      <span className="font-mono text-[11px] text-muted">{row.count}</span>
                    </div>
                    <div className="mt-1 h-[3px] bg-line">
                      <div
                        className="h-full bg-ink/70"
                        style={{ width: `${(row.count / max) * 100}%` }}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>

      {dupes.length > 0 && (
        <section className="mt-12">
          <h3 className="font-serif text-[22px] tracking-[-0.03em]">Near-duplicates</h3>
          <ul className="mt-4 divide-y divide-line border-y border-line">
            {dupes.map((d) => (
              <li key={d.id} className="flex justify-between py-3 text-[13px]">
                <span className="font-mono">{d.filename}</span>
                <span className="text-muted">matches {d.of}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {report && (
        <section className="mt-12">
          <h3 className="font-serif text-[22px] tracking-[-0.03em]">Written report</h3>
          <pre className="mt-4 whitespace-pre-wrap border border-line bg-surface p-6 text-[13px] leading-relaxed text-ink" style={{ borderRadius: 8 }}>
            {report}
          </pre>
        </section>
      )}
    </div>
  );
}
