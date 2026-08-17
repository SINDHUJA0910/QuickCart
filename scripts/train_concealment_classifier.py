"""
Training harness for a concealment-gesture classifier.

WHAT THIS IS: a ready-to-run training script for fine-tuning a video-action
classifier on YOUR OWN labeled footage. It does NOT ship with pretrained
weights for this task, because none exist for "customer conceals a product"
— this is not a task covered by any public pretrained model, unlike person
detection (COCO) which is.

WHAT YOU NEED BEFORE RUNNING THIS:
  1. Labeled video clips: short (2-4 second) clips of your own store's CCTV
     footage, each labeled as one of a small set of classes, e.g.:
       - "normal_pickup"       (customer picks up an item normally)
       - "concealment"         (customer conceals an item — pocket, bag, clothing)
       - "normal_browsing"     (customer browses without picking anything up)
     A realistic starting point is 200-500 clips per class, ideally from
     multiple cameras/angles/lighting conditions at your actual store(s).
     This data does not exist yet for QuickCart and can only come from your
     own footage with real consent/privacy processes in place — that's a
     legal and operational step, not just a technical one.

  2. Clips organized as:
       dataset/
         train/normal_pickup/clip001.mp4 ...
         train/concealment/clip001.mp4 ...
         train/normal_browsing/clip001.mp4 ...
         val/normal_pickup/...
         val/concealment/...
         val/normal_browsing/...

HOW THIS FITS THE REST OF THE PIPELINE: once trained, the resulting
classifier would run on the cropped bounding-box region of a tracked person
(from app/ai/tracking/tracker.py's TrackedPerson) over a short rolling
window of frames, as an additional signal alongside the shelf-activity
mismatch engine (app/ai/theft_logic/mismatch_engine.py) — not a replacement
for it. A new `severity` contribution / `reason` value
("concealment_gesture") would be added to ai_alert_service.create_alert
once this model exists.

This script uses a small 3D-CNN (r3d_18 from torchvision, pretrained on
Kinetics-400 for general action recognition, then fine-tuned here) as a
reasonable, resource-light starting architecture — swap for a larger
video transformer if you have more data and compute later.

Run:
    python scripts/train_concealment_classifier.py --data-dir ./dataset --epochs 15
"""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Fine-tune a concealment-gesture classifier on labeled clips.")
    parser.add_argument("--data-dir", type=Path, required=True, help="Path to dataset/ (see module docstring for layout)")
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--output", type=Path, default=Path("concealment_classifier.pt"))
    args = parser.parse_args()

    if not args.data_dir.exists():
        raise SystemExit(
            f"'{args.data_dir}' does not exist. This script cannot run without your own "
            f"labeled clips — see this file's module docstring for the required dataset layout "
            f"and why no pretrained weights are bundled for this task."
        )

    # Imported here, not at module load, so this file can be inspected/reviewed
    # without requiring torchvision to be installed unless someone actually
    # runs a training job.
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader
    from torchvision.datasets import VisionDataset
    from torchvision.io import read_video
    from torchvision.models.video import r3d_18, R3D_18_Weights

    class ClipDataset(VisionDataset):
        """Loads fixed-length clips from the train/ or val/ directory layout
        described in the module docstring. Each class subdirectory becomes a label."""

        def __init__(self, root: Path, clip_frames: int = 16):
            super().__init__(str(root))
            self.clip_frames = clip_frames
            self.classes = sorted(p.name for p in root.iterdir() if p.is_dir())
            self.samples = [
                (str(f), self.classes.index(cls))
                for cls in self.classes
                for f in (root / cls).glob("*.mp4")
            ]
            if not self.samples:
                raise SystemExit(f"No .mp4 clips found under {root} — check the dataset layout.")

        def __len__(self):
            return len(self.samples)

        def __getitem__(self, idx):
            path, label = self.samples[idx]
            video, _, _ = read_video(path, pts_unit="sec")
            video = video[: self.clip_frames].permute(3, 0, 1, 2).float() / 255.0
            if video.shape[1] < self.clip_frames:
                pad = self.clip_frames - video.shape[1]
                video = nn.functional.pad(video, (0, 0, 0, 0, 0, pad))
            return video, label

    train_set = ClipDataset(args.data_dir / "train")
    val_set = ClipDataset(args.data_dir / "val")
    train_loader = DataLoader(train_set, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_set, batch_size=args.batch_size)

    model = r3d_18(weights=R3D_18_Weights.KINETICS400_V1)
    model.fc = nn.Linear(model.fc.in_features, len(train_set.classes))

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    criterion = nn.CrossEntropyLoss()

    for epoch in range(args.epochs):
        model.train()
        total_loss = 0.0
        for clips, labels in train_loader:
            clips, labels = clips.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(clips), labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        model.eval()
        correct = total = 0
        with torch.no_grad():
            for clips, labels in val_loader:
                clips, labels = clips.to(device), labels.to(device)
                preds = model(clips).argmax(dim=1)
                correct += (preds == labels).sum().item()
                total += labels.size(0)

        val_acc = correct / total if total else 0.0
        print(f"epoch {epoch+1}/{args.epochs}  train_loss={total_loss/len(train_loader):.4f}  val_acc={val_acc:.3f}")

    torch.save({"model_state": model.state_dict(), "classes": train_set.classes}, args.output)
    print(f"Saved fine-tuned model to {args.output}")


if __name__ == "__main__":
    main()
