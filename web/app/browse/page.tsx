"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Asset } from "@/lib/types";
import { AssetGrid } from "@/components/AssetCard";

export default function BrowsePage() {
  const [tag, setTag] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .library(tag || undefined, page)
      .then((res) => {
        setAssets(res.assets);
        setTotal(res.total);
        setPages(res.pages);
        setTags(res.all_tags);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
  }, [tag, page]);

  return (
    <div className="reveal">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="font-serif text-[32px] leading-[1.1] tracking-[-0.03em]">Library</h2>
          <p className="mt-2 text-[14px] text-muted">
            {total} asset{total === 1 ? "" : "s"}
            {tag ? ` tagged “${tag}”` : ""}.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={tag}
            onChange={(e) => {
              setTag(e.target.value);
              setPage(1);
            }}
            className="border border-line bg-surface px-3 py-2 text-[13px] outline-none"
            style={{ borderRadius: 6 }}
          >
            <option value="">Any tag</option>
            {tags.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <a
            href={`/backend/export.csv${tag ? `?tag=${encodeURIComponent(tag)}` : ""}`}
            className="border border-line bg-surface px-3 py-2 text-[13px] text-ink"
            style={{ borderRadius: 6 }}
          >
            Download CSV
          </a>
        </div>
      </div>

      {error && (
        <p className="mt-6 border border-line bg-[color:var(--pale-red)] px-3 py-2 text-[13px] text-[color:var(--pale-red-ink)]">
          {error}
        </p>
      )}

      <div className="mt-10">
        <AssetGrid assets={assets} />
      </div>

      {pages > 1 && (
        <div className="mt-8 flex items-center gap-3 font-mono text-[12px] text-muted">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="disabled:opacity-40"
          >
            Prev
          </button>
          <span>
            {page} / {pages}
          </span>
          <button
            type="button"
            disabled={page >= pages}
            onClick={() => setPage((p) => p + 1)}
            className="disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
