"""
Interactive TUI for Training Food Recognition Model
Provides rich terminal interface for model training, evaluation, and export
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
from torchvision import models
import os
import json
import time
from pathlib import Path
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn, TimeElapsedColumn
from rich.prompt import Prompt, Confirm
from rich import box
from rich.text import Text

from dataset import CaiFanDataset, get_transforms
from metrics import evaluate_model, print_confusion_matrix, print_classification_report
from validate_data import validate_dataset, print_validation_report

console = Console()

class TrainingTUI:
    def __init__(self):
        self.config = {
            'data_dir': None,
            'output_dir': './models',
            'epochs': 10,
            'batch_size': 32,
            'learning_rate': 0.001,
            'train_split': 0.8,
            'num_workers': 4,
            'device': 'cuda' if torch.cuda.is_available() else 'cpu'
        }
        self.model = None
        self.device = None
        self.train_loader = None
        self.val_loader = None
        self.classes = None
        
    def display_banner(self):
        """Display welcome banner"""
        banner = Panel(
            "[bold cyan]🍱 Cai Fan Neural Network Training TUI[/bold cyan]\n"
            "[dim]Train a real food recognition model for your backend[/dim]",
            box=box.DOUBLE,
            border_style="cyan"
        )
        console.print(banner)
        
    def configure_training(self):
        """Interactive configuration"""
        console.print("\n[bold yellow]⚙️  Configuration[/bold yellow]", style="bold")
        console.print("=" * 60)
        
        # Data directory
        default_data = "./data/organized"
        self.config['data_dir'] = Prompt.ask(
            "📁 Dataset directory",
            default=default_data
        )
        
        if not os.path.exists(self.config['data_dir']):
            console.print(f"[red]✗ Directory not found: {self.config['data_dir']}[/red]")
            console.print("[yellow]💡 Tip: Run 'python download_data.py' first[/yellow]")
            return False
        
        # Output directory
        self.config['output_dir'] = Prompt.ask(
            "💾 Output directory for models",
            default=self.config['output_dir']
        )
        
        # Training parameters
        self.config['epochs'] = int(Prompt.ask(
            "🔄 Number of epochs",
            default=str(self.config['epochs'])
        ))
        
        self.config['batch_size'] = int(Prompt.ask(
            "📦 Batch size",
            default=str(self.config['batch_size'])
        ))
        
        self.config['learning_rate'] = float(Prompt.ask(
            "📈 Learning rate",
            default=str(self.config['learning_rate'])
        ))
        
        # Display summary
        console.print("\n[bold green]✓ Configuration Summary[/bold green]")
        config_table = Table(box=box.SIMPLE)
        config_table.add_column("Parameter", style="cyan")
        config_table.add_column("Value", style="yellow")
        
        for key, value in self.config.items():
            config_table.add_row(key, str(value))
        
        console.print(config_table)
        
        return Confirm.ask("\n[bold]Proceed with training?[/bold]", default=True)
    
    def load_dataset(self):
        """Load and prepare dataset"""
        console.print("\n[bold yellow]📊 Loading Dataset[/bold yellow]")
        console.print("=" * 60)

        # Validate dataset first
        console.print("[bold]Running dataset validation...[/bold]")
        vstats = validate_dataset(self.config['data_dir'])
        print_validation_report(vstats)
        if vstats.get("corrupt"):
            console.print(f"[yellow]⚠️  {len(vstats['corrupt'])} corrupt files found. They may cause errors during training.[/yellow]")

        with console.status("[bold green]Loading dataset...", spinner="dots"):
            try:
                full_dataset = CaiFanDataset(
                    self.config['data_dir'],
                    transform=get_transforms(train=True)
                )
                
                train_size = int(self.config['train_split'] * len(full_dataset))
                val_size = len(full_dataset) - train_size
                train_dataset, val_dataset = random_split(
                    full_dataset,
                    [train_size, val_size]
                )
                
                # Update validation transform
                val_dataset.dataset.transform = get_transforms(train=False)
                
                self.train_loader = DataLoader(
                    train_dataset,
                    batch_size=self.config['batch_size'],
                    shuffle=True,
                    num_workers=self.config['num_workers']
                )
                
                self.val_loader = DataLoader(
                    val_dataset,
                    batch_size=self.config['batch_size'],
                    shuffle=False,
                    num_workers=self.config['num_workers']
                )
                
                self.classes = full_dataset.classes
                
                # Display dataset info
                dataset_table = Table(title="Dataset Statistics", box=box.ROUNDED)
                dataset_table.add_column("Metric", style="cyan")
                dataset_table.add_column("Value", style="yellow", justify="right")
                
                dataset_table.add_row("Total Images", f"{len(full_dataset):,}")
                dataset_table.add_row("Training Images", f"{train_size:,}")
                dataset_table.add_row("Validation Images", f"{val_size:,}")
                dataset_table.add_row("Number of Classes", str(len(self.classes)))
                dataset_table.add_row("Batches per Epoch", str(len(self.train_loader)))
                
                console.print(dataset_table)
                
                # Show sample classes
                console.print(f"\n[bold]Sample Classes:[/bold] {', '.join(self.classes[:10])}...")
                
                return True
                
            except Exception as e:
                console.print(f"[red]✗ Failed to load dataset: {e}[/red]")
                return False
    
    def initialize_model(self):
        """Initialize model architecture"""
        console.print("\n[bold yellow]🧠 Initializing Model[/bold yellow]")
        console.print("=" * 60)
        
        with console.status("[bold green]Building model...", spinner="dots"):
            self.device = torch.device(self.config['device'])
            
            # Use MobileNetV3 for efficiency
            self.model = models.mobilenet_v3_small(weights='DEFAULT')
            
            # Replace classifier for our number of classes
            num_classes = len(self.classes)
            self.model.classifier[3] = nn.Linear(
                self.model.classifier[3].in_features,
                num_classes
            )
            
            self.model = self.model.to(self.device)
            
            # Count parameters
            total_params = sum(p.numel() for p in self.model.parameters())
            trainable_params = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
            
            model_table = Table(title="Model Architecture", box=box.ROUNDED)
            model_table.add_column("Property", style="cyan")
            model_table.add_column("Value", style="yellow")
            
            model_table.add_row("Architecture", "MobileNetV3-Small")
            model_table.add_row("Output Classes", str(num_classes))
            model_table.add_row("Total Parameters", f"{total_params:,}")
            model_table.add_row("Trainable Parameters", f"{trainable_params:,}")
            model_table.add_row("Device", str(self.device).upper())
            
            console.print(model_table)
        
        return True
    
    def train_epoch(self, epoch, optimizer, criterion, progress, task):
        """Train for one epoch"""
        self.model.train()
        running_loss = 0.0
        correct = 0
        total = 0
        
        for batch_idx, (images, labels) in enumerate(self.train_loader):
            images = images.to(self.device)
            labels = labels.to(self.device)
            
            optimizer.zero_grad()
            outputs = self.model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item()
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
            
            # Update progress
            progress.update(
                task,
                advance=1,
                description=f"[cyan]Epoch {epoch}/{self.config['epochs']} [Train] - "
                           f"Loss: {running_loss/(batch_idx+1):.4f}, "
                           f"Acc: {100*correct/total:.2f}%"
            )
        
        epoch_loss = running_loss / len(self.train_loader)
        epoch_acc = 100 * correct / total
        
        return epoch_loss, epoch_acc
    
    def validate_epoch(self, epoch, criterion, progress, task):
        """Validate model"""
        self.model.eval()
        val_loss = 0.0
        correct = 0
        total = 0
        
        with torch.no_grad():
            for batch_idx, (images, labels) in enumerate(self.val_loader):
                images = images.to(self.device)
                labels = labels.to(self.device)
                
                outputs = self.model(images)
                loss = criterion(outputs, labels)
                
                val_loss += loss.item()
                _, predicted = torch.max(outputs.data, 1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()
                
                # Update progress
                progress.update(
                    task,
                    advance=1,
                    description=f"[magenta]Epoch {epoch}/{self.config['epochs']} [Val] - "
                               f"Loss: {val_loss/(batch_idx+1):.4f}, "
                               f"Acc: {100*correct/total:.2f}%"
                )
        
        epoch_loss = val_loss / len(self.val_loader)
        epoch_acc = 100 * correct / total
        
        return epoch_loss, epoch_acc
    
    def train(self):
        """Main training loop with rich UI"""
        console.print("\n[bold yellow]🚀 Starting Training[/bold yellow]")
        console.print("=" * 60)
        
        # Prepare output directory
        os.makedirs(self.config['output_dir'], exist_ok=True)
        
        # Save configuration
        config_path = os.path.join(self.config['output_dir'], 'config.json')
        with open(config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        
        # Save class mapping
        class_mapping = {i: cls for i, cls in enumerate(self.classes)}
        classes_path = os.path.join(self.config['output_dir'], 'classes.json')
        with open(classes_path, 'w') as f:
            json.dump(class_mapping, f, indent=2)
        
        # Initialize training
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(self.model.parameters(), lr=self.config['learning_rate'])
        
        # Training history
        history = {
            'train_loss': [],
            'train_acc': [],
            'val_loss': [],
            'val_acc': []
        }
        
        best_val_acc = 0.0
        start_time = time.time()
        
        # Training loop with progress bars
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            
            for epoch in range(1, self.config['epochs'] + 1):
                # Train
                train_task = progress.add_task(
                    f"[cyan]Epoch {epoch}/{self.config['epochs']} [Train]",
                    total=len(self.train_loader)
                )
                train_loss, train_acc = self.train_epoch(epoch, optimizer, criterion, progress, train_task)
                progress.remove_task(train_task)
                
                # Validate
                val_task = progress.add_task(
                    f"[magenta]Epoch {epoch}/{self.config['epochs']} [Val]",
                    total=len(self.val_loader)
                )
                val_loss, val_acc = self.validate_epoch(epoch, criterion, progress, val_task)
                progress.remove_task(val_task)
                
                # Record history
                history['train_loss'].append(train_loss)
                history['train_acc'].append(train_acc)
                history['val_loss'].append(val_loss)
                history['val_acc'].append(val_acc)
                
                # Display epoch summary
                console.print(
                    f"\n[bold green]Epoch {epoch}/{self.config['epochs']}:[/bold green] "
                    f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.2f}% | "
                    f"Val Loss: {val_loss:.4f}, Val Acc: [yellow]{val_acc:.2f}%[/yellow]"
                )
                
                # Save best model
                if val_acc > best_val_acc:
                    best_val_acc = val_acc
                    best_model_path = os.path.join(self.config['output_dir'], 'best_model.pth')
                    torch.save(self.model.state_dict(), best_model_path)
                    console.print(f"[green]✓ Best model saved (Val Acc: {val_acc:.2f}%)[/green]")
        
        # Training complete
        total_time = time.time() - start_time
        
        console.print("\n[bold green]✓ Training Complete![/bold green]")
        
        summary_table = Table(title="Training Summary", box=box.ROUNDED)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="yellow")
        
        summary_table.add_row("Total Time", f"{total_time/60:.2f} minutes")
        summary_table.add_row("Best Validation Accuracy", f"{best_val_acc:.2f}%")
        summary_table.add_row("Final Train Accuracy", f"{history['train_acc'][-1]:.2f}%")
        summary_table.add_row("Final Val Accuracy", f"{history['val_acc'][-1]:.2f}%")
        
        console.print(summary_table)
        
        # Save final model
        final_model_path = os.path.join(self.config['output_dir'], 'caifan_model.pth')
        torch.save(self.model.state_dict(), final_model_path)

        # Save history
        history_path = os.path.join(self.config['output_dir'], 'history.json')
        with open(history_path, 'w') as f:
            json.dump(history, f, indent=2)

        # Run detailed evaluation on validation set
        console.print("\n[bold yellow]📊 Detailed Evaluation[/bold yellow]")
        console.print("=" * 60)

        # Load best model for evaluation
        best_path = os.path.join(self.config['output_dir'], 'best_model.pth')
        if os.path.exists(best_path):
            self.model.load_state_dict(torch.load(best_path, map_location=self.device))

        eval_results = evaluate_model(self.model, self.val_loader, self.classes, self.device)
        print_confusion_matrix(eval_results["confusion_matrix"], self.classes)
        print_classification_report(eval_results["per_class"], eval_results["accuracy"])

        # Save eval results
        eval_path = os.path.join(self.config['output_dir'], 'eval_results.json')
        eval_export = {
            "accuracy": eval_results["accuracy"],
            "avg_loss": eval_results["avg_loss"],
            "per_class": {k: {"precision": v.precision, "recall": v.recall, "f1": v.f1, "support": v.support} for k, v in eval_results["per_class"].items()}
        }
        with open(eval_path, 'w') as f:
            json.dump(eval_export, f, indent=2)
        console.print(f"[green]✓ Eval results saved to {eval_path}[/green]")

        return True
    
    def export_onnx(self):
        """Export model to ONNX format"""
        console.print("\n[bold yellow]📦 Exporting to ONNX[/bold yellow]")
        console.print("=" * 60)
        
        with console.status("[bold green]Exporting model...", spinner="dots"):
            try:
                dummy_input = torch.randn(1, 3, 224, 224).to(self.device)
                onnx_path = os.path.join(self.config['output_dir'], 'caifan_model.onnx')
                
                torch.onnx.export(
                    self.model,
                    dummy_input,
                    onnx_path,
                    input_names=['input'],
                    output_names=['output'],
                    dynamic_axes={
                        'input': {0: 'batch_size'},
                        'output': {0: 'batch_size'}
                    },
                    opset_version=12
                )
                
                console.print(f"[green]✓ ONNX model exported to: {onnx_path}[/green]")
                
                # Display file sizes
                pth_size = os.path.getsize(os.path.join(self.config['output_dir'], 'caifan_model.pth')) / 1024 / 1024
                onnx_size = os.path.getsize(onnx_path) / 1024 / 1024
                
                export_table = Table(box=box.ROUNDED)
                export_table.add_column("Format", style="cyan")
                export_table.add_column("Size", style="yellow")
                export_table.add_column("Purpose", style="dim")
                
                export_table.add_row("PyTorch (.pth)", f"{pth_size:.2f} MB", "Python training/inference")
                export_table.add_row("ONNX (.onnx)", f"{onnx_size:.2f} MB", "Node.js backend inference")
                
                console.print(export_table)
                
                return True
                
            except Exception as e:
                console.print(f"[red]✗ Export failed: {e}[/red]")
                return False
    
    def run(self):
        """Run the complete training pipeline"""
        self.display_banner()
        
        if not self.configure_training():
            console.print("[yellow]Training cancelled.[/yellow]")
            return
        
        if not self.load_dataset():
            return
        
        if not self.initialize_model():
            return
        
        if not self.train():
            return
        
        if Confirm.ask("\n[bold]Export model to ONNX for backend?[/bold]", default=True):
            self.export_onnx()
        
        # Final instructions
        console.print("\n[bold green]🎉 All Done![/bold green]")
        console.print(Panel(
            f"[bold]Next Steps:[/bold]\n\n"
            f"1. Your trained model is at: [cyan]{self.config['output_dir']}/caifan_model.onnx[/cyan]\n"
            f"2. Copy it to the backend: [cyan]cp {self.config['output_dir']}/caifan_model.onnx ../backend/models/[/cyan]\n"
            f"3. Copy classes.json too: [cyan]cp {self.config['output_dir']}/classes.json ../backend/models/[/cyan]\n"
            f"4. Restart your backend server to use the new model!",
            border_style="green",
            box=box.DOUBLE
        ))

if __name__ == '__main__':
    tui = TrainingTUI()
    tui.run()
