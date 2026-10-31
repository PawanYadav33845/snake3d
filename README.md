# 🐍 Snake 3D — Cyber Grid Edition (Web & Multi-User) 🌐

An optimized, full 3D WebGL Snake game designed to be **hosted on a website for multiple players**, featuring a **significantly enlarged 3D arena**, **persistent player name & high-score leaderboard**, and **fluid camera-relative controls**.

---
🌐 **Live Demo:** [https://snake3d-2w40.onrender.com/](https://snake3d-2w40.onrender.com/)
## 🌟 Key Features

### 1. 🌐 Hosted on Web for Multiple Users
- **Multi-Player & Multi-Session**: Any number of users can play simultaneously in their own browser sessions from computers, laptops, tablets, or smartphones.
- **FastAPI Backend + Three.js Frontend**: High-performance asynchronous API server serving 60/120 FPS hardware-accelerated 3D WebGL graphics.
- **No Installs Needed for Players**: Players simply visit your URL (`http://your-domain.com` or `http://localhost:8000`).

### 2. 🏆 Player Name & Global High-Score Leaderboard
- **Pilot Callsign Registration**: Players can choose and save their custom pilot name.
- **Persistent SQLite Leaderboard**: Automatically records scores, player names, levels reached, arena sizes, difficulty modes, and timestamps.
- **Real-Time Leaderboard Modal**:
  - Filter by arena size (All Arenas, 24³, 32³, 40³).
  - Medals for Top 3 pilots (🥇 Gold, 🥈 Silver, 🥉 Bronze).
  - Highlights the current player's ranking.
- **Instant Save**: On Game Over, players can submit their score directly to the global database.

### 3. 🪐 Massive 3D Game Area
- **Expanded Grid Size**: Previous 20x20x20 arena expanded by over **400%**!
- **Selectable Arena Sizes in Menu**:
  - **Medium (24³)** — 13,824 voxels
  - **Large (32³)** — 32,768 voxels (*Default — over 4x larger!*)
  - **Massive (40³)** — 64,000 voxels (*8x larger than the original!*)
- **Adaptive 3D Infrastructure**: Camera distance, boundary cage, floor grid, beacons, and obstacles dynamically scale to the selected arena size.

### 4. 🎮 Seamless 3D Navigation & Controls
- **Smart Camera-Relative Controls**:
  - `W` / `S`: Screen Forward / Backward
  - `A` / `D`: Screen Left / Right
  - `Space` / `Q`: Ascend (Up)
  - `Shift` / `E`: Descend (Down)
  *(WASD always matches what you see on your monitor regardless of camera angle)*.
- **Anti-Suicide Input Queue**: Eliminates dropped inputs on quick cornering and prevents 180° accidental self-collisions.
- **Mobile Touch Controls**: Responsive on-screen directional buttons for phone and tablet gamers.

### 5. 👁️ 3D Depth Perception & Spatial Cues
- **Floor Drop Shadows**: Both the food and the snake's head project dark circular shadows and target rings onto the floor plane at `Y = -0.5`.
- **Vertical Neon Beacon**: A luminous vertical beam connects the floor target directly up to the floating food, completely eliminating depth ambiguity.
- **Wall Projection Indicators**: Side-wall projection dots display exact X, Y, and Z plane alignments.
- **Trajectory Guide Line (`G`)**: Toggle a direct targeting trajectory from the snake's head to the food with a live distance HUD readout.
- **Visor Eyes**: Distinct glowing visor eyes on the head clearly indicate movement direction.

### 6. 🎥 3 Camera Modes (`C`)
1. **Orbit Mode (Default)**: Free orbital view. Rotate using **Mouse Click & Drag** (Left/Right button) or Arrow Keys. Zoom using the **Mouse Scroll Wheel**. Press `R` to reset camera.
2. **Chase Mode (3D Flight / Pilot)**: Dynamic third-person camera tracking directly behind the snake's head for a cockpit-style flight experience.
3. **Auto-Track Mode**: Dynamically frames both the snake and the food at optimal cinematic angles.

### 7. 🔊 Web Audio Synthesizer
- Generates procedural audio effects in-memory using Web Audio API:
  - Melodic 2-tone chirp on eating food.
  - Tactile micro-click on turning.
  - 4-note ascending fanfare on level up.
  - Deep bass crunch & frequency sweep on game over.
  - Press `M` or click the speaker button to toggle mute/unmute.

---

## 🕹️ Controls Quick Reference

| Action | Control |
|---|---|
| **Steer Horizontal** | `W` (Fwd), `S` (Back), `A` (Left), `D` (Right) |
| **Steer Vertical** | `Space` / `Q` (Up), `Left Shift` / `E` (Down) |
| **Orbit Camera** | Click & Drag Mouse (Left/Right button) or Touch Drag |
| **Zoom Camera** | Mouse Scroll Wheel / Pinch |
| **Switch Camera Mode** | `C` (Orbit / Chase / Auto) |
| **Reset Camera** | `R` |
| **Toggle Target Guide** | `G` |
| **Pause / Resume** | `P` or `Space` |
| **Toggle Sound** | `M` |
| **Restart / Play Again** | `Space` or `Enter` (on Game Over) |
| **Main Menu** | Click "Main Menu" in modal |

---

## 🚀 How to Run Locally

### 1. Start the Web Server
Make sure you have Python installed, then run:

```powershell
python main.py
```

The server starts immediately and displays:
- **Local Browser:** `http://localhost:8000` (automatically opens in your default browser)
- **Local Network (LAN):** `http://<YOUR_IP>:8000` (other computers, phones, or friends on the same Wi-Fi can join!)

---

## ☁️ How to Host on a Website (Production Deployment)

### Option A: Free Cloud Hosting (Render / Railway / Fly.io)
1. Push this project folder to GitHub.
2. Connect your repository to **Render** (as a Web Service) or **Railway**:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python main.py`
3. The platform provides a free public HTTPS URL (e.g., `https://snake3d.onrender.com`) that anyone in the world can open to play!

### Option B: Docker Container
Build and run with Docker:

```bash
docker build -t snake3d .
docker run -d -p 8000:8000 --name snake3d-game snake3d
```

### Option C: Linux VPS (Ubuntu / Debian)
```bash
pip install -r requirements.txt
PORT=80 python main.py
```

---

## 📁 Project Structure

```
snake3d/
├── main.py             # FastAPI web server & REST API
├── database.py         # SQLite persistent leaderboard manager
├── requirements.txt    # Server dependencies (fastapi, uvicorn)
├── Dockerfile          # Production container setup
├── static/
│   ├── index.html      # Responsive Cyberpunk UI & HUD
│   ├── style.css       # Futuristic neon styles & mobile controls
│   └── game.js         # Full Three.js 3D WebGL engine & Web Audio
├── desktop_game.py     # Native Pygame/PyOpenGL version (for offline desktop play)
├── high_score.txt      # Legacy desktop score file
└── README.md           # Documentation
```
