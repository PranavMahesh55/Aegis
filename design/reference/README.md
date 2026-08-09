# Open CoDesign reference

The accepted visual reference was exported from Open CoDesign as:

`/Users/pranav/Downloads/Aegis-Blocked-Agent-Prototype-App-2026-08-06-185046.html`

- SHA-256: `a1036ed7558a68868ed73a041bfc39805a43d1886ed5c1d6c7f497a7a739b599`
- Standalone export size: approximately 3.2 MB
- Embedded authored Aegis source: 36,888 bytes / 266 lines
- Embedded React runtime: 18.3.1

The full standalone runtime is intentionally not shipped. It contains React, ReactDOM, Babel,
Open CoDesign edit helpers, and unrelated `iOS.jsx` and `DesignCanvas.jsx` sources. Run the
extractor with the original export path to refresh the authored reference:

```bash
node scripts/extract-codesign-source.mjs \
  /Users/pranav/Downloads/Aegis-Blocked-Agent-Prototype-App-2026-08-06-185046.html \
  design/reference/aegis-open-codesign-artifact.jsx
```

Production code must not import the extracted reference. It exists for visual and interaction
comparison only.

