export interface SearchResult {
  name: string;
  kind: string;
  type_signature: string;
  statement: string;
  docstring: string;
  module_path: string;
  library: string;
  file_path: string;
  line_number: number;
  github_url: string;
  chapter: string;
  score: number;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
  elapsed_ms: number;
}

export interface StatsResponse {
  total_points: number;
  libraries: Record<string, number>;
  kinds: Record<string, number>;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function searchDeclarations(
  q: string,
  opts: { limit?: number; lib?: string; kind?: string; chapter?: string } = {}
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q });
  if (opts.limit)   params.set("limit", String(opts.limit));
  if (opts.lib)     params.set("lib", opts.lib);
  if (opts.kind)    params.set("kind", opts.kind);
  if (opts.chapter) params.set("chapter", opts.chapter);

  const res = await fetch(`${API_BASE}/search?${params}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getStats(): Promise<StatsResponse> {
  const res = await fetch(`${API_BASE}/stats`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface SiteStats {
  active_now: number;
  total_visitors: number;
  total_page_views: number;
}

export async function pingVisit(visitorId: string): Promise<void> {
  await fetch(`${API_BASE}/visit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ visitor_id: visitorId }),
    cache: "no-store",
  }).catch(() => {});
}

export async function pingPageview(visitorId: string, path: string): Promise<void> {
  await fetch(`${API_BASE}/pageview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ visitor_id: visitorId, path }),
    cache: "no-store",
  }).catch(() => {});
}

export async function getSiteStats(): Promise<SiteStats> {
  const res = await fetch(`${API_BASE}/site-stats`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const LIBRARIES = ["stdlib", "mathcomp", "geocoq","mathcomp-analysis", "unimath", "hott"] as const;
export type Library = typeof LIBRARIES[number];

// Currently indexed & searchable. We only ship a library once it has high-quality
// natural-language descriptions.
export const ACTIVE_LIBRARIES = ["mathcomp", "stdlib", "mathcomp-analysis", "geocoq"] as const;

// GeoCoq Tarski_dev chapters (Ch02–Ch16). Used for the geocoq-only chapter filter.
export const GEOCOQ_CHAPTERS = [
  "Ch02", "Ch03", "Ch04", "Ch05", "Ch06", "Ch07", "Ch08", "Ch09",
  "Ch10", "Ch11", "Ch12", "Ch13", "Ch14", "Ch15", "Ch16",
] as const;

export const KINDS = [
  "Lemma", "Theorem", "Corollary", "Proposition",
  "Definition", "Fixpoint", "Inductive", "Record",
  "Class", "Instance", "Notation", "Axiom",
] as const;

export const LIBRARY_LABELS: Record<string, string> = {
  stdlib:   "Stdlib",
  mathcomp: "MathComp",
  geocoq:   "GeoCoq",
  unimath:  "UniMath",
  hott:     "HoTT",
  "mathcomp-analysis": "MathComp-Analysis",
};

export const EXAMPLE_QUERIES = [
  "multiplication in a ring is associative",
  "a group homomorphism maps the identity to the identity",
  "the determinant of a product is the product of determinants",
  "convert a row vector into a polynomial",
  "every finite integral domain is a field",
  "the order of an element divides the order of the group",
  "polynomial evaluation is a ring morphism",
  "the gcd divides both of its arguments",
];

// ---------------------------------------------------------------------------
// FLT search (Fermat's Last Theorem page)
// ---------------------------------------------------------------------------

export interface FLTResult {
  name: string;
  module: string;
  title: string;
  summary: string; // HTML generated from the Lean source
  statement: string; // authoritative Lean statement
  stage: number | null;
  stage_name: string;
  aliases: string[];
  score: number;
  distance: number | null; // hops from the matched seed (used-mode only)
  n_cites: number;
  n_cited_by: number;
  url: string;
}

export interface FLTSearchResponse {
  query: string;
  mode: "what" | "used";
  seeds: FLTResult[];
  results: FLTResult[];
  groups: Record<string, string[]>;
  total: number;
  elapsed_ms: number;
}

export interface FLTStatsResponse {
  total_theorems: number;
  total_edges: number;
  stages: Record<string, number>;
}

export async function searchFLT(
  q: string,
  mode: "what" | "used" = "what",
  limit = 10
): Promise<FLTSearchResponse> {
  const params = new URLSearchParams({ q, mode, limit: String(limit) });
  const res = await fetch(`${API_BASE}/flt/search?${params}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getFLTStats(): Promise<FLTStatsResponse> {
  const res = await fetch(`${API_BASE}/flt/stats`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function getFLTTheorem(name: string): Promise<FLTResult> {
  const params = new URLSearchParams({ name });
  const res = await fetch(`${API_BASE}/flt/theorem?${params}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
