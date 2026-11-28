import { build } from "esbuild";
import { readFile, writeFile, cp } from "node:fs/promises";
const output = process.env.JUNAS_BUILD_DIR || "dist";
await build({ entryPoints: ["research/panel-host.js", "research/panel-client.js"], bundle: true, format: "esm", target: "chrome120", outdir: output });
await cp("research/panel.html", `${output}/panel.html`);
const popup = await readFile("public/popup.html", "utf8");
await writeFile(`${output}/panel-popup.html`, popup.replace('src="app.js"', 'src="panel-client.js"').replace("<footer>", "<footer hidden>"));
