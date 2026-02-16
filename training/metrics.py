"""
Evaluation metrics for food classification model.
Adapted from uh-kun's metrics module for caipng training pipeline.
Provides confusion matrix, per-class P/R/F1, and summary reporting.
"""
import torch
import torch.nn as nn
from collections import defaultdict
from dataclasses import dataclass
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

@dataclass(frozen=True)
class PerClassMetrics:
    precision: float
    recall: float
    f1: float
    support: int

def confusion_matrix_counts(y_true: list[str], y_pred: list[str], labels: list[str]) -> dict[str, dict[str, int]]:
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have same length")
    out = {t: {p: 0 for p in labels} for t in labels}
    for t, p in zip(y_true, y_pred):
        if t in out and p in out[t]:
            out[t][p] += 1
    return out

def per_class_prf1(cm: dict[str, dict[str, int]], labels: list[str]) -> dict[str, PerClassMetrics]:
    metrics = {}
    for lab in labels:
        tp = cm.get(lab, {}).get(lab, 0)
        fn = sum(cm.get(lab, {}).get(p, 0) for p in labels if p != lab)
        fp = sum(cm.get(t, {}).get(lab, 0) for t in labels if t != lab)
        support = sum(cm.get(lab, {}).get(p, 0) for p in labels)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        metrics[lab] = PerClassMetrics(precision=prec, recall=rec, f1=f1, support=support)
    return metrics

@torch.no_grad()
def evaluate_model(model, dataloader, classes, device):
    """Run full evaluation: accuracy, confusion matrix, per-class P/R/F1."""
    model.eval()
    y_true, y_pred = [], []
    total_loss = 0.0
    criterion = nn.CrossEntropyLoss()
    for images, labels in dataloader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        total_loss += criterion(outputs, labels).item()
        _, predicted = torch.max(outputs, 1)
        for t, p in zip(labels.cpu().tolist(), predicted.cpu().tolist()):
            y_true.append(classes[t])
            y_pred.append(classes[p])
    avg_loss = total_loss / len(dataloader) if len(dataloader) > 0 else 0.0
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    accuracy = correct / len(y_true) if y_true else 0.0
    cm = confusion_matrix_counts(y_true, y_pred, classes)
    prf1 = per_class_prf1(cm, classes)
    return {"accuracy": accuracy, "avg_loss": avg_loss, "confusion_matrix": cm, "per_class": prf1, "y_true": y_true, "y_pred": y_pred}

def print_confusion_matrix(cm: dict[str, dict[str, int]], labels: list[str]):
    """Print confusion matrix as a Rich table."""
    table = Table(title="Confusion Matrix", box=box.ROUNDED)
    table.add_column("True \\ Pred", style="bold cyan")
    for lab in labels:
        table.add_column(lab[:12], justify="right")
    for true_lab in labels:
        row = [true_lab[:12]]
        for pred_lab in labels:
            val = cm[true_lab][pred_lab]
            style = "bold green" if true_lab == pred_lab and val > 0 else ("red" if val > 0 else "dim")
            row.append(f"[{style}]{val}[/{style}]")
        table.add_row(*row)
    console.print(table)

def print_classification_report(prf1: dict[str, PerClassMetrics], accuracy: float):
    """Print per-class metrics as a Rich table."""
    table = Table(title="Classification Report", box=box.ROUNDED)
    table.add_column("Class", style="cyan")
    table.add_column("Precision", justify="right")
    table.add_column("Recall", justify="right")
    table.add_column("F1", justify="right")
    table.add_column("Support", justify="right", style="dim")
    total_support = 0
    weighted_f1 = 0.0
    for cls, m in prf1.items():
        table.add_row(cls[:20], f"{m.precision:.3f}", f"{m.recall:.3f}", f"{m.f1:.3f}", str(m.support))
        total_support += m.support
        weighted_f1 += m.f1 * m.support
    macro_f1 = sum(m.f1 for m in prf1.values()) / len(prf1) if prf1 else 0.0
    w_f1 = weighted_f1 / total_support if total_support > 0 else 0.0
    table.add_section()
    table.add_row("[bold]Overall[/bold]", "", "", f"[bold]{macro_f1:.3f}[/bold] macro", str(total_support))
    table.add_row("", "", "", f"[bold]{w_f1:.3f}[/bold] weighted", "")
    table.add_row("[bold]Accuracy[/bold]", "", "", f"[bold yellow]{accuracy:.3f}[/bold yellow]", "")
    console.print(table)
