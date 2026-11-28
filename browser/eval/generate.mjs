import { writeFile } from "node:fs/promises";
import { makeCases } from "./cases.js";
await writeFile(new URL("cases.json", import.meta.url), JSON.stringify(makeCases(), null, 2) + "\n");
