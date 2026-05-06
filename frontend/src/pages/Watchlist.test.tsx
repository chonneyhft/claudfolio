import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Watchlist from "./Watchlist";

const SNAPSHOT = {
  as_of: "2026-04-17",
  entries: [
    {
      ticker: "NVDA",
      sector: "Tech",
      sentiment: {
        as_of: "2026-04-17",
        sentiment_score: 0.72,
        sentiment_direction: "improving",
        sentiment_delta_7d: 0.15,
        source_breakdown: {},
        key_topics: [],
        notable_headlines: [],
      },
      quantitative: {
        as_of: "2026-04-17",
        close: 950.0,
        change_1d: 1.2,
        change_5d: 3.0,
        change_20d: 8.0,
        rsi_14: 58.4,
        above_50sma: true,
        above_200sma: true,
        macd_signal: "bullish_crossover",
        volume_vs_20d_avg: 1.3,
        sector_etf: "XLK",
        relative_return_5d: 0.8,
        health_score: "strong",
      },
      enrichment: null,
    },
  ],
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => SNAPSHOT,
    } as Response),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Watchlist page", () => {
  test("renders heading immediately", () => {
    render(
      <MemoryRouter>
        <Watchlist />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Watchlist" })).toBeInTheDocument();
  });

  test("renders ticker row after fetch resolves", async () => {
    render(
      <MemoryRouter>
        <Watchlist />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("NVDA")).toBeInTheDocument();
    });
    expect(screen.getByText("Tech")).toBeInTheDocument();
    expect(screen.getByText("strong")).toBeInTheDocument();
    expect(screen.getByText("improving")).toBeInTheDocument();
  });

  test("shows fetch error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Server Error",
        json: async () => ({}),
      } as Response),
    );

    render(
      <MemoryRouter>
        <Watchlist />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText(/Error: 500/)).toBeInTheDocument();
    });
  });
});
