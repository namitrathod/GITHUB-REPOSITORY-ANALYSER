"""
Stage 2: FastAPI + SQLite Backend for GitHub Repository Explainer
Exposes endpoints to run the Hybrid Local Ollama Map-Reduce pipeline and store/retrieve analyses.
"""

import json
from typing import List, Optional

import requests
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from analyzer import (
    OLLAMA_BASE_URL,
    OLLAMA_FAST_MODEL,
    OLLAMA_SMART_MODEL,
    analyze_repository,
)
from database import AnalysisRecord, get_db, init_db

init_db()

app = FastAPI(
    title="GitHub Repository Explainer API (Local Hybrid Ollama)",
    description="Map-Reduce repository analyzer powered by local Ollama models (gemma3:4b + gemma3:12b) and SQLite.",
    version="1.0.0",
)

# Allow local Vite development server & deployed frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    repo_url: str = Field(
        ...,
        description="Public GitHub repository URL, e.g. https://github.com/pallets/click",
    )
    max_files: int = Field(
        default=0,
        ge=0,
        le=200,
        description="0 means analyze ALL files in decreasing order of importance (or set a limit up to 200).",
    )
    force_reanalyze: bool = Field(
        default=False,
        description="If False and this repo_url was already analyzed, return the cached analysis unless forced.",
    )


def check_ollama_status() -> dict:
    """Ping local Ollama server and return installed models."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=3)
        if resp.status_code == 200:
            models = [m.get("name", "") for m in resp.json().get("models", [])]
            return {
                "ollama_online": True,
                "ollama_url": OLLAMA_BASE_URL,
                "installed_models": models,
                "fast_model": OLLAMA_FAST_MODEL,
                "smart_model": OLLAMA_SMART_MODEL,
            }
    except Exception:
        pass
    return {
        "ollama_online": False,
        "ollama_url": OLLAMA_BASE_URL,
        "installed_models": [],
        "fast_model": OLLAMA_FAST_MODEL,
        "smart_model": OLLAMA_SMART_MODEL,
    }


@app.get("/")
@app.get("/health")
@app.get("/api/health")
def health_check():
    """Return API status and local Ollama readiness."""
    ollama_info = check_ollama_status()
    return {
        "status": "ok",
        **ollama_info,
    }


@app.post("/analyze")
@app.post("/api/analyze")
def run_analysis(payload: AnalyzeRequest, db: Session = Depends(get_db)):
    """
    Analyze a public GitHub repository using the Hybrid Local Ollama Map-Reduce pipeline
    and store the resulting overview, Mermaid diagram, file summaries, and onboarding guide in SQLite.
    """
    cleaned_url = payload.repo_url.strip().rstrip("/")

    # Return cached record if already analyzed and force_reanalyze is False
    if not payload.force_reanalyze:
        existing = (
            db.query(AnalysisRecord)
            .filter(AnalysisRecord.repo_url == cleaned_url)
            .order_by(AnalysisRecord.created_at.desc())
            .first()
        )
        if existing:
            return existing.to_dict()

    try:
        result = analyze_repository(cleaned_url, max_files=payload.max_files)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except requests.HTTPError as he:
        status = he.response.status_code if he.response is not None else 502
        if status == 403:
            raise HTTPException(
                status_code=429,
                detail="GitHub API rate limit exceeded. Add a GITHUB_TOKEN to Backend/.env for 5,000 requests/hr.",
            )
        raise HTTPException(
            status_code=status,
            detail=f"GitHub API error: {he}",
        )
    except Exception as exc:
        err_msg = str(exc)
        if "Connection refused" in err_msg or "11434" in err_msg or "ConnectError" in err_msg:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Cannot connect to local Ollama at {OLLAMA_BASE_URL}. "
                    f"Make sure Ollama is running and you have pulled '{OLLAMA_FAST_MODEL}' and '{OLLAMA_SMART_MODEL}'."
                ),
            )
        raise HTTPException(status_code=500, detail=f"Analysis failed: {err_msg}")

    record = AnalysisRecord(
        repo_url=cleaned_url,
        owner=result["owner"],
        repo=result["repo"],
        default_branch=result.get("default_branch", "main"),
        model=result.get("model", f"Hybrid ({OLLAMA_FAST_MODEL} + {OLLAMA_SMART_MODEL})"),
        selected_files_reasoning=result.get("selected_files_reasoning", ""),
        architecture_summary=result["architecture_summary"],
        mermaid_diagram=result["mermaid_diagram"],
        file_summaries_json=json.dumps(result.get("file_summaries", [])),
        onboarding_guide_json=json.dumps(result.get("onboarding_guide", {})),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return record.to_dict()


@app.get("/analyses")
@app.get("/api/analyses")
@app.get("/history")
@app.get("/api/history")
def list_analyses(db: Session = Depends(get_db)):
    """Return all saved repository analyses ordered from newest to oldest."""
    records = (
        db.query(AnalysisRecord)
        .order_by(AnalysisRecord.created_at.desc())
        .all()
    )
    return [r.to_summary_dict() for r in records]


@app.get("/analyses/{analysis_id}")
@app.get("/api/analyses/{analysis_id}")
def get_analysis_by_id(analysis_id: int, db: Session = Depends(get_db)):
    """Fetch a single saved repository analysis by ID."""
    record = db.query(AnalysisRecord).filter(AnalysisRecord.id == analysis_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"Analysis #{analysis_id} not found.")
    return record.to_dict()


@app.delete("/analyses/{analysis_id}")
@app.delete("/api/analyses/{analysis_id}")
def delete_analysis(analysis_id: int, db: Session = Depends(get_db)):
    """Delete a saved repository analysis from SQLite history."""
    record = db.query(AnalysisRecord).filter(AnalysisRecord.id == analysis_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"Analysis #{analysis_id} not found.")
    db.delete(record)
    db.commit()
    return {"deleted": True, "id": analysis_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

