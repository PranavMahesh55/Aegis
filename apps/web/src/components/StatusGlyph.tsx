export function StatusGlyph({ tone }: { tone: string }) {
  return <span className={`status-glyph ${tone.toLowerCase()}`} aria-hidden="true" />;
}

