"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Radio, Eye } from "lucide-react";
import { getSiteStats, getStats, SiteStats, StatsResponse, LIBRARY_LABELS } from "@/lib/api";

const POLL_MS = 5_000;

// Computed from deploy/declarations.enriched.jsonl on 2026-09-29 — a snapshot,
// not a live query (the API doesn't expose per-library description coverage).
// Re-run the same count after a reindex if the corpus changes materially.
const LIBRARY_ANALYSIS = [
  { lib: "mathcomp", count: 19448, share: 43.8, descPct: 96.1 },
  { lib: "stdlib", count: 13735, share: 30.9, descPct: 100.0 },
  { lib: "mathcomp-analysis", count: 8994, share: 20.2, descPct: 100.0 },
  { lib: "geocoq", count: 2263, share: 5.1, descPct: 100.0 },
];

const TOP_KINDS = [
  { kind: "Lemma", count: 33335, share: 75.0 },
  { kind: "Definition", count: 6165, share: 13.9 },
  { kind: "Let", count: 1527, share: 3.4 },
  { kind: "Theorem", count: 1428, share: 3.2 },
  { kind: "Fact", count: 783, share: 1.8 },
  { kind: "Fixpoint", count: 559, share: 1.3 },
];

function StatCard({
  icon,
  label,
  value,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-6 flex flex-col gap-2">
      <div className="flex items-center gap-2 text-[var(--muted)] text-sm">
        {icon}
        {label}
      </div>
      <div className="text-4xl font-bold text-[var(--text)] tabular-nums">{value}</div>
      {hint && <div className="text-xs text-[var(--muted2)]">{hint}</div>}
    </div>
  );
}

export default function StatsPage() {
  const [site, setSite] = useState<SiteStats | null>(null);
  const [index, setIndex] = useState<StatsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const poll = () => {
      getSiteStats()
        .then((s) => !cancelled && (setSite(s), setError(null)))
        .catch(() => !cancelled && setError("Could not reach the API."));
    };

    poll();
    getStats().then((s) => !cancelled && setIndex(s)).catch(() => {});
    const interval = setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <main className="max-w-3xl mx-auto px-6 py-12">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-sm text-[var(--muted)] hover:text-[var(--text)] transition-colors mb-8"
      >
        <ArrowLeft size={14} />
        Back to search
      </Link>

      <h1 className="text-3xl font-bold text-[var(--text)] tracking-tight mb-8">Site stats</h1>

      {error && (
        <p className="text-sm text-red-500 mb-6">{error}</p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-10">
        <StatCard
          icon={<Radio size={14} className="text-emerald-500" />}
          label="Active right now"
          value={site ? site.active_now.toLocaleString() : "…"}
          hint="Heartbeat in the last 90 seconds"
        />
        <StatCard
          icon={<Eye size={14} />}
          label="Total page views"
          value={site ? site.total_page_views.toLocaleString() : "…"}
          hint="Every page load/navigation, repeats included"
        />
      </div>

      <h2 className="text-lg font-semibold text-[var(--text)] mb-1">Search index</h2>
      <p className="text-xs text-[var(--muted2)] mb-3">
        {index ? `${index.total_points.toLocaleString()} declarations indexed, live from the API.` : "Loading…"}
      </p>

      <h3 className="text-sm font-medium text-[var(--muted)] mb-2">By library</h3>
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-5 mb-6">
        <div className="flex flex-col gap-3">
          {LIBRARY_ANALYSIS.map((row) => (
            <div key={row.lib}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-[var(--text)] font-medium">{LIBRARY_LABELS[row.lib] ?? row.lib}</span>
                <span className="text-[var(--muted)] tabular-nums">
                  {row.count.toLocaleString()} · {row.share}% · {row.descPct}% described
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-[var(--surface2)] overflow-hidden">
                <div
                  className="h-full bg-[var(--accent)] rounded-full"
                  style={{ width: `${row.share}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      <h3 className="text-sm font-medium text-[var(--muted)] mb-2">By declaration kind (top 6)</h3>
      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-5">
        <div className="flex flex-col gap-3">
          {TOP_KINDS.map((row) => (
            <div key={row.kind}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-[var(--text)] font-medium">{row.kind}</span>
                <span className="text-[var(--muted)] tabular-nums">
                  {row.count.toLocaleString()} · {row.share}%
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-[var(--surface2)] overflow-hidden">
                <div
                  className="h-full bg-[var(--muted)] rounded-full"
                  style={{ width: `${row.share}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
