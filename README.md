# GitHub Repository Explainer (Local Hybrid LLM Edition)

Paste any public GitHub repository URL and get back a plain-English overview:
- **Architecture Summary**: Grounded strictly in the repository's real files.
- **Interactive Mermaid.js Diagram**: Visualizes how the main modules and files connect.
- **Per-File Explanations**: Purpose, key functions/classes/exports, and dependencies for each selected file.
- **"Start Here" Onboarding Guide**: Recommended reading order, local setup steps, and where to make common changes.
- **SQLite History**: Instantaneous reload of previously analyzed repositories.

---

## Hardware-Optimized Hybrid Local LLM Setup (`Ollama`)

Instead of requiring a paid cloud `GOOGLE_API_KEY`, this project runs 100% locally using **Ollama** with a **Batched Complexity Router** tailored for a **4 GB VRAM GPU + 32 GB System RAM** machine:

1. **Fast GPU Model (`OLLAMA_FAST_MODEL=gemma3:4b`)**:
   - Fits inside 4 GB GPU VRAM.
   - Used for Step 1 (selecting key files from the repo tree) and Step 2a (summarizing standard/config/doc files at high speed).
2. **Smart Hybrid Model (`OLLAMA_SMART_MODEL=gemma3:12b`)**:
   - Uses GPU VRAM + 32 GB System RAM.
   - Used for Step 2b (summarizing dense core source files) and Step 3 (reducing all per-file summaries into the final Architecture Overview, Mermaid.js diagram, and Onboarding Guide).

---

## Quick Start

### 1. Install Prerequisites
1. **Ollama**: Download from [ollama.com/download](https://ollama.com/download) and pull the models:
   ```powershell
   ollama pull gemma3:4b
   ollama pull gemma3:12b
   ```
2. **Python 3.10+**: Download from [python.org/downloads](https://www.python.org/downloads/) (check *"Add python.exe to PATH"*).
3. **Node.js 18+**: Download from [nodejs.org](https://nodejs.org/).

### 2. Run Stage 1 from the Command Line (CLI Pipeline)
```powershell
cd Backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Analyze any public GitHub repo directly in the terminal:
python analyzer.py https://github.com/pallets/click --max-files 6
```

### 3. Run the Full-Stack App (Stage 2 Backend + Stage 3 Frontend)
Simply double-click **`start-local.bat`** in the project root, or run both halves manually:

**Terminal 1 — FastAPI + SQLite Backend (`http://localhost:8000`)**:
```powershell
cd Backend
venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — React + Tailwind Frontend (`http://localhost:5173`)**:
```powershell
cd Frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser!

