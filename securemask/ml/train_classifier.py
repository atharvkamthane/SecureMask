"""MobileNetV2 fine-tuning for 5-class document classification.

Dataset: synthetic images from generate_synthetic.py (ImageFolder layout).
Architecture: MobileNetV2 pretrained on ImageNet, final head → Linear(1280, 5).
Optimizer: Adam, lr=1e-4, weight_decay=1e-4, cosine LR scheduler.
Trains for 20 epochs, saves best checkpoint by val accuracy.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "synthetic_data"
WEIGHTS_DIR = SCRIPT_DIR / "weights"
CHECKPOINT_PATH = WEIGHTS_DIR / "classifier.pth"

CLASS_LABELS = ["aadhaar", "pan", "passport", "driving_license", "voter_id"]
NUM_CLASSES = len(CLASS_LABELS)
BATCH_SIZE = 32
NUM_EPOCHS = 20
LR = 1e-4
WEIGHT_DECAY = 1e-4
IMAGE_SIZE = 224


def get_transforms():
    train_transform = transforms.Compose([
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.RandomHorizontalFlip(p=0.1),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.1),
        transforms.RandomRotation(5),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    val_transform = transforms.Compose([
        transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    return train_transform, val_transform


def build_model() -> nn.Module:
    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT)
    # Freeze early layers
    for param in model.features[:14].parameters():
        param.requires_grad = False
    # Replace classifier head
    model.classifier = nn.Sequential(
        nn.Dropout(0.3),
        nn.Linear(model.last_channel, NUM_CLASSES),
    )
    return model


def train():
    if not (DATA_DIR / "train").exists():
        print("ERROR: Training data not found. Run generate_synthetic.py first.")
        sys.exit(1)

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    train_transform, val_transform = get_transforms()

    train_dataset = datasets.ImageFolder(DATA_DIR / "train", transform=train_transform)
    val_dataset = datasets.ImageFolder(DATA_DIR / "val", transform=val_transform)

    # Verify class order matches our expected labels
    print(f"Classes detected: {train_dataset.classes}")
    print(f"Expected classes: {CLASS_LABELS}")

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on: {device}")

    model = build_model().to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(filter(lambda p: p.requires_grad, model.parameters()),
                           lr=LR, weight_decay=WEIGHT_DECAY)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=NUM_EPOCHS)

    best_val_acc = 0.0

    for epoch in range(NUM_EPOCHS):
        # Train
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0

        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * images.size(0)
            _, predicted = torch.max(outputs, 1)
            train_correct += (predicted == labels).sum().item()
            train_total += labels.size(0)

        scheduler.step()

        train_acc = train_correct / train_total
        avg_train_loss = train_loss / train_total

        # Validate
        model.eval()
        val_correct = 0
        val_total = 0

        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                _, predicted = torch.max(outputs, 1)
                val_correct += (predicted == labels).sum().item()
                val_total += labels.size(0)

        val_acc = val_correct / val_total

        print(f"Epoch [{epoch+1}/{NUM_EPOCHS}]  "
              f"Train Loss: {avg_train_loss:.4f}  "
              f"Train Acc: {train_acc:.4f}  "
              f"Val Acc: {val_acc:.4f}  "
              f"LR: {scheduler.get_last_lr()[0]:.6f}")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            # Save with metadata
            torch.save({
                "model_state_dict": model.state_dict(),
                "class_labels": CLASS_LABELS,
                "class_to_idx": train_dataset.class_to_idx,
                "val_accuracy": val_acc,
                "epoch": epoch + 1,
            }, CHECKPOINT_PATH)
            print(f"  -> Saved best checkpoint (val_acc={val_acc:.4f})")

    print(f"\nTraining complete. Best val accuracy: {best_val_acc:.4f}")
    print(f"Checkpoint saved to: {CHECKPOINT_PATH}")


if __name__ == "__main__":
    train()
