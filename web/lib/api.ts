import type { Asset, Health, InsightCategory, VocabCategory } from "./types";

const BASE = "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>("/backend/health"),
  library: (tag?: string, page = 1) =>
    request<{
      total: number;
      page: number;
      pages: number;
      clip_search: boolean;
      assets: Asset[];
      all_tags: string[];
    }>(`/backend/library?page=${page}${tag ? `&tag=${encodeURIComponent(tag)}` : ""}`),
  vocabulary: () => request<{ categories: VocabCategory[] }>("/backend/vocabulary"),
  insights: () =>
    request<{
      by_category: InsightCategory[];
      duplicates: { id: string; filename: string; of: string }[];
      report_markdown: string;
      asset_count: number;
      keyframe_count: number;
      image_count: number;
    }>("/backend/insights"),
  search: (body: {
    query: string;
    exclude?: string;
    tag_filter?: string;
    top_k: number;
    min_score: number;
    group_videos: boolean;
  }) =>
    request<{
      mode: string;
      grouped: boolean;
      assets?: Asset[];
      groups?: { source_video: string | null; best: Asset; hits: Asset[] }[];
      note?: string;
    }>("/backend/search", { method: "POST", body: JSON.stringify(body) }),
  similar: (asset_id: string) =>
    request<{ mode: string; source: Asset; assets: Asset[] }>("/backend/similar", {
      method: "POST",
      body: JSON.stringify({ asset_id }),
    }),
  review: () => request<{ total: number; assets: Asset[] }>("/backend/review"),
  saveReview: (asset_id: string, confirm_tags: string[]) =>
    request<{ saved: number; asset: Asset }>("/backend/review", {
      method: "POST",
      body: JSON.stringify({ asset_id, confirm_tags }),
    }),
  rebuild: (incremental: boolean) =>
    request<{ ok: boolean; exit_code: number; stdout: string; stderr: string }>(
      "/backend/rebuild",
      { method: "POST", body: JSON.stringify({ incremental }) },
    ),
};
