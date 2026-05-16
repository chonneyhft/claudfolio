import { describe, expect, test } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorBox, Loader } from "./Loader";

describe("Loader", () => {
  test("default label", () => {
    render(<Loader />);
    expect(screen.getByText("Loading")).toBeInTheDocument();
  });

  test("custom label", () => {
    render(<Loader label="Fetching…" />);
    expect(screen.getByText("Fetching…")).toBeInTheDocument();
  });
});

describe("ErrorBox", () => {
  test("shows Error.message", () => {
    render(<ErrorBox error={new Error("boom")} />);
    expect(screen.getByText(/boom/)).toBeInTheDocument();
  });

  test("stringifies non-Error values", () => {
    render(<ErrorBox error="plain string"/>);
    expect(screen.getByText(/plain string/)).toBeInTheDocument();
  });
});
