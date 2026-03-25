from pathlib import Path
import torch
import tiktoken

from .model import GPT, GPTConfig


def load_model(ckpt_path: str):
    repo_root = Path(__file__).resolve().parents[2]
    ckpt_full = repo_root / ckpt_path

    device = "cuda" if torch.cuda.is_available() else "cpu"
    ckpt = torch.load(ckpt_full, map_location=device)

    cfg = GPTConfig(**ckpt["model_cfg"])
    model = GPT(cfg).to(device)
    model.load_state_dict(ckpt["model_state"])
    model.eval()

    enc = tiktoken.get_encoding("gpt2")
    return model, enc, device


@torch.no_grad()
def generate_recipes(
    model,
    enc,
    device,
    budget: str,
    time_minutes: int,
    tools: str,
    preferences: str,
    n: int = 3,
    max_new_tokens: int = 420,
    temperature: float = 0.7,
    top_k: int = 40,
):
    prompt = (
        "<REQUEST>\n"
        f"Budget: {budget}\n"
        f"Time: {time_minutes} minutes\n"
        f"Tools: {tools}\n"
        f"Preferences: {preferences}\n"
        "</REQUEST>\n"
        "<RECIPE>\n"
        "Title: "
    )

    x = torch.tensor(enc.encode(prompt), dtype=torch.long, device=device)[None, :]
    outputs = []
    for _ in range(n):
        y = model.generate(x.clone(), max_new_tokens=max_new_tokens, temperature=temperature, top_k=top_k)
        text = enc.decode(y[0].tolist())

        # extract one recipe
        start = text.find("<RECIPE>")
        end = text.find("</RECIPE>", start)
        if start != -1 and end != -1:
            recipe = text[start : end + len("</RECIPE>")]
        else:
            recipe = text

        outputs.append(recipe)
    return outputs