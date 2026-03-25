import argparse
import codecs
from pathlib import Path

import torch
import tiktoken

from model import GPT, GPTConfig


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt", default="nanogpt/outputs/ckpt_best.pt")
    parser.add_argument(
        "--prompt",
        default="<REQUEST>\nBudget: low\nTime: 25 minutes\nTools: skillet\nPreferences: vegetarian\n</REQUEST>\n<RECIPE>\nTitle: ",
    )
    parser.add_argument("--num_recipes", type=int, default=3)
    parser.add_argument("--max_new_tokens", type=int, default=420)
    parser.add_argument("--temperature", type=float, default=0.9)
    parser.add_argument("--top_k", type=int, default=50)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    ckpt_path = repo_root / args.ckpt

    device = "cuda" if torch.cuda.is_available() else "cpu"

    ckpt = torch.load(ckpt_path, map_location=device)
    model_cfg = GPTConfig(**ckpt["model_cfg"])
    model = GPT(model_cfg).to(device)
    model.load_state_dict(ckpt["model_state"])
    model.eval()

    enc = tiktoken.get_encoding("gpt2")
    prompt_ids = enc.encode(args.prompt)
    x = torch.tensor(prompt_ids, dtype=torch.long, device=device)[None, :]

    for i in range(args.num_recipes):
        y = model.generate(
            x.clone(),
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
            top_k=args.top_k,
        )
        text = enc.decode(y[0].tolist())

        # Try to extract one recipe block nicely
        start = text.find("<RECIPE>")
        end = text.find("</RECIPE>", start)
        if start != -1 and end != -1:
            text_out = text[start : end + len("</RECIPE>")]
        else:
            text_out = text

        # Decode sequences like \u00b0 into actual characters (°)
        try:
            text_out = codecs.decode(text_out, "unicode_escape")
        except Exception:
            pass

        print("\n" + "=" * 60)
        print(f"RECIPE OPTION {i+1}")
        print("=" * 60)
        print(text_out.strip())
        print("=" * 60)


if __name__ == "__main__":
    main()