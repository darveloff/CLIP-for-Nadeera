"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Asset } from "@/lib/types";
import { AssetGrid } from "@/components/AssetCard";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [exclude, setExclude] = useState("");
  const [tag, setTag] = useState("");
  const [topK, setTopK] = useState(12);
  const [minScore, setMinScore] = useState(0.15);
  const [groupVideos, setGroupVideos] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [groups, setGroups] = useState<
    { source_video: string | null; best: Asset; hits: Asset[] }[]
  >([]);
  const [similarTo, setSimilarTo] = useState<Asset | null>(null);

  async function runSearch(e?: React.FormEvent) {
    e?.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setSimilarTo(null);
    try {
      const res = await api.search({
        query,
        exclude: exclude || undefined,
        tag_filter: tag || undefined,
        top_k: topK,
        min_score: minScore,
        group_videos: groupVideos,
      });
      setNote(res.note ?? null);
      if (res.grouped && res.groups) {
        setGroups(res.groups);
        setAssets([]);
      } else {
        setAssets(res.assets ?? []);
        setGroups([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  async function findSimilar(id: string) {
    setLoading(true);
    setError(null);
    try {
      const res = await api.similar(id);
      setSimilarTo(res.source);
      setAssets(res.assets);
      setGroups([]);
      setNote(res.mode === "lexical" ? "Ranked by overlapping tags (CLIP not loaded)." : null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Similar search failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="reveal">
      <p className="max-w-xl text-[15px] text-muted">
        Describe a shot the way you would brief a photographer. Ranking uses CLIP when
        the index is present; otherwise it matches against tags and filenames.
      </p>

      <form onSubmit={runSearch} className="mt-8 space-y-4">
        <label className="block">
          <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
            Query
          </span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="an outdoor team photo, bright and energetic"
            className="mt-2 w-full border border-line bg-surface px-3 py-3 text-[15px] text-ink outline-none placeholder:text-muted/70 focus:border-ink"
            style={{ borderRadius: 6 }}
          />
        </label>
        <label className="block">
          <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
            Exclude
          </span>
          <input
            value={exclude}
            onChange={(e) => setExclude(e.target.value)}
            placeholder="people"
            className="mt-2 w-full border border-line bg-surface px-3 py-2 text-[14px] text-ink outline-none placeholder:text-muted/70 focus:border-ink"
            style={{ borderRadius: 6 }}
          />
        </label>
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="block">
            <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
              Tag filter
            </span>
            <input
              value={tag}
              onChange={(e) => setTag(e.target.value)}
              placeholder="an office"
              className="mt-2 w-full border border-line bg-surface px-3 py-2 text-[14px] outline-none focus:border-ink"
              style={{ borderRadius: 6 }}
            />
          </label>
          <label className="block">
            <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
              Results {topK}
            </span>
            <input
              type="range"
              min={4}
              max={40}
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="mt-3 w-full accent-[#2f3437]"
            />
          </label>
          <label className="block">
            <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
              Min similarity {minScore.toFixed(2)}
            </span>
            <input
              type="range"
              min={0}
              max={0.4}
              step={0.01}
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="mt-3 w-full accent-[#2f3437]"
            />
          </label>
        </div>
        <label className="flex items-center gap-2 text-[13px] text-ink">
          <input
            type="checkbox"
            checked={groupVideos}
            onChange={(e) => setGroupVideos(e.target.checked)}
            className="accent-[#2f3437]"
          />
          Group video hits by source clip
        </label>
        <button
          type="submit"
          disabled={loading}
          className="bg-[#111111] px-5 py-2.5 text-[13px] text-white transition-transform hover:bg-[#333333] active:scale-[0.98] disabled:opacity-50"
          style={{ borderRadius: 5 }}
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      {error && (
        <p className="mt-6 border border-line bg-[color:var(--pale-red)] px-3 py-2 text-[13px] text-[color:var(--pale-red-ink)]">
          {error}
        </p>
      )}
      {note && <p className="mt-6 text-[13px] text-muted">{note}</p>}

      {similarTo && (
        <div className="mt-10 border-b border-line pb-6">
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
            Similar to
          </p>
          <div className="mt-3 flex items-center justify-between">
            <p className="font-serif text-[28px] tracking-[-0.03em]">{similarTo.filename}</p>
            <button
              type="button"
              onClick={() => setSimilarTo(null)}
              className="text-[12px] text-muted underline-offset-4 hover:text-ink hover:underline"
            >
              Clear
            </button>
          </div>
        </div>
      )}

      <div className="mt-10">
        {groups.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2">
            {groups.map((g, i) => (
              <article
                key={`${g.source_video ?? g.best.id}-${i}`}
                className="hairline bg-surface p-3 reveal"
                style={{ borderRadius: 8, animationDelay: `${i * 80}ms` }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={g.best.media_url}
                  alt={g.best.filename}
                  className="aspect-[4/3] w-full object-cover"
                />
                <h3 className="mt-3 text-[14px]">
                  {g.source_video ?? g.best.filename}
                </h3>
                {g.source_video && (
                  <p className="font-mono text-[11px] text-muted">
                    {g.hits.length} matching moment{g.hits.length === 1 ? "" : "s"} at{" "}
                    {g.hits.map((h) => `${h.timestamp_s}s`).join(", ")}
                  </p>
                )}
              </article>
            ))}
          </div>
        ) : (
          <AssetGrid assets={assets} onSimilar={findSimilar} />
        )}
        {!loading && assets.length === 0 && groups.length === 0 && query && !error && (
          <p className="text-[14px] text-muted">
            No strong match. Try rephrasing, or lower the minimum similarity.
          </p>
        )}
      </div>
    </div>
  );
}
