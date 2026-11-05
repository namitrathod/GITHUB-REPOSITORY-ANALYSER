"""
Stage 1: High-Speed, Grounded Repository Analysis Pipeline (Local LLM via Ollama)

Speed & Accuracy Optimizations for 4GB VRAM GPU (Quadro T2000):
1. 100% GPU VRAM Residency: Defaults to `gemma3:4b` (or `qwen2.5-coder:3b`) with `num_ctx=4096` and
   `keep_alive='30m'` so the model + KV cache fit inside 4GB VRAM without spilling onto slow CPU RAM
   and without unloading/reloading models between steps.
2. Parallel GitHub File Fetching: Uses `ThreadPoolExecutor` to download all selected files simultaneously.
3. Single-Pass Grammar-Enforced JSON: Uses Ollama's native `format=schema.model_json_schema()` so the
   model outputs valid JSON on the first call (no double-call retry penalty).
4. Unified Reduce Step: Combines Architecture Overview, Mermaid.js Diagram, and Onboarding Guide into a
   single Reduce LLM call, cutting Reduce latency by 50% while keeping all outputs grounded in the
   per-file summaries.
"""

import argparse
import base64
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_FAST_MODEL = os.getenv("OLLAMA_FAST_MODEL", os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b"))
OLLAMA_SMART_MODEL = os.getenv("OLLAMA_SMART_MODEL", os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b"))
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()


# ---------------------------------------------------------------------------
# Pydantic Schemas for Structured LLM Outputs
# ---------------------------------------------------------------------------

class SelectedFilesOutput(BaseModel):
    selected_files: List[str] = Field(
        description="List of file paths from the provided candidate list that are most important for understanding the repository's architecture."
    )
    reasoning: str = Field(
        description="1-2 sentence explanation of why these files were chosen."
    )


class FileSummaryOutput(BaseModel):
    path: str = Field(description="The file path being summarized.")
    purpose: str = Field(
        description="1-2 sentence high-level summary of this file's role in the project."
    )
    key_components: List[str] = Field(
        description="Key functions, classes, routes, or exports defined in this file."
    )
    dependencies_and_connections: List[str] = Field(
        description="Internal modules or external libraries this file interacts with."
    )


class BatchFileSummariesOutput(BaseModel):
    summaries: List[FileSummaryOutput] = Field(
        description="List of file summaries, one for each file provided in the batch."
    )


class OnboardingGuideOutput(BaseModel):
    project_overview: str = Field(
        description="Brief welcome and summary of what the project does for a new contributor."
    )
    reading_order: List[str] = Field(
        description="Ordered list of files a new developer should read first, with a 1-sentence explanation for each."
    )
    setup_and_run_steps: List[str] = Field(
        description="Concrete steps to set up and run the project locally, inferred strictly from config/README files."
    )
    where_to_make_changes: List[str] = Field(
        description="Practical pointers on which files to edit for common tasks (e.g., adding a route, updating UI, changing config)."
    )


class FullReduceSynthesisOutput(BaseModel):
    architecture_summary: str = Field(
        description="Plain-English overview (2-3 paragraphs) of how the repository works, its tech stack, and how components interact, strictly grounded in the file summaries."
    )
    mermaid_diagram: str = Field(
        description="Valid Mermaid.js flowchart (starting with 'flowchart TD') showing how the main files and modules connect."
    )
    onboarding_guide: OnboardingGuideOutput = Field(
        description="Practical 'Start Here' onboarding guide for a new contributor."
    )


# ---------------------------------------------------------------------------
# Step 0: GitHub API Helpers & Heuristic Filtering
# ---------------------------------------------------------------------------

IGNORED_DIRS = {
    ".git", ".github", ".vscode", ".idea", "node_modules", "bower_components",
    "venv", ".venv", "env", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".next", ".nuxt", "dist", "build", "out", "target", "vendor", "coverage",
    ".gradle", "migrations", "assets", "public/assets", "static/images",
}

IGNORED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp",
    ".mp4", ".mp3", ".wav", ".ogg", ".webm",
    ".pdf", ".zip", ".tar", ".gz", ".rar", ".7z",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".a",
    ".pyc", ".pyo", ".pyd", ".class", ".jar", ".war",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".lock", ".min.js", ".min.css", ".map",
    ".db", ".sqlite", ".sqlite3", ".parquet", ".csv",
}

IGNORED_FILENAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Pipfile.lock", "Cargo.lock", "composer.lock", "Gemfile.lock",
    ".DS_Store", "Thumbs.db", ".gitignore", ".gitattributes", ".editorconfig",
    ".prettierrc", ".eslintrc", "LICENSE", "LICENSE.md", "LICENSE.txt",
    "CHANGELOG.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md",
}

