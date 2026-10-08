"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import Link from "next/link";
import {
  Search, Loader2, ExternalLink, ChevronDown, Copy, Check, GitBranch,
  Activity, Sun, Moon, HelpCircle, Network, ArrowLeft, X,
} from "lucide-react";
import {
  searchFLT,
  getFLTStats,
  FLTResult,
  FLTSearchResponse,
  FLTStatsResponse,
} from "@/lib/api";

type Mode = "what" | "used";

const EXAMPLES: Record<Mode, string[]> = {
  what: [
    "Frey curve",
    "Frobenius endomorphism",
    "Selmer group",
    "Fermat's last theorem",
    "Mazur's irreducibility result",
    "discriminant of the Frey curve",
  ],
  used: [
    "modularity lifting",
    "Frey curve",
    "Ribet's level lowering",
    "Eisenstein ideal",
  ],
};

// ---------------------------------------------------------------------------
// Atoms (mirroring the main page)
// ---------------------------------------------------------------------------
function ThemeToggle() {
  const [dark, setDark] = useState<boolean | null>(null);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  const toggle = () => {
    const next = !document.documentElement.classList.contains("dark");
    document.documentElement.classList.toggle("dark", next);
    try { localStorage.setItem("rocqet-theme", next ? "dark" : "light"); } catch {}
    setDark(next);
  };

  return (
    <button
      onClick={toggle}
      aria-label="Toggle dark mode"
      className="flex items-center justify-center w-8 h-8 text-[var(--muted)] hover:text-[var(--text)] border border-[var(--border)] hover:border-[var(--border-strong)] rounded-lg transition-colors"
    >
      {dark === null ? null : dark ? <Sun size={14} /> : <Moon size={14} />}
    </button>
  );
}

