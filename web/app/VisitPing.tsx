"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { pingVisit, pingPageview } from "@/lib/api";

const STORAGE_KEY = "rocqet-visitor-id";
const HEARTBEAT_MS = 30_000;

function getVisitorId(): string | null {
  try {
    let id = localStorage.getItem(STORAGE_KEY);
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem(STORAGE_KEY, id);
    }
    return id;
  } catch {
    return null;
  }
}

/**
 * Silent visitor tracking for /site-stats:
 * - a heartbeat every 30s keeps this browser counted as "active now"
 * - a pageview fires on first load and every client-side navigation
 */
export default function VisitPing() {
  const pathname = usePathname();

  useEffect(() => {
    const id = getVisitorId();
    if (!id) return;

    pingVisit(id);
    const interval = setInterval(() => pingVisit(id), HEARTBEAT_MS);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const id = getVisitorId();
    if (!id) return;
    pingPageview(id, pathname || "/");
  }, [pathname]);

  return null;
}
