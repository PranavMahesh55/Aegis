import { readFile, writeFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";

const [, , inputArg, outputArg] = process.argv;
if (!inputArg || !outputArg) {
  throw new Error("Usage: node scripts/extract-codesign-source.mjs <export.html> <output.jsx>");
}

const input = resolve(inputArg);
const output = resolve(outputArg);
const html = await readFile(input, "utf8");
const matches = [...html.matchAll(/var source = ("(?:\\.|[^"\\])*");/g)];
if (matches.length === 0) throw new Error("No embedded Open CoDesign sources found");
const authored = JSON.parse(matches.at(-1)[1]);
if (!authored.includes("function App()") || !authored.includes("ApprovedContextSource")) {
  throw new Error("The final source does not appear to be the Aegis artifact");
}
await mkdir(dirname(output), { recursive: true });
await writeFile(output, authored, "utf8");
console.log(`Extracted ${authored.length} characters to ${output}`);

