import { build } from "esbuild";
import { cp, mkdir, rm, readdir, readFile } from "node:fs/promises";
import { createHash } from "node:crypto";

async function sources(directory) {
  const files = [];
  for (const item of await readdir(directory, { withFileTypes: true })) {
    const path = `${directory}/${item.name}`;
    files.push(...(item.isDirectory() ? await sources(path) : [path]));
  }
  return files;
}
const hash = createHash("sha256");
const files = [...await sources("src"), ...await sources("public"), "eval/cases.js", "package-lock.json", "build.mjs", "../config/sensitivity-development-gates.json"];
for (const file of files.sort()) { hash.update(file); hash.update("\0"); hash.update(await readFile(file)); hash.update("\0"); }
const identity = hash.digest("hex");

await rm("dist", { recursive: true, force: true });
await mkdir("dist");
await build({
  entryPoints: ["src/app.js", "src/worker.js", "src/background.js", "src/benchmark.js"],
  outdir: "dist", bundle: true, format: "esm", target: "chrome120",
  minify: true, sourcemap: false,
  define: { __JUNAS_BUILD_ID__: JSON.stringify(identity) },
});
for (const file of ["manifest.json", "process.html", "style.css", "benchmark.html"]) {
  await cp(`public/${file}`, `dist/${file}`);
}
