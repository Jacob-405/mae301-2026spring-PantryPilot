import argparse
import math
import time
from pathlib import Path

import numpy as np
import torch
import yaml

from model import GPT, GPTConfig


def load_bin(path: Path) -> np.memmap:
    # written as uint16 in prepare script
    return np.memmap(path, dtype=np.uint16, mode="r")


def get_batch(data: np.memmap, batch_size: int, block_size: int, device: str):
    # sample random contiguous chunks
    ix = torch.randint(len(data) - block_size - 1, (batch_size,))
    x = torch.stack([torch.from_numpy((data[i : i + block_size]).astype(np.int64)) for i in ix])
    y = torch.stack([torch.from_numpy((data[i + 1 : i + 1 + block_size]).astype(np.int64)) for i in ix])
    return x.to(device), y.to(device)


@torch.no_grad()
def estimate_loss(model, train_data, val_data, eval_iters, batch_size, block_size, device):
    model.eval()
    out = {}
    for split, data in [("train", train_data), ("val", val_data)]:
        losses = torch.zeros(eval_iters)
        for k in range(eval_iters):
            xb, yb = get_batch(data, batch_size, block_size, device)
            _, loss = model(xb, yb)
            losses[k] = loss.item()
        out[split] = losses.mean().item()
    model.train()
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())

    repo_root = Path(__file__).resolve().parents[2]
    data_dir = repo_root / cfg["data_dir"]
    out_dir = repo_root / cfg["out_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.manual_seed(cfg.get("seed", 1337))

    train_data = load_bin(data_dir / "train.bin")
    val_data = load_bin(data_dir / "val.bin")

    model_cfg = GPTConfig(
        vocab_size=cfg["vocab_size"],
        block_size=cfg["block_size"],
        n_layer=cfg["n_layer"],
        n_head=cfg["n_head"],
        n_embd=cfg["n_embd"],
        dropout=cfg.get("dropout", 0.1),
    )
    model = GPT(model_cfg).to(device)

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=cfg["learning_rate"],
        betas=(0.9, 0.95),
        weight_decay=cfg.get("weight_decay", 0.1),
    )

    # mixed precision helps on 8GB
    use_amp = bool(cfg.get("use_amp", True)) and device == "cuda"
    scaler = torch.cuda.amp.GradScaler(enabled=use_amp)

    batch_size = cfg["batch_size"]
    block_size = cfg["block_size"]
    max_iters = cfg["max_iters"]
    eval_interval = cfg["eval_interval"]
    eval_iters = cfg["eval_iters"]
    grad_clip = cfg.get("grad_clip", 1.0)

    best_val = float("inf")
    t0 = time.time()

    for it in range(1, max_iters + 1):
        xb, yb = get_batch(train_data, batch_size, block_size, device)

        # forward + backward (amp)
        with torch.cuda.amp.autocast(enabled=use_amp):
            _, loss = model(xb, yb)

        scaler.scale(loss).backward()
        if grad_clip is not None:
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)

        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad(set_to_none=True)

        # simple LR warmup/decay (optional)
        if cfg.get("lr_decay", False):
            warmup = cfg.get("warmup_iters", 200)
            if it < warmup:
                lr = cfg["learning_rate"] * it / warmup
            else:
                # cosine decay
                progress = (it - warmup) / max(1, (max_iters - warmup))
                lr = cfg.get("min_lr", 1e-5) + 0.5 * (cfg["learning_rate"] - cfg.get("min_lr", 1e-5)) * (1 + math.cos(math.pi * progress))
            for pg in optimizer.param_groups:
                pg["lr"] = lr

        if it % cfg.get("log_interval", 50) == 0:
            dt = time.time() - t0
            print(f"iter {it}/{max_iters} | loss {loss.item():.4f} | time {dt:.1f}s")
            t0 = time.time()

        if it % eval_interval == 0 or it == max_iters:
            losses = estimate_loss(model, train_data, val_data, eval_iters, batch_size, block_size, device)
            print(f"[eval] iter {it} train {losses['train']:.4f} val {losses['val']:.4f}")

            # save best checkpoint
            if losses["val"] < best_val:
                best_val = losses["val"]
                ckpt_path = out_dir / "ckpt_best.pt"
                torch.save(
                    {
                        "model_state": model.state_dict(),
                        "model_cfg": model_cfg.__dict__,
                        "iter": it,
                        "val_loss": best_val,
                    },
                    ckpt_path,
                )
                print(f"saved {ckpt_path} (val {best_val:.4f})")

            # also save latest
            ckpt_path = out_dir / "ckpt_last.pt"
            torch.save(
                {
                    "model_state": model.state_dict(),
                    "model_cfg": model_cfg.__dict__,
                    "iter": it,
                    "val_loss": losses["val"],
                },
                ckpt_path,
            )


if __name__ == "__main__":
    main()