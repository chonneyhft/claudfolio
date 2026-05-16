export function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export function fmtPct(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return `${n.toFixed(digits)}%`;
}

export function fmtNum(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return n.toFixed(digits);
}

export function pillClass(value: string | null | undefined): string {
  if (!value) return "pill";
  const v = value.toLowerCase();
  if (["bullish", "bull", "strong", "positive", "upgrade"].includes(v)) return "pill bull";
  if (["bearish", "bear", "weak", "negative", "downgrade"].includes(v)) return "pill bear";
  return "pill neutral";
}

const MONEY = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});

const MONEY_SIGNED = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
  signDisplay: "exceptZero",
});

export function fmtMoney(n: number | null | undefined, signed = false): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return (signed ? MONEY_SIGNED : MONEY).format(n);
}

export function signedPct(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const sign = n > 0 ? "+" : n < 0 ? "" : "";
  return `${sign}${n.toFixed(digits)}%`;
}

export function pnlClass(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n) || n === 0) return "";
  return n > 0 ? "pos" : "neg";
}
