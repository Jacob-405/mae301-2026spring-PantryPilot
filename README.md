# Recipe Generator (nanoGPT)

A constraint-aware recipe generator for college students (budget, time, and cooking tools).

## Repository Structure
- [Proposal](proposal/idea.md)
- [nanoGPT](nanogpt/)
- [MVP](mvp/)
- [Docs](docs/)

## Run PantryPilot Locally (Windows 11)

### What you need (one-time installs)
- **Python 3.12.x (64-bit)** (during install: check **“Add python.exe to PATH”**)
- **Git** (or GitHub Desktop)
- (Optional) **VS Code** for editing

---

## Quickstart (recommended): Run the MVP using a provided checkpoint
This is the fastest way to run the Streamlit UI without training.

### 1) Clone the repo
Using GitHub Desktop: **File → Clone Repository…**

Or PowerShell:
```powershell
git clone https://github.com/Jacob-405/mae301-2026spring-PantryPilot.git
cd mae301-2026spring-PantryPilot```

### 2) Create + activate a virtual environment
PowerShell command: py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

If PowerShell blocks activation
PowerShell command: Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1

### 3) Install dependencies
Upgrade pip
 PowerShell command: python -m pip install --upgrade pip

Install PyTorch, try cu 121 first
 PowerShell command: python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

If cu121 fails, try cu118
PowerShell command: python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

Install remaining packages
PowerShell command: python -m pip install numpy tqdm pyyaml tiktoken streamlit

### 4) Add the trained model checkpoint
You need a checkpoint file from teammembers (e.q., ckpt_best.pt)

Place it here:
nanogpt/outputs/ckpt_best.pt

### 5) Run the Streamlit MVP
PowerShell command: python -m streamlit run mvp/app.py

Open the Local URL Streamlit prints (usually http://localhost:8501)
