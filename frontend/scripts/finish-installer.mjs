/**
 * Publish the installer as a single, plainly-named file.
 *
 * Tauri names its NSIS output `{productName}_{version}_{arch}-setup.exe` and
 * offers no way to override it, so the last step is ours: copy that one file to
 * `release/atlas_setup.exe`. Nothing is extracted or split — the setup already
 * carries the app, the bundled backend and the WebView2 bootstrapper, and
 * expands them on install.
 */
import { copyFileSync, mkdirSync, readdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const nsisDir = resolve(here, "../src-tauri/target/release/bundle/nsis");
const outDir = resolve(here, "../../release");
const outFile = join(outDir, "atlas_setup.exe");

let candidates;
try {
  candidates = readdirSync(nsisDir).filter((f) => f.endsWith(".exe"));
} catch {
  console.error(`No NSIS output at ${nsisDir}. Run \`npm run tauri build\` first.`);
  process.exit(1);
}

if (candidates.length === 0) {
  console.error(`No installer found in ${nsisDir}.`);
  process.exit(1);
}

// Newest wins, so a stale artifact from an older version is never published.
const newest = candidates
  .map((f) => ({ f, mtime: statSync(join(nsisDir, f)).mtimeMs }))
  .sort((a, b) => b.mtime - a.mtime)[0].f;

mkdirSync(outDir, { recursive: true });
copyFileSync(join(nsisDir, newest), outFile);

const mb = (statSync(outFile).size / 1024 / 1024).toFixed(1);
console.log(`installer -> ${outFile}  (${mb} MB, from ${newest})`);
