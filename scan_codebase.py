import os
import re
from collections import defaultdict

def scan_codebase(root_dir):
    # Regex for empty interfaces (handling extends and generics)
    # This is a basic approximation
    empty_interface_pattern = re.compile(r'interface\s+(\w+)(?:<[^>]+>)?(?:\s+extends\s+[^{]+)?\s*\{\s*\}', re.DOTALL)
    
    # Regex for type definitions
    type_def_pattern = re.compile(r'(?:export\s+)?(?:interface|type)\s+(\w+)', re.MULTILINE)

    definitions = defaultdict(list)

    for root, dirs, files in os.walk(root_dir):
        if "node_modules" in root:
            continue
        for file in files:
            if file.endswith('.ts') or file.endswith('.tsx'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                        # Find empty interfaces
                        matches = empty_interface_pattern.finditer(content)
                        for match in matches:
                            print(f"Empty interface '{match.group(1)}' found in {path}")
                        
                        # Find all definitions
                        type_matches = type_def_pattern.finditer(content)
                        for match in type_matches:
                            name = match.group(1)
                            # Ignore common names like Props unless we want to be strict
                            definitions[name].append(path)
                            
                except Exception as e:
                    print(f"Error reading {path}: {e}")

    # Check for duplicates
    for name, paths in definitions.items():
        if len(paths) > 1:
            # Filter imports/exports issues? No, regex finds definitions.
            # But we need to distinguish between 'interface Foo' and 'import { Foo }'
            # My regex checks for (export)? interface|type Foo
            # It won't match 'import { Foo }' 
            # It WILL match 'export type Foo = ...' or 'interface Foo {'
            
            # Check if paths are actually different files (not just same file multiple times)
            unique_paths = sorted(list(set(paths)))
            if len(unique_paths) > 1:
                # If it's "Props", ignore it usually
                if "Props" in name:
                    continue
                # LayoutProps, PageProps...
                
                print(f"Potential duplicate type '{name}' found in: {unique_paths}")

if __name__ == "__main__":
    scan_codebase("src")
