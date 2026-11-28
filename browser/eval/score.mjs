import { readFile, writeFile } from "node:fs/promises";
import { scoreResults } from "../src/evaluation.js";
if (process.argv.length !== 5) throw Error("Usage: node eval/score.mjs CASES.json RESULTS.json OUTPUT.json");
const [cases, rows] = await Promise.all(process.argv.slice(2, 4).map(path => readFile(path, "utf8").then(JSON.parse)));
await writeFile(process.argv[4], JSON.stringify(scoreResults(cases, rows), null, 2) + "\n", { flag: "wx" });
