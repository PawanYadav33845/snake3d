import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "leaderboard.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT NOT NULL,
            score INTEGER NOT NULL,
            level INTEGER NOT NULL,
            grid_size INTEGER NOT NULL,
            difficulty TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scores ON scores(score DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_grid ON scores(grid_size)")
    conn.commit()
    conn.close()

def add_score(player_name: str, score: int, level: int = 1, grid_size: int = 32, difficulty: str = "Normal"):
    clean_name = player_name.strip()[:20] if player_name and player_name.strip() else "Anonymous"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO scores (player_name, score, level, grid_size, difficulty, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (clean_name, score, level, grid_size, difficulty, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    inserted_id = cursor.lastrowid
    conn.close()
    return inserted_id

def get_top_scores(limit: int = 20, grid_size: int = None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if grid_size:
        cursor.execute("""
            SELECT id, player_name, score, level, grid_size, difficulty, created_at
            FROM scores
            WHERE grid_size = ?
            ORDER BY score DESC, created_at ASC
            LIMIT ?
        """, (grid_size, limit))
    else:
        cursor.execute("""
            SELECT id, player_name, score, level, grid_size, difficulty, created_at
            FROM scores
            ORDER BY score DESC, created_at ASC
            LIMIT ?
        """, (limit,))
        
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "player_name": r["player_name"],
            "score": r["score"],
            "level": r["level"],
            "grid_size": r["grid_size"],
            "difficulty": r["difficulty"],
            "created_at": r["created_at"]
        })
    return results

def get_leaderboard_stats():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), MAX(score) FROM scores")
    count, max_score = cursor.fetchone()
    conn.close()
    return {
        "total_games": count or 0,
        "all_time_high": max_score or 0
    }

# Initialize on import
init_db()