PRIORITY_FILENAMES = {
    "readme.md", "package.json", "requirements.txt", "pyproject.toml",
    "cargo.toml", "go.mod", "pom.xml", "dockerfile", "docker-compose.yml",
    "docker-compose.yaml", "makefile", "main.py", "app.py", "server.py",
    "index.ts", "index.js", "main.ts", "main.go", "main.rs", "app.tsx", "app.jsx",
    "openapi.yaml", "openapi.json",
}


def get_github_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def parse_github_url(repo_url: str) -> Tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL."""
    cleaned = repo_url.strip().rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    parsed = urlparse(cleaned)
    if parsed.netloc not in ("github.com", "www.github.com"):
        raise ValueError(f"Invalid GitHub URL '{repo_url}'. Must be a github.com URL.")
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise ValueError(
            f"Could not extract owner and repository name from '{repo_url}'."
        )
    return parts[0], parts[1]


def fetch_repo_tree(owner: str, repo: str) -> Tuple[str, List[Dict]]:
    """Fetch default branch and full recursive git tree from GitHub API."""
    headers = get_github_headers()
    repo_api = f"https://api.github.com/repos/{owner}/{repo}"
    resp = requests.get(repo_api, headers=headers, timeout=15)
    if resp.status_code == 404:
        raise ValueError(f"Repository '{owner}/{repo}' not found or is private.")
    resp.raise_for_status()
    default_branch = resp.json().get("default_branch", "main")

    tree_api = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
    tree_resp = requests.get(tree_api, headers=headers, timeout=15)
    tree_resp.raise_for_status()
    tree_data = tree_resp.json().get("tree", [])
    return default_branch, tree_data


SOURCE_CODE_EXTENSIONS = {
    ".py", ".go", ".ts", ".tsx", ".js", ".jsx", ".rs", ".java", ".cpp", ".c",
    ".cs", ".rb", ".php", ".swift", ".kt", ".scala", ".sql", ".sh", ".ipynb",
}

CORE_CODE_DIRS = {
    "src", "app", "lib", "pkg", "internal", "cmd", "api", "core", "services",
    "controllers", "routes", "models", "components", "pages", "scripts",
    "codes", "notebooks", "utils", "engine", "pipeline", "server", "client",
}


def heuristic_filter_files(tree: List[Dict], max_candidates: int = 200) -> List[str]:
    """
    Filter out only true binary/junk files and return ALL meaningful repository files
    sorted in decreasing order of architectural importance:
    1. Main entrypoints (app.py, main.py, server.py, index.ts, cmd/*/main.go)
    2. Core subfolder source code (src/*, internal/*, scripts/*, codes/*, lib/*, app/*)
    3. Notebooks & SQL/schema files (notebooks/*, *.ipynb, *.sql)
    4. Primary configuration & README (README.md, requirements.txt, package.json, go.mod, Dockerfile)
    5. Secondary documentation, data samples & test files
    """
    candidates = []

    for item in tree:
        if item.get("type") != "blob":
            continue
        path: str = item.get("path", "")
        size: int = item.get("size", 0)

        # Allow up to 1.5MB so Jupyter notebooks (.ipynb) inside notebooks/ are included
        if size == 0 or size > 1_500_000:
            continue

        parts = path.split("/")
        filename = parts[-1]
        lower_filename = filename.lower()
        _, ext = os.path.splitext(lower_filename)

        # Skip tiny empty __init__.py files
        if lower_filename == "__init__.py" and size < 60:
            continue

        if any(part in IGNORED_DIRS or part.lower() in {"screenshots", "images", "img"} for part in parts[:-1]):
            continue
        if filename in IGNORED_FILENAMES or lower_filename in {f.lower() for f in IGNORED_FILENAMES}:
            continue
        if any(lower_filename.endswith(ignored_ext) for ignored_ext in IGNORED_EXTENSIONS):
            continue

        is_test = 1 if ("test" in lower_filename or "spec" in lower_filename or "tests" in parts) else 0
        is_entrypoint = lower_filename in {
            "app.py", "main.py", "server.py", "index.ts", "index.js", "main.go", "main.rs", "app.tsx", "app.jsx"
        }
        is_source_code = ext in SOURCE_CODE_EXTENSIONS and ext != ".ipynb"
        is_notebook = ext == ".ipynb"
        in_core_subfolder = len(parts) > 1 and parts[0].lower() in CORE_CODE_DIRS
        is_main_readme = lower_filename == "readme.md" and len(parts) == 1
        is_main_config = lower_filename in {
            "package.json", "requirements.txt", "go.mod", "pyproject.toml", "cargo.toml", "dockerfile", "openapi.yaml", "openapi.json"
        }

        # Importance ranking (lower score = higher importance)
        if is_entrypoint:
            tier_score = 1
        elif is_source_code and in_core_subfolder:
            tier_score = 2
        elif is_source_code:
            tier_score = 3
        elif is_notebook:
            tier_score = 4
        elif is_main_readme or is_main_config:
            tier_score = 5
        elif not is_test:
            tier_score = 10
        else:
            tier_score = 20

        candidates.append((tier_score, len(parts), path))

    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
    return [path for _, _, path in candidates[:max_candidates]]


def extract_ipynb_code_and_markdown(raw_ipynb: str, max_chars: int = 3500) -> str:
    """Extract clean markdown and code cells from a Jupyter Notebook (.ipynb) JSON file, stripping base64 outputs."""
    try:
        nb = json.loads(raw_ipynb)
        cells = nb.get("cells", [])
        extracted = []
        for idx, cell in enumerate(cells[:25]):
            cell_type = cell.get("cell_type", "")
            source = cell.get("source", [])
            text = "".join(source) if isinstance(source, list) else str(source)
            text = text.strip()
            if not text:
                continue
            if cell_type == "markdown":
                extracted.append(f"# [Markdown Cell {idx + 1}]\n{text[:400]}")
            elif cell_type == "code":
                extracted.append(f"# [Code Cell {idx + 1}]\n{text[:800]}")
        joined = "\n\n".join(extracted)
        return joined[:max_chars] if joined else raw_ipynb[:max_chars]
    except Exception:
        return raw_ipynb[:max_chars]


def fetch_file_content(owner: str, repo: str, path: str, branch: str = "main", max_chars: int = 3500) -> str:
    """
    Fetch raw file content from GitHub API and trim to `max_chars`
    so batched files fit comfortably inside the GPU VRAM context window.
    """
    headers = get_github_headers()
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if isinstance(data, dict) and data.get("encoding") == "base64":
        raw_bytes = base64.b64decode(data.get("content", ""))
        content = raw_bytes.decode("utf-8", errors="replace")
    else:
        download_url = data.get("download_url")
        if download_url:
            raw_resp = requests.get(download_url, timeout=15)
            raw_resp.raise_for_status()
            content = raw_resp.text
        else:
            content = ""

    if path.lower().endswith(".ipynb"):
        return extract_ipynb_code_and_markdown(content, max_chars=max_chars)

    content = re.sub(r"\n{3,}", "\n\n", content)
    if len(content) > max_chars:
        content = content[:max_chars] + "\n... [TRUNCATED]"
    return content


def fetch_all_files_parallel(
    owner: str, repo: str, file_paths: List[str], branch: str
) -> Dict[str, str]:
    """Download all selected files from GitHub concurrently using a thread pool."""
    contents: Dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        future_to_path = {
            executor.submit(fetch_file_content, owner, repo, path, branch): path
            for path in file_paths
        }
        for future in as_completed(future_to_path):
            path = future_to_path[future]
            try:
                contents[path] = future.result()
            except Exception as exc:
                contents[path] = f"# Error fetching file: {exc}"
    return contents


# ---------------------------------------------------------------------------
# Fast Single-Pass Structured Local LLM Helper (100% GPU VRAM Optimized)
# ---------------------------------------------------------------------------

def repair_truncated_json(raw: str) -> dict:
    """
    Attempt to parse JSON, and if truncated mid-string/array/object,
    automatically close open quotes, brackets, and braces so json.loads succeeds.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Trim trailing incomplete escape or comma
    s = raw.rstrip()
    while s and s[-1] in (",", ":", "\\"):
        s = s[:-1].rstrip()

    # Count unescaped quotes
    in_string = False
    escaped = False
    stack = []
    for ch in s:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if not in_string:
            if ch in ("{", "["):
                stack.append("}" if ch == "{" else "]")
            elif ch in ("}", "]") and stack and stack[-1] == ch:
                stack.pop()

    if in_string:
        s += '"'
    # Clean any dangling colon or comma before closing brackets
    s = re.sub(r"[,:\s]+$", "", s)
    while stack:
        closer = stack.pop()
        # If we are closing a dict and the last token was just a key string, append `: null`
        if closer == "}" and re.search(r'"[^"]*"\s*$', s) and not re.search(r':\s*"[^"]*"\s*$', s):
            s += ": null"
        s += closer

    return json.loads(s)


def extract_json_from_text(text: str) -> dict:
    """Parse JSON from model output, stripping any <think> tags or markdown code fences, with auto-repair."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    else:
        brace_match = re.search(r"(\{.*)", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(1)
    return repair_truncated_json(text)


def invoke_structured_fast(
    tier: str,
    schema_cls,
    prompt_messages: list,
    num_ctx: int = 4096,
    num_predict: int = 1024,
) -> BaseModel:
    """
    Single-pass structured output invocation using Ollama's native grammar-locked `format` parameter.
    - Sets `num_ctx=4096` so the KV cache stays small enough to remain 100% inside 4GB GPU VRAM.
    - Sets `keep_alive='30m'` so Ollama keeps the model warm in VRAM across calls.
    """
    model_name = OLLAMA_SMART_MODEL if tier == "smart" else OLLAMA_FAST_MODEL
    llm = ChatOllama(
        model=model_name,
        base_url=OLLAMA_BASE_URL,
        temperature=0.0,
        num_ctx=num_ctx,
        num_predict=num_predict,
        keep_alive="30m",
        format=schema_cls.model_json_schema(),
    )
    raw_resp = llm.invoke(prompt_messages)
    parsed_dict = extract_json_from_text(raw_resp.content)
    return schema_cls.model_validate(parsed_dict)


# ---------------------------------------------------------------------------
# Step 1: Select Key Files (Fast GPU Call)
# ---------------------------------------------------------------------------

def enforce_subfolder_and_code_diversity(
    selected: List[str],
    candidate_files: List[str],
    max_files: int,
) -> List[str]:
    """
    Ensure the selected files aren't all root-level `.md` or `.txt` files when actual
    source code files exist inside subdirectories (`src/`, `scripts/`, `codes/`, `internal/`, etc.).
    - Caps `.md` files to at most 1 (preferring `README.md`)
    - Caps dependency/config `.txt`/`.json`/`.toml` files to at most 1
    - Fills remaining slots with the top-ranked source code files from subdirectories
    """
    valid_set = set(candidate_files)
    cleaned = [f for f in selected if f in valid_set]

    # Check if repository has source code files or subdirectory files in candidates
    subfolder_code = [
        c for c in candidate_files
        if ("/" in c and os.path.splitext(c.lower())[1] in SOURCE_CODE_EXTENSIONS)
    ]
    any_code = [
        c for c in candidate_files
        if os.path.splitext(c.lower())[1] in SOURCE_CODE_EXTENSIONS
    ]

    if not any_code:
        return (cleaned or candidate_files)[:max_files]

    final_list: List[str] = []
    md_count = 0
    config_count = 0

    for path in cleaned:
        lower = path.lower()
        _, ext = os.path.splitext(lower)
        is_md = ext in {".md", ".rst"}
        is_cfg = ext in {".txt", ".toml", ".ini", ".cfg", ".lock"} or lower.endswith("package.json")

        if is_md:
            if md_count >= 1:
                continue
            md_count += 1
        elif is_cfg:
            if config_count >= 1:
                continue
            config_count += 1

        if path not in final_list:
            final_list.append(path)

    # Fill remaining slots first from subfolder source code (`src/`, `scripts/`, `codes/`, etc.), then any candidate
    for pool in (subfolder_code, any_code, candidate_files):
        for cand in pool:
            if len(final_list) >= max_files:
                break
            if cand not in final_list:
                lower = cand.lower()
                _, ext = os.path.splitext(lower)
                if ext in {".md", ".rst"} and md_count >= 1:
                    continue
                if ext in {".txt"} and config_count >= 1:
                    continue
                final_list.append(cand)

    return final_list[:max_files]


def select_important_files(
    owner: str,
    repo: str,
    candidate_files: List[str],
    max_files: int = 6,
) -> SelectedFilesOutput:
    """Select the most architecturally significant files, ensuring subfolder source modules are included."""
    if len(candidate_files) <= max_files:
        return SelectedFilesOutput(
            selected_files=candidate_files,
            reasoning="Repository has fewer candidate files than max_files; selected all candidates.",
        )

    candidate_list_str = "\n".join(f"- {p}" for p in candidate_files)
    messages = [
        (
            "system",
            "You are a senior software architect analyzing a GitHub repository. "
            f"Select the {max_files} most important files from the list below that explain "
            "the project's core implementation across its subdirectories (such as `src/`, `scripts/`, `codes/`, `internal/`, `cmd/`, `app/`).\n"
            "STRICT RULES:\n"
            "1. Select at most ONE `.md` documentation file (prefer `README.md`).\n"
            "2. Select at most ONE dependency file (such as `requirements.txt`, `package.json`, or `go.mod`).\n"
            "3. All other selected files MUST be actual source code files, especially those inside subdirectories (`src/...`, `scripts/...`, `internal/...`, etc.).\n"
            "4. ONLY select exact file paths from the provided list.",
        ),
        (
            "user",
            f"Repository: {owner}/{repo}\n"
            f"Select {max_files} files (prioritize subfolder source code + main entrypoint):\n{candidate_list_str}",
        ),
    ]

    result: SelectedFilesOutput = invoke_structured_fast(
        tier="fast",
        schema_cls=SelectedFilesOutput,
        prompt_messages=messages,
        num_ctx=2048,
        num_predict=400,
    )
    result.selected_files = enforce_subfolder_and_code_diversity(
        result.selected_files, candidate_files, max_files
    )
    return result


# ---------------------------------------------------------------------------
# Step 2: Map Step — Summarize Each Selected File Grounded in Real Content
# ---------------------------------------------------------------------------

def summarize_single_file(path: str, content: str) -> FileSummaryOutput:
    """Summarize a single file strictly grounded in its actual source code."""
    messages = [
        (
            "system",
            "You are an expert code reviewer summarizing a source file from a GitHub repository. "
            "Your summary MUST be strictly grounded in the provided file content. "
            "NEVER invent functions, classes, or behavior not present in the file. "
            "Keep component and dependency names short (just the identifier names, not full code lines).",
        ),
        (
            "user",
            f"File Path: {path}\n\n"
            f"File Content:\n```\n{content}\n```\n\n"
            "Return JSON with `path`, `purpose` (1-2 sentences), `key_components` (up to 5 short function/class names), "
            "and `dependencies_and_connections` (up to 5 imported package/module names).",
        ),
    ]
    try:
        result: FileSummaryOutput = invoke_structured_fast(
            tier="fast",
            schema_cls=FileSummaryOutput,
            prompt_messages=messages,
            num_ctx=4096,
            num_predict=1024,
        )
        result.path = path
        return result
    except Exception as exc:
        print(f"[WARN] Fallback summary for {path}: {exc}")
        return FileSummaryOutput(
            path=path,
            purpose=f"Core repository file ({path}) containing application implementation and configuration.",
            key_components=[path.split("/")[-1]],
            dependencies_and_connections=[],
        )


# ---------------------------------------------------------------------------
# Step 3: Unified Reduce Step — Architecture, Mermaid & Onboarding in 1 Call
# ---------------------------------------------------------------------------

def build_grounded_mermaid(owner: str, repo: str, file_summaries: List[FileSummaryOutput]) -> str:
    """
    Build a guaranteed-valid Mermaid flowchart directly from the verified per-file summaries
    and their dependencies/connections. Used when the LLM's raw Mermaid string is truncated or invalid.
    """
    lines = ["flowchart TD"]
    if not file_summaries:
        lines.append(f'  R["{owner}/{repo}"]')
        return "\n".join(lines)

    def clean(val: str) -> str:
        return re.sub(r'["\[\]\(\)\{\}<>]', "", str(val or "")).strip()

    for i, fs in enumerate(file_summaries):
        path_label = clean(fs.path)
        comps = ", ".join(clean(c) for c in (fs.key_components or [])[:2] if clean(c))
        label = f"{path_label}\\n({comps})" if comps else path_label
        lines.append(f'  F{i}["{label}"]')

    edge_count = 0
    ext_nodes: Dict[str, str] = {}
    for i, fs in enumerate(file_summaries):
        for dep in (fs.dependencies_and_connections or [])[:4]:
            dep_clean = clean(dep)
            if not dep_clean:
                continue
            matched_target = None
            for j, other in enumerate(file_summaries):
                if i == j:
                    continue
                other_stem = other.path.split("/")[-1].split(".")[0].lower()
                if dep_clean.lower() in other.path.lower() or (
                    len(other_stem) > 2 and other_stem in dep_clean.lower()
                ):
                    matched_target = j
                    break
            if matched_target is not None:
                lines.append(f"  F{i} --> F{matched_target}")
                edge_count += 1
            elif len(ext_nodes) < 6:
                ext_id = ext_nodes.get(dep_clean)
                if not ext_id:
                    ext_id = f"EXT{len(ext_nodes) + 1}"
                    ext_nodes[dep_clean] = ext_id
                    lines.append(f'  {ext_id}(["{dep_clean}"])')
                lines.append(f"  F{i} -.-> {ext_id}")
                edge_count += 1

    if edge_count == 0 and len(file_summaries) > 1:
        for i in range(len(file_summaries) - 1):
            lines.append(f"  F{i} --> F{i + 1}")

    return "\n".join(lines)


def sanitize_mermaid(diagram: str, owner: str = "", repo: str = "", file_summaries: List[FileSummaryOutput] = None) -> str:
    """Strip markdown fences, quote unquoted brackets, or fall back to grounded diagram builder if truncated."""
    cleaned = (diagram or "").strip()
    cleaned = re.sub(r"^```(?:mermaid)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()

    # If the model truncated the diagram or failed to output arrows, build a clean grounded Mermaid diagram
    if len(cleaned) < 25 or ("-->" not in cleaned and "-.->" not in cleaned and "---" not in cleaned):
        if file_summaries is not None:
            return build_grounded_mermaid(owner, repo, file_summaries)

    if not cleaned.startswith(("flowchart", "graph", "sequenceDiagram", "classDiagram")):
        cleaned = "flowchart TD\n" + cleaned

    # Quote any unquoted node labels A[some/path.py] -> A["some/path.py"]
    cleaned = re.sub(
        r'([A-Za-z0-9_]+)\[([^"\]\n]+)\]',
        lambda m: f'{m.group(1)}["{m.group(2).strip()}"]',
        cleaned,
    )
    return cleaned.strip()


def reduce_all_in_one(
    owner: str,
    repo: str,
    file_summaries: List[FileSummaryOutput],
) -> FullReduceSynthesisOutput:
    """
    Single unified Reduce call: synthesizes all per-file summaries into:
    1. Plain-English Architecture Summary
    2. Mermaid.js Architecture Diagram
    3. 'Start Here' Contributor Onboarding Guide
    """
    summaries_block = "\n\n".join(
        f"### {s.path}\n"
        f"- Purpose: {s.purpose}\n"
        f"- Key Components: {', '.join(s.key_components[:6])}\n"
        f"- Connections: {', '.join(s.dependencies_and_connections[:6])}"
        for s in file_summaries
    )

    messages = [
        (
            "system",
            "You are a staff software architect creating a repository explanation based ONLY on the verified "
            "per-file summaries below. Every claim and diagram node must trace back to the analyzed files.\n"
            "Rules for `mermaid_diagram`:\n"
            "- Start with `flowchart TD`\n"
            "- Quote all node labels containing slashes, dots, or spaces, e.g. `A[\"cmd/mcp/main.go\"] --> B[\"internal/api/server.go\"]`\n"
            "- Output raw Mermaid syntax without markdown code fences.",
        ),
        (
            "user",
            f"Repository: {owner}/{repo}\n\n"
            f"Verified Per-File Summaries:\n{summaries_block}\n\n"
            "Generate the complete architecture summary, Mermaid.js flowchart, and contributor onboarding guide.",
        ),
    ]

    result: FullReduceSynthesisOutput = invoke_structured_fast(
        tier="smart",
        schema_cls=FullReduceSynthesisOutput,
        prompt_messages=messages,
        num_ctx=4096,
        num_predict=2048,
    )
    result.mermaid_diagram = sanitize_mermaid(result.mermaid_diagram, owner, repo, file_summaries)
    return result


def summarize_files_batch(batch: List[Tuple[str, str]]) -> List[FileSummaryOutput]:
    """
    Summarize a batch of 1 to 3 files in a single GPU LLM call to dramatically speed up
    full-repository analysis while keeping every summary strictly grounded in real file content.
    Falls back to single-file summarization if batch parsing fails.
    """
    if len(batch) == 1:
        return [summarize_single_file(batch[0][0], batch[0][1])]

    files_block = "\n\n".join(
        f"=== FILE {i + 1}: {path} ===\n```\n{content[:2200]}\n```"
        for i, (path, content) in enumerate(batch)
    )
    expected_paths = [p for p, _ in batch]

    messages = [
        (
            "system",
            "You are an expert code reviewer summarizing multiple files from a GitHub repository. "
            "For EACH file provided below, return a summary in `summaries` with its exact `path`, "
            "`purpose` (1-2 sentences grounded strictly in its content), `key_components` (up to 5 short function/class/section names), "
            "and `dependencies_and_connections` (up to 5 imported packages or connected modules).",
        ),
        (
            "user",
            f"Summarize each of these {len(batch)} files in order ({', '.join(expected_paths)}):\n\n{files_block}",
        ),
    ]

    try:
        result: BatchFileSummariesOutput = invoke_structured_fast(
            tier="fast",
            schema_cls=BatchFileSummariesOutput,
            prompt_messages=messages,
            num_ctx=4096,
            num_predict=1200,
        )
        by_path = {s.path: s for s in result.summaries}
        output: List[FileSummaryOutput] = []
        for idx, (path, content) in enumerate(batch):
            if path in by_path:
                output.append(by_path[path])
            elif idx < len(result.summaries):
                item = result.summaries[idx]
                item.path = path
                output.append(item)
            else:
                output.append(summarize_single_file(path, content))
        return output
    except Exception:
        return [summarize_single_file(path, content) for path, content in batch]


# ---------------------------------------------------------------------------
# Full Pipeline Orchestrator (All Files in Decreasing Order of Importance)
# ---------------------------------------------------------------------------

def analyze_repository(repo_url: str, max_files: int = 0) -> Dict:
    """
    Run the repository analysis pipeline across ALL repository files (or up to `max_files` if > 0),
    ordered in decreasing architectural importance (entrypoints -> core subfolder code -> notebooks -> configs/docs).
    Uses batched GPU summarization (3 files per call) so analyzing 25-40 files finishes quickly!
    """
    t0 = time.time()
    owner, repo = parse_github_url(repo_url)
    print(f"[1/3] Fetching file tree for {owner}/{repo}...")
    branch, tree = fetch_repo_tree(owner, repo)
    ranked_files = heuristic_filter_files(tree, max_candidates=200)

    if max_files and max_files > 0 and len(ranked_files) > max_files:
        files_to_analyze = ranked_files[:max_files]
    else:
        files_to_analyze = ranked_files

    print(
        f"      Total items in tree: {len(tree)} | Analyzing {len(files_to_analyze)} files "
        f"(ranked in decreasing order of importance)"
    )

    print(f"[2/3] Downloading {len(files_to_analyze)} files in parallel & summarizing on GPU ({OLLAMA_FAST_MODEL})...")
    file_contents = fetch_all_files_parallel(owner, repo, files_to_analyze, branch)

    # Group files into batches of 3 for fast GPU execution
    batch_size = 3
    batches: List[List[Tuple[str, str]]] = []
    for i in range(0, len(files_to_analyze), batch_size):
        chunk_paths = files_to_analyze[i : i + batch_size]
        batches.append([(p, file_contents.get(p, "")) for p in chunk_paths])

    file_summaries: List[FileSummaryOutput] = []
    for b_idx, batch in enumerate(batches, start=1):
        step_t = time.time()
        batch_names = ", ".join(p for p, _ in batch)
        print(f"      [Batch {b_idx}/{len(batches)}] Summarizing ({batch_names})...", end=" ", flush=True)
        batch_results = summarize_files_batch(batch)
        file_summaries.extend(batch_results)
        print(f"({time.time() - step_t:.1f}s)")

    print(f"[3/3] Synthesizing Architecture, Mermaid & Onboarding in 1 unified Reduce call ({OLLAMA_SMART_MODEL})...")
    red_t = time.time()
    # Pass top 20 most important file summaries to the Reduce prompt so it stays within 4096 context
    reduced = reduce_all_in_one(owner, repo, file_summaries[:20])
    # Rebuild/sanitize Mermaid diagram using top 15 files so the diagram covers all folders cleanly
    reduced.mermaid_diagram = sanitize_mermaid(
        reduced.mermaid_diagram, owner, repo, file_summaries[:15]
    )
    print(f"      Reduce completed in {time.time() - red_t:.1f}s! Total time: {time.time() - t0:.1f}s")

    model_label = (
        OLLAMA_FAST_MODEL
        if OLLAMA_FAST_MODEL == OLLAMA_SMART_MODEL
        else f"Hybrid ({OLLAMA_FAST_MODEL} + {OLLAMA_SMART_MODEL})"
    )

    return {
        "repo_url": repo_url,
        "owner": owner,
        "repo": repo,
        "default_branch": branch,
        "model": model_label,
        "selected_files_reasoning": (
            f"Analyzed all {len(file_summaries)} repository files ranked in decreasing order of architectural importance "
            "(Entrypoints -> Core Subdirectory Modules -> Notebooks/Scripts -> Configs & Docs)."
        ),
        "architecture_summary": reduced.architecture_summary,
        "mermaid_diagram": reduced.mermaid_diagram,
        "file_summaries": [s.model_dump() for s in file_summaries],
        "onboarding_guide": reduced.onboarding_guide.model_dump(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="GitHub Repository Explainer CLI (High-Speed Local Ollama Pipeline)"
    )
    parser.add_argument(
        "repo_url",
        help="Public GitHub repository URL (e.g., https://github.com/namitrathod/Mini-Control-Plane)",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=6,
        help="Maximum number of key files to summarize in the Map step (default: 6)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Optional file path to save the JSON output",
    )
    args = parser.parse_args()

    try:
        result = analyze_repository(args.repo_url, max_files=args.max_files)
        print("\n" + "=" * 70)
        print(f"REPOSITORY: {result['owner']}/{result['repo']} ({result['model']})")
        print("=" * 70)
        print("\n## Architecture Summary\n")
        print(result["architecture_summary"])
        print("\n## Mermaid Diagram\n")
        print("```mermaid")
        print(result["mermaid_diagram"])
        print("```")
        print("\n## Per-File Explanations\n")
        for fs in result["file_summaries"]:
            print(f"### {fs['path']}")
            print(f"Purpose: {fs['purpose']}")
            print(f"Key Components: {', '.join(fs['key_components'])}")
            print()
        print("## Start Here: Onboarding Guide\n")
        og = result["onboarding_guide"]
        print(og["project_overview"])
        print("\nRecommended Reading Order:")
        for step in og["reading_order"]:
            print(f"  - {step}")

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            print(f"\nSaved full JSON analysis to {args.output}")
    except Exception as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
