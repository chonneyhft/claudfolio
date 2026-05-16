export function Loader({ label = "Loading" }: { label?: string }) {
  return (
    <span className="loader" role="status">
      {label}
    </span>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error);
  return <div className="error">Error: {msg}</div>;
}
