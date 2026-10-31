import os
import sys
import socket
import webbrowser
import threading
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

import database

# Initialize FastAPI App
app = FastAPI(
    title="Snake 3D — Cyber Grid Edition",
    description="Multi-user 3D WebGL Snake Game with Global Leaderboards",
    version="2.0.0"
)

# Enable CORS for multi-domain hosting
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static directory
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# -----------------------------------------------------------------------------
# PYDANTIC MODELS
# -----------------------------------------------------------------------------
class ScoreSubmission(BaseModel):
    player_name: str = Field(..., min_length=1, max_length=24, description="Pilot name")
    score: int = Field(..., ge=0, description="Final score")
    level: int = Field(default=1, ge=1, description="Level reached")
    grid_size: int = Field(default=32, ge=10, le=100, description="Arena size")
    difficulty: str = Field(default="Normal", description="Difficulty mode")

# -----------------------------------------------------------------------------
# ROUTES
# -----------------------------------------------------------------------------
@app.get("/")
async def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="index.html not found")

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "snake3d-server"}

@app.get("/api/leaderboard")
async def get_leaderboard(
    limit: int = Query(default=20, ge=1, le=100),
    grid_size: Optional[int] = Query(default=None)
):
    try:
        scores = database.get_top_scores(limit=limit, grid_size=grid_size)
        return scores
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/api/score")
async def submit_score(payload: ScoreSubmission):
    try:
        inserted_id = database.add_score(
            player_name=payload.player_name,
            score=payload.score,
            level=payload.level,
            grid_size=payload.grid_size,
            difficulty=payload.difficulty
        )
        return {
            "success": True,
            "id": inserted_id,
            "message": f"Score of {payload.score} by '{payload.player_name}' recorded!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record score: {str(e)}")

@app.get("/api/stats")
async def get_stats():
    try:
        return database.get_leaderboard_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------------
# AUTO-LAUNCHER & SERVER ENTRY POINT
# -----------------------------------------------------------------------------
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def open_browser_delayed(url: str):
    time.sleep(1.0)
    try:
        webbrowser.open(url)
    except Exception:
        pass

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))
    local_ip = get_local_ip()

    print("\n" + "=" * 65)
    print("  🚀 SNAKE 3D — CYBER GRID EDITION (Web Server)")
    print("=" * 65)
    print(f"  ► Local Browser:     http://localhost:{port}")
    print(f"  ► Network (LAN):     http://{local_ip}:{port}")
    print(f"  ► Online Hosting:    Ready for Render, Railway, Docker, etc.")
    print("=" * 65)
    print("  Press Ctrl+C to stop the server.\n")

    # If launched locally on desktop, automatically open in browser
    if os.environ.get("AUTO_OPEN", "1") == "1":
        threading.Thread(target=open_browser_delayed, args=(f"http://localhost:{port}",), daemon=True).start()

    uvicorn.run("main:app", host=host, port=port, log_level="info")
