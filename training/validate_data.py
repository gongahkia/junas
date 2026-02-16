"""
Dataset validation for caipng training pipeline.
Adapted from uh-kun's data_validate module.
Checks for corrupt images, duplicates, and dataset health.
"""
import os
import hashlib
from pathlib import Path
from collections import defaultdict
from PIL import Image
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

VALID_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff'}

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def validate_dataset(data_dir: str, max_side: int = 1024) -> dict:
    """Validate dataset directory for training readiness.
    Returns dict with stats and issues found."""
    data_path = Path(data_dir)
    if not data_path.exists():
        console.print(f"[red]Directory not found: {data_dir}[/red]")
        return {"valid": False, "error": "directory not found"}
    classes = sorted([d.name for d in data_path.iterdir() if d.is_dir()])
    if not classes:
        console.print(f"[red]No class subdirectories found in {data_dir}[/red]")
        return {"valid": False, "error": "no classes"}
    stats = {"total_images": 0, "classes": len(classes), "class_counts": {}, "corrupt": [], "duplicates": [], "oversized": [], "invalid_ext": [], "min_dim": None, "max_dim": None}
    hash_map = defaultdict(list) # sha256 -> [paths]
    for cls in classes:
        cls_dir = data_path / cls
        count = 0
        for f in cls_dir.iterdir():
            if not f.is_file():
                continue
            ext = f.suffix.lower()
            if ext not in VALID_EXTENSIONS:
                stats["invalid_ext"].append(str(f))
                continue
            # check corruption
            try:
                with Image.open(f) as img:
                    img.verify()
                with Image.open(f) as img:
                    w, h = img.size
                    if stats["min_dim"] is None:
                        stats["min_dim"] = (w, h)
                        stats["max_dim"] = (w, h)
                    else:
                        stats["min_dim"] = (min(stats["min_dim"][0], w), min(stats["min_dim"][1], h))
                        stats["max_dim"] = (max(stats["max_dim"][0], w), max(stats["max_dim"][1], h))
                    if max(w, h) > max_side:
                        stats["oversized"].append(str(f))
            except Exception:
                stats["corrupt"].append(str(f))
                continue
            # check duplicates
            fhash = sha256_file(str(f))
            hash_map[fhash].append(str(f))
            count += 1
            stats["total_images"] += 1
        stats["class_counts"][cls] = count
    # collect duplicates
    for h, paths in hash_map.items():
        if len(paths) > 1:
            stats["duplicates"].append(paths)
    stats["valid"] = len(stats["corrupt"]) == 0
    return stats

def print_validation_report(stats: dict):
    """Print validation results as Rich tables."""
    if "error" in stats:
        return
    # summary
    table = Table(title="Dataset Validation Report", box=box.ROUNDED)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="yellow", justify="right")
    table.add_row("Total Images", str(stats["total_images"]))
    table.add_row("Classes", str(stats["classes"]))
    if stats["min_dim"]:
        table.add_row("Min Dimensions", f"{stats['min_dim'][0]}x{stats['min_dim'][1]}")
        table.add_row("Max Dimensions", f"{stats['max_dim'][0]}x{stats['max_dim'][1]}")
    table.add_row("Corrupt Files", f"[{'red' if stats['corrupt'] else 'green'}]{len(stats['corrupt'])}[/]")
    table.add_row("Duplicate Sets", f"[{'yellow' if stats['duplicates'] else 'green'}]{len(stats['duplicates'])}[/]")
    table.add_row("Oversized (>{} px)".format(1024), f"[{'yellow' if stats['oversized'] else 'green'}]{len(stats['oversized'])}[/]")
    table.add_row("Invalid Extensions", f"[{'yellow' if stats['invalid_ext'] else 'green'}]{len(stats['invalid_ext'])}[/]")
    console.print(table)
    # per-class
    cls_table = Table(title="Per-Class Distribution", box=box.ROUNDED)
    cls_table.add_column("Class", style="cyan")
    cls_table.add_column("Count", justify="right")
    cls_table.add_column("Status", justify="center")
    for cls, count in sorted(stats["class_counts"].items()):
        status = "[green]OK[/green]" if count >= 10 else "[yellow]LOW[/yellow]" if count > 0 else "[red]EMPTY[/red]"
        cls_table.add_row(cls, str(count), status)
    console.print(cls_table)
    # issues
    if stats["corrupt"]:
        console.print("\n[red bold]Corrupt files:[/red bold]")
        for p in stats["corrupt"][:10]:
            console.print(f"  [red]{p}[/red]")
        if len(stats["corrupt"]) > 10:
            console.print(f"  ... and {len(stats['corrupt'])-10} more")
    if stats["duplicates"]:
        console.print(f"\n[yellow bold]Duplicate sets ({len(stats['duplicates'])}):[/yellow bold]")
        for paths in stats["duplicates"][:5]:
            console.print(f"  [yellow]{' <-> '.join(os.path.basename(p) for p in paths)}[/yellow]")

if __name__ == '__main__':
    import sys
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "./data/organized"
    stats = validate_dataset(data_dir)
    print_validation_report(stats)
