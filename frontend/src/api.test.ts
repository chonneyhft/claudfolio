import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { api } from "./api";

const okJson = (body: unknown) =>
  ({
    ok: true,
    status: 200,
    statusText: "OK",
    json: async () => body,
  }) as Response;

const errJson = (status: number, detail?: string) =>
  ({
    ok: false,
    status,
    statusText: "Bad",
    json: async () => (detail ? { detail } : {}),
  }) as Response;

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("api.health", () => {
  test("hits /health and returns body", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      okJson({ status: "ok" }),
    );
    const out = await api.health();
    expect(out).toEqual({ status: "ok" });
    expect(fetch).toHaveBeenCalledWith(
      "/api/health",
      expect.objectContaining({
        headers: { "Content-Type": "application/json" },
      }),
    );
  });
});

describe("api.watchlistSnapshot", () => {
  test("appends date query param when given", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      okJson({ as_of: "2026-04-17", entries: [] }),
    );
    await api.watchlistSnapshot("2026-04-17");
    expect(fetch).toHaveBeenCalledWith(
      "/api/watchlist/snapshot?date=2026-04-17",
      expect.any(Object),
    );
  });

  test("omits date when not provided", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      okJson({ as_of: "x", entries: [] }),
    );
    await api.watchlistSnapshot();
    expect(fetch).toHaveBeenCalledWith(
      "/api/watchlist/snapshot",
      expect.any(Object),
    );
  });
});

describe("api.tickerDetail", () => {
  test("URL-encodes the symbol", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      okJson({ ticker: "BRK.B" }),
    );
    await api.tickerDetail("BRK.B");
    expect(fetch).toHaveBeenCalledWith(
      "/api/tickers/BRK.B",
      expect.any(Object),
    );
  });
});

describe("api.runPipeline", () => {
  test("POSTs and serializes wait flag", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      okJson({ status: "completed" }),
    );
    await api.runPipeline("meta", { ticker: "NVDA", date: "2026-04-17", wait: true });
    expect(fetch).toHaveBeenCalledWith(
      "/api/pipeline/meta?ticker=NVDA&date=2026-04-17&wait=true",
      expect.objectContaining({ method: "POST" }),
    );
  });
});

describe("error handling", () => {
  test("surfaces FastAPI detail in thrown error", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      errJson(404, "no briefing stored for 2026-04-17"),
    );
    await expect(api.briefing("2026-04-17")).rejects.toThrow(
      /404 no briefing stored/,
    );
  });

  test("falls back to statusText when detail missing", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      errJson(500),
    );
    await expect(api.health()).rejects.toThrow(/500 Bad/);
  });
});
