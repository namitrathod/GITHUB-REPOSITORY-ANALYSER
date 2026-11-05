"""
Stage 2: SQLite Database Configuration & SQLAlchemy Models
Stores completed repository analyses so they can be viewed anytime in History without re-running the LLM.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "analyses.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class AnalysisRecord(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    repo_url = Column(String(512), nullable=False, index=True)
    owner = Column(String(255), nullable=False)
    repo = Column(String(255), nullable=False)
    default_branch = Column(String(128), nullable=False, default="main")
    model = Column(String(255), nullable=False, default="gemma3:4b + gemma3:12b")
    selected_files_reasoning = Column(Text, nullable=True, default="")
    architecture_summary = Column(Text, nullable=False)
    mermaid_diagram = Column(Text, nullable=False)
    file_summaries_json = Column(Text, nullable=False, default="[]")
    onboarding_guide_json = Column(Text, nullable=False, default="{}")
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert database row into the full structured analysis response dictionary."""
        try:
            file_summaries = json.loads(self.file_summaries_json or "[]")
        except Exception:
            file_summaries = []

        try:
            onboarding_guide = json.loads(self.onboarding_guide_json or "{}")
        except Exception:
            onboarding_guide = {
                "project_overview": "",
                "reading_order": [],
                "setup_and_run_steps": [],
                "where_to_make_changes": [],
            }

        return {
            "id": self.id,
            "repo_url": self.repo_url,
            "owner": self.owner,
            "repo": self.repo,
            "default_branch": self.default_branch,
            "model": self.model,
            "selected_files_reasoning": self.selected_files_reasoning or "",
            "architecture_summary": self.architecture_summary,
            "mermaid_diagram": self.mermaid_diagram,
            "file_summaries": file_summaries,
            "onboarding_guide": onboarding_guide,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_summary_dict(self) -> Dict[str, Any]:
        """Lightweight dictionary for the History sidebar/list view."""
        try:
            file_count = len(json.loads(self.file_summaries_json or "[]"))
        except Exception:
            file_count = 0

        return {
            "id": self.id,
            "repo_url": self.repo_url,
            "owner": self.owner,
            "repo": self.repo,
            "default_branch": self.default_branch,
            "model": self.model,
            "file_count": file_count,
            "architecture_preview": (self.architecture_summary or "")[:180] + (
                "..." if len(self.architecture_summary or "") > 180 else ""
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def init_db() -> None:
    """Create database tables if they do not exist yet."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency yielding a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