function StageBadge({ stage }: { stage: string }) {
  if (!stage) return null;
  return (
    <span className="text-[11px] px-2 py-0.5 rounded-md border border-[var(--border)] bg-[var(--surface2)] text-[var(--muted)] whitespace-nowrap">
      {stage}
    </span>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() =>
        navigator.clipboard?.writeText(text).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        })
      }
      className="flex items-center gap-1 text-xs text-[var(--muted)] hover:text-[var(--text)] transition-colors"
      title="Copy Lean statement"
    >
      {copied ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

function SkeletonCard() {
  return (
    <div className="border border-[var(--border)] rounded-2xl bg-[var(--surface)] p-4 space-y-3">
      <div className="flex gap-2">
        <div className="skeleton h-4 w-16" />
        <div className="skeleton h-4 w-32" />
      </div>
      <div className="skeleton h-8 w-full" />
      <div className="skeleton h-3 w-2/3" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Result card
// ---------------------------------------------------------------------------
function FLTCard({ r, rank, mode }: { r: FLTResult; rank: number; mode: Mode }) {
  const [expanded, setExpanded] = useState(false);
  const score = Math.max(0, Math.min(100, Math.round(r.score * 100)));

  return (
    <div
      className="border border-[var(--border)] rounded-2xl bg-[var(--surface)] hover:border-[var(--border-strong)] hover:shadow-sm transition-all duration-150 animate-slide-up overflow-hidden"
      style={{ animationDelay: `${Math.min(rank, 12) * 30}ms` }}
    >
      <div className="flex items-start gap-3 p-4">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <span className="kind-badge kind-Theorem">theorem</span>
            {mode === "used" && r.distance != null && (
              <span className="text-[11px] px-2 py-0.5 rounded-md bg-[var(--accent-soft)] text-[var(--accent)] font-medium whitespace-nowrap">
                {r.distance === 1 ? "used directly" : `${r.distance} hops away`}
              </span>
            )}
            <span className="font-semibold text-[var(--text)] text-[15px] break-all">
              {r.title || r.name}
            </span>
            <StageBadge stage={r.stage_name} />
            <span className="flex items-center gap-2 ml-auto shrink-0">
              <span className="score-meter" title={`Relevance score: ${score}%`}>
                <span style={{ width: `${score}%` }} />
              </span>
              <span className="text-[11px] text-[var(--muted2)] tabular-nums">{score}%</span>
            </span>
          </div>

          <p className="font-mono text-[11px] text-[var(--muted2)] mb-2 break-all">{r.name}</p>

          {r.summary && (
            <div
              className="text-sm text-[var(--muted)] mb-2 leading-relaxed"
              dangerouslySetInnerHTML={{ __html: r.summary }}
            />
          )}

          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mt-2.5">
            <span className="text-[11px] text-[var(--muted2)] truncate max-w-[18rem]">
              {r.module}
            </span>
            <span className="text-[11px] text-[var(--muted2)]">
              cites {r.n_cites} · used by {r.n_cited_by}
            </span>

            {r.statement && <CopyButton text={r.statement} />}

            <a
              href={r.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-xs text-[var(--accent)] hover:underline"
            >
              <ExternalLink size={12} /> Docs
            </a>

            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 text-xs text-[var(--muted)] hover:text-[var(--text)] transition-colors ml-auto"
            >
              Lean statement
              <ChevronDown size={13} className={`transition-transform ${expanded ? "rotate-180" : ""}`} />
            </button>
          </div>
        </div>
      </div>

      {expanded && r.statement && (
        <div className="border-t border-[var(--border)] px-4 py-3 bg-[var(--surface2)] animate-fade-in">
          <pre className="type-sig whitespace-pre-wrap break-words">{r.statement}</pre>
          <p className="text-[11px] text-[var(--muted2)] mt-2">
            The Lean statement is authoritative; the English summary above is generated.
          </p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function FLTPage() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<Mode>("what");
  const [resp, setResp] = useState<FLTSearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [hasSearched, setHasSearched] = useState(false);
  const [stats, setStats] = useState<FLTStatsResponse | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    getFLTStats().then(setStats).catch(() => {});
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.key === "/" || (e.key === "k" && (e.metaKey || e.ctrlKey))) && document.activeElement !== inputRef.current) {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if (e.key === "Escape" && document.activeElement === inputRef.current) inputRef.current?.blur();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const doSearch = useCallback(async (q: string, m: Mode) => {
    if (!q.trim()) { setResp(null); setHasSearched(false); return; }
    setLoading(true);
    setError("");
    try {
      const r = await searchFLT(q, m, 10);
      setResp(r);
      setHasSearched(true);
    } catch {
      setError("Could not reach the API. Make sure the backend is running with the FLT index built.");
      setResp(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleInput = (val: string) => {
    setQuery(val);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(val, mode), 280);
  };

  const switchMode = (m: Mode) => {
    setMode(m);
    if (query.trim()) doSearch(query, m);
  };

  const handleExample = (q: string) => { setQuery(q); doSearch(q, mode); inputRef.current?.focus(); };

  const clearAll = () => {
    setQuery(""); setResp(null); setHasSearched(false);
    inputRef.current?.focus();
  };

  const heroMode = !hasSearched && !loading;

  // group used-mode results by proof stage, preserving score order within groups
  const grouped: [string, FLTResult[]][] = [];
  if (resp && mode === "used") {
    const byStage = new Map<string, FLTResult[]>();
    for (const r of resp.results) {
      const key = r.stage_name || "Unstaged";
      if (!byStage.has(key)) byStage.set(key, []);
      byStage.get(key)!.push(r);
    }
    grouped.push(...byStage.entries());
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Nav */}
      <nav className="flex items-center justify-between px-6 py-5">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-1.5 text-sm text-[var(--muted)] hover:text-[var(--text)] transition-colors">
            <ArrowLeft size={14} /> Rocqet
          </Link>
          <span className="kind-badge kind-Theorem">FLT</span>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/stats"
            className="flex items-center gap-1.5 text-sm text-[var(--muted)] hover:text-[var(--text)] border border-[var(--border)] hover:border-[var(--border-strong)] rounded-lg px-3 py-1.5 transition-colors"
          >
            <Activity size={14} /> Stats
          </Link>
          <a
            href="https://github.com/LLM4Rocq/rocqet-search"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-sm text-[var(--muted)] hover:text-[var(--text)] border border-[var(--border)] hover:border-[var(--border-strong)] rounded-lg px-3 py-1.5 transition-colors"
          >
            <GitBranch size={14} /> GitHub
          </a>
          <ThemeToggle />
        </div>
      </nav>

      {/* Main */}
      <main className={`flex-1 w-full max-w-2xl mx-auto px-4 flex flex-col ${heroMode ? "justify-center pb-32" : "pt-2"}`}>
        {heroMode && (
          <div className="text-center mb-8 animate-fade-in">
            <h1 className="text-4xl sm:text-5xl font-bold text-[var(--text)] tracking-tight">
              FLT Search
            </h1>
            <p className="text-[var(--muted)] mt-4 text-sm">
              Search the 29,511 theorems of the machine-checked proof of Fermat's Last Theorem.
            </p>
            {stats && (
              <p className="text-xs text-[var(--muted2)] mt-4 font-mono">
                {stats.total_theorems.toLocaleString()} theorems ·{" "}
                {stats.total_edges.toLocaleString()} citations ·{" "}
                {Object.keys(stats.stages).length} proof stages
              </p>
            )}
          </div>
        )}

        {/* Mode toggle */}
        <div className="flex justify-center mb-4">
          <div className="inline-flex rounded-xl border border-[var(--border)] bg-[var(--surface)] p-1 gap-1">
            <button
              onClick={() => switchMode("what")}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm transition-colors ${
                mode === "what"
                  ? "bg-[var(--accent-soft)] text-[var(--accent)] font-medium"
                  : "text-[var(--muted)] hover:text-[var(--text)]"
              }`}
            >
              <HelpCircle size={14} /> What is it?
            </button>
            <button
              onClick={() => switchMode("used")}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm transition-colors ${
                mode === "used"
                  ? "bg-[var(--accent-soft)] text-[var(--accent)] font-medium"
                  : "text-[var(--muted)] hover:text-[var(--text)]"
              }`}
            >
              <Network size={14} /> Where is it used?
            </button>
          </div>
        </div>

        {/* Search bar */}
        <div className="relative">
          <div className={`flex items-center gap-3 bg-[var(--surface)] border rounded-2xl px-5 py-4 transition-all duration-150
            focus-within:border-[var(--accent)] focus-within:ring-2 focus-within:ring-[var(--accent)]/25
            ${heroMode ? "search-shadow" : ""}
            ${query ? "border-[var(--border-strong)]" : "border-[var(--border)] hover:border-[var(--border-strong)]"}`}>
            {loading
              ? <Loader2 size={18} className="text-[var(--muted)] shrink-0 animate-spin" />
              : <Search size={18} className="text-[var(--muted2)] shrink-0" />}
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={e => handleInput(e.target.value)}
              placeholder={mode === "what" ? "Describe a theorem in plain language…" : "Name a concept, e.g. modularity lifting…"}
              className="flex-1 bg-transparent outline-none text-[15px] text-[var(--text)] placeholder:text-[var(--muted2)]"
              autoComplete="off"
              spellCheck={false}
            />
            {query && (
              <button onClick={clearAll} className="text-[var(--muted2)] hover:text-[var(--text)] transition-colors" aria-label="Clear">
                <X size={16} />
              </button>
            )}
          </div>
        </div>

        {/* Example queries */}
        {heroMode && (
          <div className="flex flex-wrap justify-center gap-2 mt-6 animate-fade-in">
            {EXAMPLES[mode].map(q => (
              <button
                key={q}
                onClick={() => handleExample(q)}
                className="text-xs text-[var(--muted)] hover:text-[var(--accent)] border border-[var(--border)] hover:border-[var(--accent)] rounded-full px-3 py-1.5 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {/* Error */}
        {error && (
          <p className="text-sm text-red-500 mt-4 text-center animate-fade-in">{error}</p>
        )}

        {/* Loading skeletons */}
        {loading && !resp && (
          <div className="space-y-3 mt-6">
            <SkeletonCard /><SkeletonCard /><SkeletonCard />
          </div>
        )}

        {/* Results */}
        {resp && !loading && (
          <div className="mt-6 space-y-5">
            <p className="text-xs text-[var(--muted2)] font-mono">
              {resp.results.length} results · {resp.elapsed_ms}ms
              {mode === "used" && resp.seeds.length > 0 && (
                <span> · matched: {resp.seeds.map(s => s.name.split(".").pop()).join(", ")}</span>
              )}
            </p>

            {mode === "what" && (
              <div className="space-y-3">
                {resp.results.map((r, i) => <FLTCard key={r.name} r={r} rank={i} mode={mode} />)}
              </div>
            )}

            {mode === "used" && grouped.map(([stage, items]) => (
              <div key={stage}>
                <h2 className="text-sm font-semibold text-[var(--text)] mb-3 flex items-center gap-2">
                  <span className="kind-badge kind-Theorem">{items.length}</span>
                  {stage}
                </h2>
                <div className="space-y-3">
                  {items.map((r, i) => <FLTCard key={r.name} r={r} rank={i} mode={mode} />)}
                </div>
              </div>
            ))}

            {resp.results.length === 0 && (
              <p className="text-sm text-[var(--muted)] text-center py-8">
                Nothing found. Try a different description.
              </p>
            )}
          </div>
        )}

        {/* Footer note */}
        {heroMode && (
          <p className="text-center text-[11px] text-[var(--muted2)] mt-10 max-w-md mx-auto leading-relaxed">
            Built on the anthropics/fermats-last-theorem corpus. The Lean statement is
            authoritative; English summaries are generated. "Where is it used" walks the
            citation graph outward from the best matches.
          </p>
        )}
      </main>
    </div>
  );
}
