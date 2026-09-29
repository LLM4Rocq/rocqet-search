import { describe, it, expect, vi, afterEach } from "vitest";
import {
  searchDeclarations, getStats, getSiteStats, pingVisit, pingPageview,
  ACTIVE_LIBRARIES, LIBRARY_LABELS,
} from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubFetch(body: unknown, ok = true, status = 200) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok,
    status,
    json: () => Promise.resolve(body),
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("searchDeclarations", () => {
  it("builds the query string from options", async () => {
    const fetchMock = stubFetch({ query: "q", results: [], total: 0, elapsed_ms: 1 });
    await searchDeclarations("commutativity", { limit: 5, lib: "stdlib", kind: "Lemma" });

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain("/search?");
    expect(calledUrl).toContain("q=commutativity");
    expect(calledUrl).toContain("limit=5");
    expect(calledUrl).toContain("lib=stdlib");
    expect(calledUrl).toContain("kind=Lemma");
  });

  it("omits unset optional params", async () => {
    const fetchMock = stubFetch({ query: "q", results: [], total: 0, elapsed_ms: 1 });
    await searchDeclarations("q");

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).not.toContain("lib=");
    expect(calledUrl).not.toContain("kind=");
    expect(calledUrl).not.toContain("chapter=");
  });

  it("throws on a non-ok response", async () => {
    stubFetch({}, false, 500);
    await expect(searchDeclarations("q")).rejects.toThrow("API error: 500");
  });
});

describe("getStats", () => {
  it("fetches /stats and returns the parsed body", async () => {
    const payload = { total_points: 44440, libraries: { stdlib: 13735 }, kinds: {} };
    const fetchMock = stubFetch(payload);
    const result = await getStats();

    expect(fetchMock.mock.calls[0][0]).toContain("/stats");
    expect(result).toEqual(payload);
  });

  it("throws on a non-ok response", async () => {
    stubFetch({}, false, 503);
    await expect(getStats()).rejects.toThrow("API error: 503");
  });
});

describe("getSiteStats", () => {
  it("fetches /site-stats and returns the parsed body", async () => {
    const payload = { active_now: 3, total_visitors: 42, total_page_views: 210 };
    const fetchMock = stubFetch(payload);
    const result = await getSiteStats();

    expect(fetchMock.mock.calls[0][0]).toContain("/site-stats");
    expect(result).toEqual(payload);
  });
});

describe("pingVisit / pingPageview", () => {
  it("posts the visitor id to /visit", async () => {
    const fetchMock = stubFetch({ ok: true });
    await pingVisit("11111111-1111-1111-1111-111111111111");

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain("/visit");
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body)).toEqual({ visitor_id: "11111111-1111-1111-1111-111111111111" });
  });

  it("posts the visitor id and path to /pageview", async () => {
    const fetchMock = stubFetch({ ok: true });
    await pingPageview("11111111-1111-1111-1111-111111111111", "/stats");

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain("/pageview");
    expect(JSON.parse(opts.body)).toEqual({
      visitor_id: "11111111-1111-1111-1111-111111111111",
      path: "/stats",
    });
  });

  it("never throws, even when fetch fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));
    await expect(pingVisit("x")).resolves.toBeUndefined();
    await expect(pingPageview("x", "/")).resolves.toBeUndefined();
  });
});

describe("library constants", () => {
  it("every active library has a display label", () => {
    for (const lib of ACTIVE_LIBRARIES) {
      expect(LIBRARY_LABELS[lib]).toBeTruthy();
    }
  });
});
