"""
Projects (recruiting requisitions) CRUD.
Each project = one sourcing initiative: Company + Industry + Position.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_db

router = APIRouter()


class ProjectIn(BaseModel):
    name: str
    company: Optional[str] = None
    industry_id: Optional[int] = None
    position_id: Optional[int] = None
    notes: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    industry_id: Optional[int] = None
    position_id: Optional[int] = None
    notes: Optional[str] = None


def _project_with_meta(conn, project_id: int) -> dict:
    row = conn.execute(
        """SELECT p.*,
                  i.name AS industry_name,
                  pos.name AS position_name,
                  (SELECT COUNT(*) FROM candidate_projects cp WHERE cp.project_id=p.id) AS candidate_count
           FROM projects p
           LEFT JOIN industries i   ON p.industry_id  = i.id
           LEFT JOIN positions  pos ON p.position_id  = pos.id
           WHERE p.id = ?""",
        (project_id,),
    ).fetchone()
    return dict(row) if row else None


@router.get("/")
def list_projects():
    conn = get_db()
    rows = conn.execute(
        """SELECT p.*,
                  i.name AS industry_name,
                  pos.name AS position_name,
                  (SELECT COUNT(*) FROM candidate_projects cp WHERE cp.project_id=p.id) AS candidate_count
           FROM projects p
           LEFT JOIN industries i   ON p.industry_id  = i.id
           LEFT JOIN positions  pos ON p.position_id  = pos.id
           ORDER BY p.created_at DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/", status_code=201)
def create_project(body: ProjectIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO projects(name, company, industry_id, position_id, notes) VALUES(?,?,?,?,?)",
        (body.name.strip(), body.company, body.industry_id, body.position_id, body.notes),
    )
    conn.commit()
    result = _project_with_meta(conn, cur.lastrowid)
    conn.close()
    return result


@router.get("/{project_id}")
def get_project(project_id: int):
    conn = get_db()
    result = _project_with_meta(conn, project_id)
    if not result:
        raise HTTPException(404, "Project not found.")

    # Attach keywords relevant to this project
    result["keywords"] = [
        dict(r) for r in conn.execute(
            """SELECT k.* FROM keywords k
               WHERE (k.industry_id=? OR k.industry_id IS NULL)
                 AND (k.position_id=? OR k.position_id IS NULL)
               ORDER BY k.term""",
            (result.get("industry_id"), result.get("position_id")),
        ).fetchall()
    ]
    conn.close()
    return result


@router.put("/{project_id}")
def update_project(project_id: int, body: ProjectUpdate):
    conn = get_db()
    if not conn.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
        raise HTTPException(404, "Project not found.")
    updates = {}
    if body.name is not None:        updates["name"]        = body.name.strip()
    if body.company is not None:     updates["company"]     = body.company
    if body.industry_id is not None: updates["industry_id"] = body.industry_id
    if body.position_id is not None: updates["position_id"] = body.position_id
    if body.notes is not None:       updates["notes"]       = body.notes
    if updates:
        sets = ", ".join(f"{k}=?" for k in updates)
        conn.execute(f"UPDATE projects SET {sets} WHERE id=?", (*updates.values(), project_id))
        conn.commit()
    result = _project_with_meta(conn, project_id)
    conn.close()
    return result


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int):
    conn = get_db()
    conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    conn.commit()
    conn.close()


@router.get("/{project_id}/candidates")
def get_project_candidates(project_id: int):
    conn = get_db()
    rows = conn.execute(
        """SELECT c.*, cp.notes AS project_notes, cp.saved_at
           FROM candidates c
           JOIN candidate_projects cp ON cp.candidate_id=c.id
           WHERE cp.project_id=?
           ORDER BY cp.saved_at DESC""",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/{project_id}/keywords")
def get_project_keywords(project_id: int):
    conn = get_db()
    project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        raise HTTPException(404, "Project not found.")
    rows = conn.execute(
        """SELECT k.*, i.name AS industry_name, p.name AS position_name
           FROM keywords k
           LEFT JOIN industries i ON k.industry_id=i.id
           LEFT JOIN positions  p ON k.position_id=p.id
           WHERE (k.industry_id=? OR k.industry_id IS NULL)
             AND (k.position_id=? OR k.position_id IS NULL)
           ORDER BY k.term""",
        (project["industry_id"], project["position_id"]),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
