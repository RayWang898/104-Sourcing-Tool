"""
Keywords knowledge base.
Structure: Industry → Position → [Keywords]
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_db

router = APIRouter()


# ── Industries ────────────────────────────────────────────────────────────────

class IndustryIn(BaseModel):
    name: str


@router.get("/industries")
def list_industries():
    conn = get_db()
    rows = conn.execute("SELECT * FROM industries ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/industries", status_code=201)
def create_industry(body: IndustryIn):
    conn = get_db()
    try:
        cur = conn.execute("INSERT INTO industries(name) VALUES(?)", (body.name.strip(),))
        conn.commit()
        row = conn.execute("SELECT * FROM industries WHERE id=?", (cur.lastrowid,)).fetchone()
        return dict(row)
    except Exception:
        raise HTTPException(409, f"Industry '{body.name}' already exists.")
    finally:
        conn.close()


@router.delete("/industries/{industry_id}", status_code=204)
def delete_industry(industry_id: int):
    conn = get_db()
    conn.execute("DELETE FROM industries WHERE id=?", (industry_id,))
    conn.commit()
    conn.close()


# ── Positions ─────────────────────────────────────────────────────────────────

class PositionIn(BaseModel):
    name: str
    industry_id: int


@router.get("/positions")
def list_positions(industry_id: Optional[int] = None):
    conn = get_db()
    if industry_id:
        rows = conn.execute(
            "SELECT p.*, i.name as industry_name FROM positions p "
            "JOIN industries i ON p.industry_id=i.id "
            "WHERE p.industry_id=? ORDER BY p.name",
            (industry_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT p.*, i.name as industry_name FROM positions p "
            "JOIN industries i ON p.industry_id=i.id ORDER BY i.name, p.name"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/positions", status_code=201)
def create_position(body: PositionIn):
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO positions(name, industry_id) VALUES(?,?)",
            (body.name.strip(), body.industry_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM positions WHERE id=?", (cur.lastrowid,)).fetchone()
        return dict(row)
    except Exception:
        raise HTTPException(409, f"Position '{body.name}' already exists in this industry.")
    finally:
        conn.close()


@router.delete("/positions/{position_id}", status_code=204)
def delete_position(position_id: int):
    conn = get_db()
    conn.execute("DELETE FROM positions WHERE id=?", (position_id,))
    conn.commit()
    conn.close()


# ── Keywords ──────────────────────────────────────────────────────────────────

class KeywordIn(BaseModel):
    term: str
    notes: Optional[str] = None
    industry_id: Optional[int] = None
    position_id: Optional[int] = None


class KeywordUpdate(BaseModel):
    term: Optional[str] = None
    notes: Optional[str] = None
    industry_id: Optional[int] = None
    position_id: Optional[int] = None


@router.get("/")
def list_keywords(industry_id: Optional[int] = None, position_id: Optional[int] = None):
    conn = get_db()
    q = """
        SELECT k.*,
               i.name AS industry_name,
               p.name AS position_name
        FROM keywords k
        LEFT JOIN industries i ON k.industry_id = i.id
        LEFT JOIN positions  p ON k.position_id  = p.id
    """
    conditions, params = [], []
    if industry_id is not None:
        conditions.append("k.industry_id = ?")
        params.append(industry_id)
    if position_id is not None:
        conditions.append("k.position_id = ?")
        params.append(position_id)
    if conditions:
        q += " WHERE " + " AND ".join(conditions)
    q += " ORDER BY k.term"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/", status_code=201)
def create_keyword(body: KeywordIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO keywords(term, notes, industry_id, position_id) VALUES(?,?,?,?)",
        (body.term.strip(), body.notes, body.industry_id, body.position_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT k.*, i.name AS industry_name, p.name AS position_name "
        "FROM keywords k LEFT JOIN industries i ON k.industry_id=i.id "
        "LEFT JOIN positions p ON k.position_id=p.id WHERE k.id=?",
        (cur.lastrowid,),
    ).fetchone()
    conn.close()
    return dict(row)


@router.put("/{keyword_id}")
def update_keyword(keyword_id: int, body: KeywordUpdate):
    conn = get_db()
    row = conn.execute("SELECT * FROM keywords WHERE id=?", (keyword_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Keyword not found.")
    updates = {}
    if body.term is not None:      updates["term"]        = body.term.strip()
    if body.notes is not None:     updates["notes"]       = body.notes
    if body.industry_id is not None: updates["industry_id"] = body.industry_id
    if body.position_id is not None: updates["position_id"] = body.position_id
    if updates:
        sets = ", ".join(f"{k}=?" for k in updates)
        conn.execute(f"UPDATE keywords SET {sets} WHERE id=?", (*updates.values(), keyword_id))
        conn.commit()
    row = conn.execute(
        "SELECT k.*, i.name AS industry_name, p.name AS position_name "
        "FROM keywords k LEFT JOIN industries i ON k.industry_id=i.id "
        "LEFT JOIN positions p ON k.position_id=p.id WHERE k.id=?",
        (keyword_id,),
    ).fetchone()
    conn.close()
    return dict(row)


@router.delete("/{keyword_id}", status_code=204)
def delete_keyword(keyword_id: int):
    conn = get_db()
    conn.execute("DELETE FROM keywords WHERE id=?", (keyword_id,))
    conn.commit()
    conn.close()
