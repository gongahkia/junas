import os
import re

def find_empty_interfaces(root_dir):
    pattern = re.compile(r'interface\s+(\w+)\s*\{\s*\}', re.MULTILINE)
    for root, dirs, files in os.walk(root_dir):
        if "node_modules" in root:
            continue
        for file in files:
            if file.endswith('.ts') or file.endswith('.tsx'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        matches = pattern.finditer(content)
                        for match in matches:
                            print(f"Empty interface {match.group(1)} found in {path}")
                except Exception as e:
                    print(f"Error reading {path}: {e}")

if __name__ == "__main__":
    find_empty_interfaces("src")
