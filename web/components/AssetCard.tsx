"use client";

import type { Asset } from "@/lib/types";
import { TagChip } from "./TagChip";

export function AssetCard({
  asset,
  onSimilar,
}: {
  asset: Asset;
  onSimilar?: (id: string) => void;
}) {
  return (
    <article
      className="group hairline bg-surface p-3 transition-[box-shadow,transform] duration-200 hover:[box-shadow:0_2px_8px_rgba(0,0,0,0.04)]"
      style={{ borderRadius: 8 }}
    >
      <div className="relative overflow-hidden bg-canvas" style={{ borderRadius: 6 }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={asset.media_url}
          alt={asset.filename}
          className="aspect-[4/3] w-full object-cover opacity-95"
        />
      </div>
      <div className="mt-3 flex items-baseline justify-between gap-2">
        <h3 className="truncate text-[14px] tracking-[-0.01em] text-ink">{asset.filename}</h3>
        {asset.score != null && (
          <span className="font-mono text-[11px] text-muted">{asset.score.toFixed(3)}</span>
        )}
      </div>
      {asset.kind === "keyframe" && asset.source_video && (
        <p className="mt-1 font-mono text-[11px] text-muted">
          keyframe @ {asset.timestamp_s}s of {asset.source_video}
        </p>
      )}
      {asset.near_duplicate_of && (
        <p className="mt-1 text-[12px] text-[color:var(--pale-red-ink)]">
          Near-duplicate of {asset.near_duplicate_of}
        </p>
      )}
      <div className="mt-2 flex flex-wrap gap-1">
        {asset.tags.slice(0, 4).map((t) => (
          <TagChip key={t.tag} tag={t} />
        ))}
      </div>
      {onSimilar && (
        <button
          type="button"
          onClick={() => onSimilar(asset.id)}
          className="mt-3 text-[12px] text-muted underline-offset-4 hover:text-ink hover:underline"
        >
          Find similar
        </button>
      )}
    </article>
  );
}

export function AssetGrid({
  assets,
  onSimilar,
}: {
  assets: Asset[];
  onSimilar?: (id: string) => void;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {assets.map((asset, i) => (
        <div
          key={asset.id}
          className="reveal"
          style={{ animationDelay: `${i * 80}ms` }}
        >
          <AssetCard asset={asset} onSimilar={onSimilar} />
        </div>
      ))}
    </div>
  );
}
