export type SourceId =
  | "myanimelistanime"
  | "themoviedbtv"
  | "themoviedbmovie"
  | "myanimelistmanga"
  | "openlibrary";

export type SpoilerLevel = "light" | "standard" | "full";

export interface SourceOption {
  id: SourceId;
  label: string;
  eyebrow: string;
  description: string;
  accent: string;
}

export interface SearchResult {
  id: string;
  title: string;
  subtitle?: string | null;
  source: SourceId;
  source_label: string;
  media_type: string;
  image_url?: string | null;
  external_url?: string | null;
  supports_segments: boolean;
}

export interface MediaSummary {
  id: string;
  title: string;
  subtitle?: string | null;
  source: SourceId;
  source_label: string;
  media_type: string;
  image_url?: string | null;
  external_url?: string | null;
}

export interface TargetOption {
  id: string;
  type: "title" | "episode";
  label: string;
  description?: string | null;
  season_number?: number | null;
  episode_number?: number | null;
}

export interface TargetsPayload {
  media: MediaSummary;
  target_mode: "title" | "segment";
  targets: TargetOption[];
}

export interface SummaryFields {
  characters: string[];
  key_events: string[];
  plot_points: string[];
  skip_context: string;
}

export interface SummaryPayload {
  media: MediaSummary;
  target: TargetOption;
  summary: SummaryFields;
  meta: {
    spoiler_level: SpoilerLevel;
    source_name: string;
    generated_at: string;
    attribution: {
      label: string;
      url?: string | null;
    };
  };
}

export interface ApiErrorPayload {
  errors?: {
    code?: string;
    detail?: string;
  };
}

export interface RecentSummary {
  stored_at: string;
  payload: SummaryPayload;
}

export const SOURCE_OPTIONS: SourceOption[] = [
  {
    id: "myanimelistanime",
    label: "Anime",
    eyebrow: "Episode mode",
    description: "Search anime series and summarize specific episodes.",
    accent: "from-amber-400 via-orange-500 to-rose-500",
  },
  {
    id: "themoviedbtv",
    label: "TV",
    eyebrow: "Episode mode",
    description: "Search TV shows and choose the exact episode you want to skip.",
    accent: "from-cyan-400 via-sky-500 to-blue-600",
  },
  {
    id: "themoviedbmovie",
    label: "Movies",
    eyebrow: "Title mode",
    description: "Get a spoiler-controlled summary of the whole film.",
    accent: "from-emerald-400 via-teal-500 to-cyan-600",
  },
  {
    id: "myanimelistmanga",
    label: "Manga",
    eyebrow: "Title mode",
    description: "Use MyAnimeList synopses for title-level manga summaries.",
    accent: "from-fuchsia-500 via-pink-500 to-rose-500",
  },
  {
    id: "openlibrary",
    label: "Books",
    eyebrow: "Title mode",
    description: "Use OpenLibrary metadata for book-level summaries.",
    accent: "from-lime-400 via-green-500 to-emerald-600",
  },
];

export const SPOILER_LEVELS: Array<{
  id: SpoilerLevel;
  label: string;
  description: string;
}> = [
  {
    id: "light",
    label: "Light",
    description: "Minimum viable context with restrained reveals.",
  },
  {
    id: "standard",
    label: "Standard",
    description: "Balanced recap of the major beats and consequences.",
  },
  {
    id: "full",
    label: "Full",
    description: "Complete spoilers with direct downstream context.",
  },
];
