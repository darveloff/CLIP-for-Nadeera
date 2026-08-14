export type Tag = {
  tag: string;
  category: string;
  score: number;
  z: number | null;
  needs_review: boolean;
  low_confidence: boolean;
  human_confirmed?: boolean;
};

export type Asset = {
  id: string;
  filename: string;
  kind: "image" | "keyframe" | string;
  source_video: string | null;
  timestamp_s: number | null;
  near_duplicate_of: string | null;
  tags: Tag[];
  score: number | null;
  media_url: string;
};

export type Health = {
  ok: boolean;
  assets: number;
  clip_search: boolean;
  model: string;
  pretrained: string;
  data_dir: string;
};

export type VocabCategory = {
  id: string;
  label: string;
  low_confidence: boolean;
  tags: { name: string; confident_matches: number }[];
};

export type InsightCategory = {
  id: string;
  label: string;
  rows: { tag: string; count: number }[];
};
