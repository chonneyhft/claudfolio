import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import Briefing from "./Briefing";

const VIEW = {
  as_of: "2026-04-17",
  tickers: ["NVDA"],
  markdown: "# Hello briefing\n\nAll systems go.",
  model: "claude-opus-4-7",
  created_at: "2026-04-17T10:00:00Z",
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => VIEW,
    } as Response),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/briefing" element={<Briefing />} />
        <Route path="/briefing/:date" element={<Briefing />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Briefing page", () => {
  test("renders markdown body once loaded", async () => {
    renderAt("/briefing/2026-04-17");
    await waitFor(() => {
      expect(screen.getByText("Hello briefing")).toBeInTheDocument();
    });
    expect(screen.getByText("All systems go.")).toBeInTheDocument();
  });

  test("404 shows the no-briefing fallback", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ detail: "no briefing stored" }),
      } as Response),
    );
    renderAt("/briefing/2026-04-17");
    await waitFor(() => {
      expect(screen.getByText(/Error:.*no briefing stored/)).toBeInTheDocument();
    });
  });
});
