import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
from torchvision import models
import argparse
import os
from dataset import CaiFanDataset, get_transforms
from tqdm import tqdm
import json

def train_model(data_dir, output_dir, epochs=10, batch_size=32, learning_rate=0.001):
    # Device configuration
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")

    # Prepare directories
    os.makedirs(output_dir, exist_ok=True)

    # Load Dataset
    print(f"Loading data from {data_dir}...")
    try:
        full_dataset = CaiFanDataset(data_dir, transform=get_transforms(train=True))
    except Exception as e:
        print(f"Error loading dataset: {e}")
        print("Please ensure your data is organized as: data_dir/class_name/image.jpg")
        return

    train_size = int(0.8 * len(full_dataset))
    val_size = len(full_dataset) - train_size
    train_dataset, val_dataset = random_split(full_dataset, [train_size, val_size])
    
    # Update transform for validation
    val_dataset.dataset.transform = get_transforms(train=False)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=4)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=4)
    
    print(f"Classes: {full_dataset.classes}")
    num_classes = len(full_dataset.classes)
    
    # Save class mapping
    class_mapping = {i: cls for i, cls in enumerate(full_dataset.classes)}
    with open(os.path.join(output_dir, 'classes.json'), 'w') as f:
        json.dump(class_mapping, f, indent=2)

    # Model (MobileNetV3 Small for efficiency)
    model = models.mobilenet_v3_small(weights='DEFAULT')
    # Replace last layer
    model.classifier[3] = nn.Linear(model.classifier[3].in_features, num_classes)
    model = model.to(device)

    # Loss and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)

    # Training Loop
    for epoch in range(epochs):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0
        
        loop = tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs} [Train]")
        for images, labels in loop:
            images = images.to(device)
            labels = labels.to(device)

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item()
            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
            
            loop.set_postfix(loss=running_loss/len(train_loader), acc=100*correct/total)

        # Validation
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for images, labels in val_loader:
                images = images.to(device)
                labels = labels.to(device)
                outputs = model(images)
                loss = criterion(outputs, labels)
                val_loss += loss.item()
                _, predicted = torch.max(outputs.data, 1)
                val_total += labels.size(0)
                val_correct += (predicted == labels).sum().item()

        print(f"Epoch {epoch+1} Validation Accuracy: {100*val_correct/val_total:.2f}%")

    # Save PyTorch Model
    torch.save(model.state_dict(), os.path.join(output_dir, 'caifan_model.pth'))
    print("Training complete. Model saved.")
    
    # Export to ONNX
    print("Exporting to ONNX...")
    dummy_input = torch.randn(1, 3, 224, 224).to(device)
    onnx_path = os.path.join(output_dir, 'caifan_model.onnx')
    torch.onnx.export(model, dummy_input, onnx_path, 
                      input_names=['input'], output_names=['output'],
                      dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}})
    print(f"ONNX model saved to {onnx_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Train Cai Fan Classifier')
    parser.add_argument('--data_dir', type=str, required=True, help='Path to dataset directory')
    parser.add_argument('--output_dir', type=str, default='models', help='Directory to save models')
    parser.add_argument('--epochs', type=int, default=10, help='Number of epochs')
    args = parser.parse_args()
    
    train_model(args.data_dir, args.output_dir, epochs=args.epochs)
