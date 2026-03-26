"""
Saved candidates CRUD.
Candidates are fetched from 104, cached locally, and linked to projects.
When saved to a project, keywords from that project's industry+position are
auto-matched against the candidate's text and stored in candidate_keywords.
"""

import json
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from database import get_db

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _candidate_searchable_text(raw: dict) -> str:
    """Flatten all text fields of a candidate into one string for keyword matching."""
    fields = [
        raw.get("name", ""),
        raw.get("current_title", ""),
        raw.get("skills", ""),
        raw.get("education", ""),
        raw.get("location", ""),
        raw.get("self_intro", ""),
        raw.get("work_experience", ""),
        raw.get("edu_experience", ""),
        # add more fields as the actual 104 API response is discovered
    ]
    return " ".join(str(f) for f in fields if f).lower()


def _auto_tag_keywords(conn, candidate_id: int, project_id: int):
    """Match project-relevant keywords against candidate text and store hits."""
    project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        return

    candidate = conn.execute("SELECT raw_data FROM candidates WHERE id=?", (candidate_id,)).fetchone()
    if not candidate:
        return

    raw = json.loads(candidate["raw_data"]) if candidate["raw_data"] else {}
    text = _candidate_searchable_text(raw)

    # Keywords relevant to this project's industry and/or position
    kws = conn.execute(
        """SELECT id, term FROM keywords
           WHERE (industry_id = ? OR industry_id IS NULL)
             AND (position_id = ? OR position_id IS NULL)""",
        (project["industry_id"], project["position_id"]),
    ).fetchall()

    for kw in kws:
        if kw["term"].lower() in text:
            conn.execute(
                "INSERT OR IGNORE INTO candidate_keywords(candidate_id, keyword_id) VALUES(?,?)",
                (candidate_id, kw["id"]),
            )


# ── Save / upsert a candidate ─────────────────────────────────────────────────

class CandidateIn(BaseModel):
    candidate_104_id: str
    name: Optional[str] = None
    age: Optional[int] = None
    education: Optional[str] = None
    experience_years: Optional[int] = None
    location: Optional[str] = None
    current_title: Optional[str] = None
    expected_salary: Optional[str] = None
    skills: Optional[str] = None
    raw_data: Optional[dict] = None   # full JSON from 104 response
    project_id: Optional[int] = None  # save to this project immediately
    notes: Optional[str] = None       # note for the project link


@router.post("/", status_code=201)
def save_candidate(body: CandidateIn):
    conn = get_db()
    raw_json = json.dumps(body.raw_data) if body.raw_data else None

    # Upsert candidate
    conn.execute(
        """INSERT INTO candidates
               (candidate_104_id, name, age, education, experience_years,
                location, current_title, expected_salary, skills, raw_data)
           VALUES (?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(candidate_104_id) DO UPDATE SET
               name=excluded.name, age=excluded.age,
               education=excluded.education,
               experience_years=excluded.experience_years,
               location=excluded.location, current_title=excluded.current_title,
               expected_salary=excluded.expected_salary, skills=excluded.skills,
               raw_data=excluded.raw_data,
               snapshot_at=datetime('now')""",
        (
            body.candidate_104_id, body.name, body.age, body.education,
            body.experience_years, body.location, body.current_title,
            body.expected_salary, body.skills, raw_json,
        ),
    )
    conn.commit()
    candidate = conn.execute(
        "SELECT * FROM candidates WHERE candidate_104_id=?", (body.candidate_104_id,)
    ).fetchone()
    cid = candidate["id"]

    # Link to project and auto-tag keywords
    if body.project_id:
        conn.execute(
            "INSERT OR IGNORE INTO candidate_projects(candidate_id, project_id, notes) VALUES(?,?,?)",
            (cid, body.project_id, body.notes),
        )
        conn.commit()
        _auto_tag_keywords(conn, cid, body.project_id)
        conn.commit()

    result = dict(candidate)
    conn.close()
    return result


# ── List candidates ───────────────────────────────────────────────────────────

@router.get("/")
def list_candidates(
    project_id: Optional[int] = Query(None),
    keyword_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
):
    conn = get_db()
    q = "SELECT DISTINCT c.* FROM candidates c"
    joins, conditions, params = [], [], []

    if project_id:
        joins.append("JOIN candidate_projects cp ON cp.candidate_id=c.id")
        conditions.append("cp.project_id=?")
        params.append(project_id)

    if keyword_id:
        joins.append("JOIN candidate_keywords ck ON ck.candidate_id=c.id")
        conditions.append("ck.keyword_id=?")
        params.append(keyword_id)

    if search:
        conditions.append(
            "(LOWER(c.name) LIKE ? OR LOWER(c.current_title) LIKE ? "
            "OR LOWER(c.skills) LIKE ? OR LOWER(c.raw_data) LIKE ?)"
        )
        term = f"%{search.lower()}%"
        params += [term, term, term, term]

    if joins:      q += " " + " ".join(joins)
    if conditions: q += " WHERE " + " AND ".join(conditions)
    q += " ORDER BY c.snapshot_at DESC"

    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Single candidate ──────────────────────────────────────────────────────────

@router.get("/{candidate_id}")
def get_candidate(candidate_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Candidate not found.")
    result = dict(row)

    # Attach linked projects
    result["projects"] = [
        dict(r) for r in conn.execute(
            "SELECT p.*, cp.notes, cp.saved_at FROM projects p "
            "JOIN candidate_projects cp ON cp.project_id=p.id "
            "WHERE cp.candidate_id=?",
            (candidate_id,),
        ).fetchall()
    ]

    # Attach matched keywords
    result["keywords"] = [
        dict(r) for r in conn.execute(
            "SELECT k.* FROM keywords k "
            "JOIN candidate_keywords ck ON ck.keyword_id=k.id "
            "WHERE ck.candidate_id=?",
            (candidate_id,),
        ).fetchall()
    ]

    conn.close()
    return result


# ── Add candidate to a project ────────────────────────────────────────────────

class ProjectLink(BaseModel):
    project_id: int
    notes: Optional[str] = None


@router.post("/{candidate_id}/projects")
def link_to_project(candidate_id: int, body: ProjectLink):
    conn = get_db()
    if not conn.execute("SELECT 1 FROM candidates WHERE id=?", (candidate_id,)).fetchone():
        raise HTTPException(404, "Candidate not found.")
    conn.execute(
        "INSERT OR IGNORE INTO candidate_projects(candidate_id, project_id, notes) VALUES(?,?,?)",
        (candidate_id, body.project_id, body.notes),
    )
    conn.commit()
    _auto_tag_keywords(conn, candidate_id, body.project_id)
    conn.commit()
    conn.close()
    return {"status": "linked"}


@router.delete("/{candidate_id}/projects/{project_id}", status_code=204)
def unlink_from_project(candidate_id: int, project_id: int):
    conn = get_db()
    conn.execute(
        "DELETE FROM candidate_projects WHERE candidate_id=? AND project_id=?",
        (candidate_id, project_id),
    )
    conn.commit()
    conn.close()


@router.delete("/{candidate_id}", status_code=204)
def delete_candidate(candidate_id: int):
    conn = get_db()
    conn.execute("DELETE FROM candidates WHERE id=?", (candidate_id,))
    conn.commit()
    conn.close()
