import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database import init_db
from api import search, keywords, candidates, projects

app = FastAPI(title="104 Sourcing Tool", version="1.0.0")

init_db()

app.include_router(search.router,     prefix="/api/search",     tags=["search"])
app.include_router(keywords.router,   prefix="/api/keywords",   tags=["keywords"])
app.include_router(candidates.router, prefix="/api/candidates", tags=["candidates"])
app.include_router(projects.router,   prefix="/api/projects",   tags=["projects"])

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def root():
    return FileResponse(os.path.join(static_dir, "index.html"))


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
