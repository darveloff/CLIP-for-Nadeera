"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Asset } from "@/lib/types";
import { TagChip } from "@/components/TagChip";

export default function ReviewPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [currentId, setCurrentId] = useState<string>("");
  const [pending, setPending] = useState<string[]>([]);
  const [saved, setSaved] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api
      .review()
      .then((res) => {
        setAssets(res.assets);
        setCurrentId((id) => id || res.assets[0]?.id || "");
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
  }

  useEffect(() => {
    load();
  }, []);

  const current = assets.find((a) => a.id === currentId);

  async function save() {
    if (!current || pending.length === 0) return;
    setError(null);
    try {
      const res = await api.saveReview(current.id, pending);
      setSaved(`Saved ${res.saved} confirmation${res.saved === 1 ? "" : "s"}.`);
      setPending([]);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  }

  return (
    <div className="reveal">
      <h2 className="font-serif text-[32px] leading-[1.1] tracking-[-0.03em]">Review</h2>
      <p className="mt-3 max-w-xl text-[14px] text-muted">
        {assets.length} asset{assets.length === 1 ? "" : "s"} have at least one flagged
        tag. Confirming writes to metadata.json without re-embedding.
      </p>

      {error && (
        <p className="mt-6 border border-line bg-[color:var(--pale-red)] px-3 py-2 text-[13px] text-[color:var(--pale-red-ink)]">
          {error}
        </p>
      )}
      {saved && (
        <p className="mt-6 border border-line bg-[color:var(--pale-green)] px-3 py-2 text-[13px] text-[color:var(--pale-green-ink)]">
          {saved}
        </p>
      )}

      {assets.length === 0 && !error && (
        <p className="mt-10 text-[14px] text-muted">Nothing flagged for review.</p>
      )}

      {current && (
        <div className="mt-10 grid gap-8 md:grid-cols-[minmax(0,1fr)_240px]">
          <div>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={current.media_url}
              alt={current.filename}
              className="w-full max-w-md border border-line object-cover"
              style={{ borderRadius: 8 }}
            />
            <p className="mt-3 text-[14px]">{current.filename}</p>
            <div className="mt-2 flex flex-wrap gap-1">
              {current.tags.map((t) => (
                <TagChip key={t.tag} tag={t} />
              ))}
            </div>
          </div>
          <div>
            <label className="block font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
              Asset
            </label>
            <select
              value={currentId}
              onChange={(e) => {
                setCurrentId(e.target.value);
                setPending([]);
                setSaved(null);
              }}
              className="mt-2 w-full border border-line bg-surface px-3 py-2 text-[13px]"
              style={{ borderRadius: 6 }}
            >
              {assets.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.filename}
                </option>
              ))}
            </select>
            <ul className="mt-6 space-y-3">
              {current.tags
                .filter((t) => t.needs_review && !t.human_confirmed)
                .map((t) => (
                  <li key={t.tag}>
                    <label className="flex items-start gap-2 text-[13px]">
                      <input
                        type="checkbox"
                        checked={pending.includes(t.tag)}
                        onChange={(e) =>
                          setPending((prev) =>
                            e.target.checked
                              ? [...prev, t.tag]
                              : prev.filter((x) => x !== t.tag),
                          )
                        }
                        className="mt-1 accent-[#2f3437]"
                      />
                      <span>
                        Confirm “{t.tag}” ({t.score.toFixed(2)})
                      </span>
                    </label>
                  </li>
                ))}
            </ul>
            <button
              type="button"
              disabled={pending.length === 0}
              onClick={save}
              className="mt-6 bg-[#111111] px-4 py-2 text-[13px] text-white hover:bg-[#333333] active:scale-[0.98] disabled:opacity-40"
              style={{ borderRadius: 5 }}
            >
              Save corrections
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
