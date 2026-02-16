"""
Data Download Script for Food Recognition Training
Downloads Food-101 dataset and prepares it for training
"""

import os
import tarfile
import urllib.request
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
import shutil

console = Console()

FOOD101_URL = "http://data.vision.ee.ethz.ch/cvl/food-101.tar.gz"
DATASET_DIR = Path("./data")

def download_with_progress(url, dest_path):
    """Download file with progress bar"""
    
    class DownloadProgressBar():
        def __init__(self):
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
            )
            self.task = None
            
        def __call__(self, block_num, block_size, total_size):
            if self.task is None:
                self.progress.start()
                self.task = self.progress.add_task("Downloading...", total=total_size)
            downloaded = block_num * block_size
            if downloaded < total_size:
                self.progress.update(self.task, completed=downloaded)
            else:
                self.progress.update(self.task, completed=total_size)
                
    dpb = DownloadProgressBar()
    urllib.request.urlretrieve(url, dest_path, reporthook=dpb)
    if dpb.progress:
        dpb.progress.stop()

def download_food101():
    """Download and extract Food-101 dataset"""
    
    console.print("\n[bold cyan]Food-101 Dataset Downloader[/bold cyan]")
    console.print("=" * 60)
    
    # Create data directory
    DATASET_DIR.mkdir(exist_ok=True)
    
    tar_path = DATASET_DIR / "food-101.tar.gz"
    
    # Download if not exists
    if not tar_path.exists():
        console.print(f"\n[yellow]Downloading Food-101 dataset from {FOOD101_URL}[/yellow]")
        console.print("[dim]This is ~5GB and may take a while...[/dim]\n")
        
        try:
            download_with_progress(FOOD101_URL, str(tar_path))
            console.print("\n[green]✓ Download complete![/green]")
        except Exception as e:
            console.print(f"\n[red]✗ Download failed: {e}[/red]")
            return False
    else:
        console.print(f"\n[green]✓ Dataset archive already exists at {tar_path}[/green]")
    
    # Extract
    extract_dir = DATASET_DIR / "food-101"
    if not extract_dir.exists():
        console.print(f"\n[yellow]Extracting dataset...[/yellow]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Extracting...", total=None)
            
            try:
                with tarfile.open(tar_path, 'r:gz') as tar:
                    tar.extractall(path=DATASET_DIR)
                progress.update(task, completed=100)
                console.print("[green]✓ Extraction complete![/green]")
            except Exception as e:
                console.print(f"[red]✗ Extraction failed: {e}[/red]")
                return False
    else:
        console.print(f"[green]✓ Dataset already extracted at {extract_dir}[/green]")
    
    # Organize for PyTorch (images/class_name/img.jpg)
    organized_dir = DATASET_DIR / "organized"
    if not organized_dir.exists():
        console.print(f"\n[yellow]Organizing dataset for training...[/yellow]")
        organized_dir.mkdir(exist_ok=True)
        
        images_src = extract_dir / "images"
        
        with Progress(console=console) as progress:
            classes = sorted([d for d in images_src.iterdir() if d.is_dir()])
            task = progress.add_task("[cyan]Organizing files...", total=len(classes))
            
            for class_dir in classes:
                dest_class_dir = organized_dir / class_dir.name
                if not dest_class_dir.exists():
                    shutil.copytree(class_dir, dest_class_dir)
                progress.advance(task)
        
        console.print("[green]✓ Dataset organized![/green]")
    else:
        console.print(f"[green]✓ Dataset already organized at {organized_dir}[/green]")
    
    # Display stats
    console.print("\n[bold green]Dataset Ready![/bold green]")
    console.print(f"📁 Location: [cyan]{organized_dir}[/cyan]")
    
    class_count = len(list(organized_dir.iterdir()))
    total_images = sum(len(list(d.glob('*.jpg'))) for d in organized_dir.iterdir())
    
    console.print(f"📊 Classes: [yellow]{class_count}[/yellow]")
    console.print(f"🖼️  Images: [yellow]{total_images:,}[/yellow]")
    console.print(f"\n[dim]Use this path for training: {organized_dir.absolute()}[/dim]\n")
    
    return True

def download_sample_dataset():
    """Download a smaller sample dataset for quick testing"""
    console.print("\n[bold cyan]Sample Dataset (Testing Mode)[/bold cyan]")
    console.print("=" * 60)
    
    sample_dir = DATASET_DIR / "sample"
    sample_dir.mkdir(exist_ok=True, parents=True)
    
    # Create sample structure with placeholder info
    console.print("\n[yellow]Creating sample dataset structure...[/yellow]")
    console.print("[dim]For production, use the full Food-101 dataset[/dim]\n")
    
    sample_classes = ['chicken_rice', 'char_siew', 'vegetables', 'tofu', 'fish']
    
    for cls in sample_classes:
        (sample_dir / cls).mkdir(exist_ok=True)
    
    console.print("[green]✓ Sample directory structure created![/green]")
    console.print(f"📁 Location: [cyan]{sample_dir}[/cyan]")
    console.print("\n[yellow]⚠️  Add your own images to train on real data[/yellow]")
    console.print(f"[dim]Place images in: {sample_dir}/[class_name]/image.jpg[/dim]\n")
    
    return True

if __name__ == '__main__':
    import sys
    
    if '--sample' in sys.argv:
        download_sample_dataset()
    else:
        download_food101()
