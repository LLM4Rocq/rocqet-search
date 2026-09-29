"use client";

import { useEffect } from "react";
import { pingVisit } from "@/lib/api";

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

/** Silent heartbeat so /site-stats has real active/total visitor counts. */
export default function VisitPing() {
  useEffect(() => {
    const id = getVisitorId();
    if (!id) return;

    pingVisit(id);
    const interval = setInterval(() => pingVisit(id), HEARTBEAT_MS);
    return () => clearInterval(interval);
  }, []);

  return null;
}
