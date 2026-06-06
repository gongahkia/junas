import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function read(relativePath) {
  return readFileSync(path.join(frontendRoot, relativePath), "utf8");
}

function commandDefinitions() {
  const source = read("lib/commands/definitions.ts");
  const arrayStart = source.indexOf("export const COMMAND_DEFINITIONS");
  assert.notEqual(arrayStart, -1, "COMMAND_DEFINITIONS export is missing");

  const assignment = source.indexOf("=", arrayStart);
  assert.notEqual(assignment, -1, "COMMAND_DEFINITIONS assignment is missing");

  const openBracket = source.indexOf("[", assignment);
  assert.notEqual(openBracket, -1, "COMMAND_DEFINITIONS array is missing");

  const definitions = [];
  let depth = 0;
  let definitionStart = -1;

  for (let index = openBracket + 1; index < source.length; index += 1) {
    const char = source[index];
    if (char === "{") {
      if (depth === 0) definitionStart = index;
      depth += 1;
    } else if (char === "}") {
      depth -= 1;
      if (depth === 0 && definitionStart !== -1) {
        definitions.push(source.slice(definitionStart, index + 1));
        definitionStart = -1;
      }
    } else if (char === "]" && depth === 0) {
      break;
    }
  }

  return definitions.map((definition) => {
    const id = definition.match(/id:\s*"([^"]+)"/)?.[1];
    const action = definition.match(/action:\s*\{\s*kind:\s*"([^"]+)"(?:,\s*commandId:\s*"([^"]+)")?(?:,\s*href:\s*"([^"]+)")?/s);
    assert.ok(id, `definition is missing id: ${definition}`);
    assert.ok(action, `definition ${id} is missing action`);
    return {
      id,
      actionKind: action[1],
      commandId: action[2],
      href: action[3],
    };
  });
}

function routeExists(href) {
  if (href === "/") return existsSync(path.join(frontendRoot, "app/page.tsx"));
  return existsSync(path.join(frontendRoot, "app", href.replace(/^\//, ""), "page.tsx"));
}

test("CommandSuggestions exposes only slash commands implemented by command-handler", () => {
  const suggestions = read("components/chat/CommandSuggestions.tsx");
  assert.match(suggestions, /COMMAND_DEFINITIONS\.reduce<CommandDef\[\]>/);
  assert.match(suggestions, /definition\.action\.kind !== "command"/);

  const suggestedCommands = commandDefinitions()
    .filter((definition) => definition.actionKind === "command")
    .map((definition) => definition.commandId);
  const handledCommands = new Set([...read("lib/commands/command-handler.ts").matchAll(/case\s+"([^"]+)":/g)].map((match) => match[1]));

  assert.ok(suggestedCommands.length > 0, "CommandSuggestions should expose at least one slash command");
  assert.deepEqual(
    suggestedCommands.filter((commandId) => !handledCommands.has(commandId)),
    [],
  );
});

test("command palette navigation commands target existing app routes", () => {
  const navigationCommands = commandDefinitions().filter((definition) => definition.actionKind === "navigate");
  const brokenRoutes = navigationCommands.filter((definition) => !definition.href || !routeExists(definition.href));

  assert.equal(navigationCommands.find((definition) => definition.id === "home")?.href, "/");
  assert.deepEqual(brokenRoutes, []);
});
