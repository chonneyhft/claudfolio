import { describe, expect, test } from "vitest";
import { fmtNum, fmtPct, pillClass, todayISO } from "./util";

describe("fmtNum", () => {
  test("formats numbers to 2 decimals by default", () => {
    expect(fmtNum(3.14159)).toBe("3.14");
  });
  test("respects custom digits", () => {
    expect(fmtNum(3.14159, 4)).toBe("3.1416");
  });
  test("returns em dash for null/undefined/NaN", () => {
    expect(fmtNum(null)).toBe("—");
    expect(fmtNum(undefined)).toBe("—");
    expect(fmtNum(Number.NaN)).toBe("—");
  });
});

describe("fmtPct", () => {
  test("appends %", () => {
    expect(fmtPct(2.5)).toBe("2.50%");
  });
  test("nullish → em dash", () => {
    expect(fmtPct(null)).toBe("—");
  });
});

describe("pillClass", () => {
  test("bullish-family → bull", () => {
    expect(pillClass("bullish")).toBe("pill bull");
    expect(pillClass("STRONG")).toBe("pill bull");
    expect(pillClass("upgrade")).toBe("pill bull");
  });
  test("bearish-family → bear", () => {
    expect(pillClass("bearish")).toBe("pill bear");
    expect(pillClass("DOWNGRADE")).toBe("pill bear");
  });
  test("anything else → neutral", () => {
    expect(pillClass("stable")).toBe("pill neutral");
    expect(pillClass(undefined)).toBe("pill");
    expect(pillClass(null)).toBe("pill");
  });
});

describe("todayISO", () => {
  test("returns a YYYY-MM-DD string", () => {
    expect(todayISO()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
