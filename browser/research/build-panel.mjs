import { build } from "esbuild";
import { readFile, writeFile, cp } from "node:fs/promises";
await build({ entryPoints: ["research/panel-host.js", "research/panel-client.js"], bundle: true, format: "esm", target: "chrome120", outdir: "dist" });
await cp("research/panel.html", "dist/panel.html");
const popup = await readFile("public/popup.html", "utf8");
await writeFile("dist/panel-popup.html", popup.replace('src="app.js"', 'src="panel-client.js"').replace("<footer>", "<footer hidden>"));
