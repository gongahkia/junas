// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function parseToml(toml: string): Record<string, any> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const result: Record<string, any> = {};
  let currentSection = result;

  const lines = toml.split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;

    // Section
    const sectionMatch = trimmed.match(/^\\\[(.*?)\\\]$/);
    if (sectionMatch) {
      const sectionName = sectionMatch[1];
      result[sectionName] = {};
      currentSection = result[sectionName];
      continue;
    }

    // Key-Value
    const kvMatch = trimmed.match(/^([\w\d_-]+)\s*=\s*(.*)$/);
    if (kvMatch) {
      const key = kvMatch[1];
      const valueStr = kvMatch[2];
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let value: any = valueStr;

      // Handle strings
      if (valueStr.startsWith('"') && valueStr.endsWith('"')) {
        value = valueStr.slice(1, -1);
      } else if (valueStr.startsWith("'" ) && valueStr.endsWith("'" )) {
        value = valueStr.slice(1, -1);
      } 
      // Handle booleans
      else if (valueStr === 'true') value = true;
      else if (valueStr === 'false') value = false;
      // Handle numbers
      else if (!isNaN(Number(valueStr))) value = Number(valueStr);

      currentSection[key] = value;
    }
  }
  return result;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function stringifyToml(data: Record<string, any>): string {
  let toml = '';
  const sections: string[] = [];

  // Top level
  for (const [key, value] of Object.entries(data)) {
    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      sections.push(key);
      continue;
    }
    if (Array.isArray(value)) continue; // Skip arrays for now (snippets/profiles) or handle simplified

    let valStr = String(value);
    if (typeof value === 'string') {
        // Simple escaping
        valStr = `"${value.replace(/"/g, '\"').replace(/\n/g, '\\n')}"`;
    }
    toml += `${key} = ${valStr}\n`;
  }

  // Sections
  for (const section of sections) {
    toml += `\n[${section}]\n`;
    const sectionData = data[section];
    for (const [key, value] of Object.entries(sectionData)) {
       let valStr = String(value);
       if (typeof value === 'string') {
           valStr = `"${value.replace(/"/g, '\"').replace(/\n/g, '\\n')}"`;
       }
       toml += `${key} = ${valStr}\n`;
    }
  }

  return toml;
}
