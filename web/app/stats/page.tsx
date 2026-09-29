"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Radio, Users, Loader2 } from "lucide-react";
import { getSiteStats, getStats, SiteStats, StatsResponse, LIBRARY_LABELS } from "@/lib/api";

const POLL_MS = 5_000;

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

      <h1 className="text-3xl font-bold text-[var(--text)] tracking-tight mb-2">Site stats</h1>
      <p className="text-[var(--muted)] text-sm mb-8">
        Visitors are counted from a self-hosted heartbeat (localStorage id, no
        cookies, no third-party tracker) — an approximate count, not
        analytics-grade. &ldquo;Active now&rdquo; means a heartbeat in the last 90s.
      </p>

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
          icon={<Users size={14} />}
          label="Total visitors"
          value={site ? site.total_visitors.toLocaleString() : "…"}
          hint="Distinct browsers seen since counting started"
        />
      </div>

      <h2 className="text-lg font-semibold text-[var(--text)] mb-3">Search index</h2>
      {index ? (
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-5">
          <div className="text-sm text-[var(--muted)] mb-3">
            {index.total_points.toLocaleString()} declarations indexed
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(index.libraries)
              .sort((a, b) => b[1] - a[1])
              .map(([lib, count]) => (
                <span
                  key={lib}
                  className="text-xs px-2.5 py-1 rounded-lg border border-[var(--border)] bg-[var(--surface2)] text-[var(--text)]"
                >
                  {LIBRARY_LABELS[lib] ?? lib}: {count.toLocaleString()}
                </span>
              ))}
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-2 text-[var(--muted)] text-sm">
          <Loader2 size={14} className="animate-spin" />
          Loading…
        </div>
      )}
    </main>
  );
}
