import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import TickerDetail from "./TickerDetail";

const SNAP = {
  ticker: "NVDA",
  sector: "Tech",
  sentiment: {
    as_of: "2026-04-17",
    sentiment_score: 0.72,
    sentiment_direction: "improving",
    sentiment_delta_7d: 0.15,
    source_breakdown: {},
    key_topics: ["earnings"],
    notable_headlines: [{ headline: "Beat estimates" }],
  },
  quantitative: {
    as_of: "2026-04-17",
    close: 950,
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
};

const HISTORY = { sentiment: [], quant: [] };

beforeEach(() => {
  // The page does a Promise.all with two requests — round-robin the responses.
  let n = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(() => {
      const body = n++ === 0 ? SNAP : HISTORY;
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => body,
      } as Response);
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("TickerDetail page", () => {
  test("renders ticker heading and quant card after fetch", async () => {
    render(
      <MemoryRouter initialEntries={["/tickers/NVDA"]}>
        <Routes>
          <Route path="/tickers/:symbol" element={<TickerDetail />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /NVDA/ })).toBeInTheDocument();
    });
    expect(screen.getByText("Quant")).toBeInTheDocument();
    expect(screen.getByText("Sentiment")).toBeInTheDocument();
    expect(screen.getByText(/Beat estimates/)).toBeInTheDocument();
  });
});
