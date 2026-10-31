import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import random
import os
import sys
import math
import time

# =============================================================================
# CONSTANTS & CONFIGURATION
# =============================================================================
GRID_SIZE = 30
CUBE_SIZE = 1.0
ARENA_MIN = -0.5
ARENA_MAX = GRID_SIZE - 0.5
ARENA_CENTER = (GRID_SIZE - 1) / 2.0

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 750
TARGET_FPS = 60

# Game States
STATE_MENU = 0
STATE_PLAYING = 1
STATE_PAUSED = 2
STATE_GAME_OVER = 3

# Camera Modes
CAM_ORBIT = 0
CAM_CHASE = 1
CAM_AUTO = 2
CAM_MODE_NAMES = ["Orbit (Free Cam)", "Chase (3D Follow)", "Auto-Track"]

# Difficulties (Base steps per second)
DIFFICULTIES = {
    "Casual": 4.5,
    "Normal": 6.5,
    "Fast": 9.5,
    "Insane": 13.5
}
DIFF_KEYS = list(DIFFICULTIES.keys())

# Level thresholds for obstacle & speed increases
LEVEL_THRESHOLDS = [5, 12, 22, 35, 50]

# Direction vectors in 3D
DIR_UP = np.array([0, 1, 0])
DIR_DOWN = np.array([0, -1, 0])
DIR_LEFT = np.array([-1, 0, 0])
DIR_RIGHT = np.array([1, 0, 0])
DIR_FORWARD = np.array([0, 0, 1])
DIR_BACKWARD = np.array([0, 0, -1])

CARDINAL_HORIZONTAL = [
    np.array([ 1, 0,  0]),
    np.array([-1, 0,  0]),
    np.array([ 0, 0,  1]),
    np.array([ 0, 0, -1])
]

# High score file
HIGH_SCORE_FILE = "high_score.txt"

# =============================================================================
# AUDIO SYNTHESIS SYSTEM (Procedural Sound Effects)
# =============================================================================
class SoundManager:
    def __init__(self):
        self.enabled = True
        self.sounds = {}
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self._generate_sounds()
        except Exception as e:
            print(f"Audio init warning: {e}. Audio disabled.")
            self.enabled = False

    def _generate_sounds(self):
        sr = 44100

        # 1. Eat Food chime (bright 2-tone melodic chirp)
        t1 = np.linspace(0, 0.05, int(sr * 0.05), False)
        t2 = np.linspace(0, 0.10, int(sr * 0.10), False)
        w1 = np.sin(2 * np.pi * 659.25 * t1) * np.exp(-t1 * 18)
        w2 = np.sin(2 * np.pi * 987.77 * t2) * np.exp(-t2 * 12)
        wave_eat = np.concatenate([w1, w2])
        self.sounds['eat'] = self._make_sound(wave_eat * 18000)

        # 2. Turn click (tactile micro-click)
        t = np.linspace(0, 0.02, int(sr * 0.02), False)
        wave_turn = np.sin(2 * np.pi * 440 * t) * np.exp(-t * 120)
        self.sounds['turn'] = self._make_sound(wave_turn * 12000)

        # 3. Crash / Game Over (crunch + sub-bass frequency sweep)
        tc = np.linspace(0, 0.40, int(sr * 0.40), False)
        freq = np.linspace(280, 35, len(tc))
        sweep = np.sin(2 * np.pi * freq * tc)
        noise = np.random.uniform(-0.5, 0.5, len(tc))
        wave_crash = (sweep * 0.7 + noise * 0.3) * np.exp(-tc * 6)
        self.sounds['crash'] = self._make_sound(wave_crash * 22000)

        # 4. Level Up fanfare (ascending 4-note arpeggio)
        notes = [523.25, 659.25, 783.99, 1046.50]
        chunks = []
        for n in notes:
            tn = np.linspace(0, 0.07, int(sr * 0.07), False)
            wn = (np.sin(2 * np.pi * n * tn) + 0.3 * np.sin(4 * np.pi * n * tn)) * np.exp(-tn * 8)
            chunks.append(wn)
        wave_lvl = np.concatenate(chunks)
        self.sounds['levelup'] = self._make_sound(wave_lvl * 17000)

        # 5. Pause blip
        tp = np.linspace(0, 0.06, int(sr * 0.06), False)
        wave_pause = (np.sin(2 * np.pi * 880 * tp) * 0.5 + np.sin(2 * np.pi * 1760 * tp) * 0.5) * np.exp(-tp * 20)
        self.sounds['pause'] = self._make_sound(wave_pause * 14000)

    def _make_sound(self, mono_array):
        mono = mono_array.astype(np.int16)
        stereo = np.column_stack((mono, mono))
        return pygame.sndarray.make_sound(stereo)

    def play(self, name):
        if self.enabled and name in self.sounds:
            try:
                self.sounds[name].play()
            except Exception:
                pass

    def toggle_mute(self):
        self.enabled = not self.enabled
        return self.enabled

# =============================================================================
# TEXTURE & OPENGL DISPLAY LIST MANAGER
# =============================================================================
textures = {}
DL_CUBE = 0
DL_FLOOR_GRID = 0
DL_BOUNDS = 0

def create_cyber_texture(col_bg, col_border, col_accent, pattern="frame", size=128):
    surf = pygame.Surface((size, size))
    surf.fill(col_bg)
    
    # Outer border
    pygame.draw.rect(surf, col_border, (0, 0, size, size), 6)
    
    if pattern == "frame":
        pygame.draw.rect(surf, col_accent, (14, 14, size - 28, size - 28), 2)
        # Chamfer corners
        pygame.draw.line(surf, col_border, (0, 0), (18, 18), 3)
        pygame.draw.line(surf, col_border, (size, 0), (size - 18, 18), 3)
        pygame.draw.line(surf, col_border, (0, size), (18, size - 18), 3)
        pygame.draw.line(surf, col_border, (size, size), (size - 18, size - 18), 3)
    elif pattern == "crystal":
        # Diamond facets
        center = size // 2
        pts = [(center, 12), (size - 12, center), (center, size - 12), (12, center)]
        pygame.draw.polygon(surf, col_accent, pts, 3)
        pygame.draw.circle(surf, (255, 255, 255), (center, center), 8)
    elif pattern == "hazard":
        # Diagonal hazard stripes
        for offset in range(-size, size * 2, 24):
            pygame.draw.line(surf, col_accent, (offset, 0), (offset + size, size), 8)
        pygame.draw.rect(surf, col_border, (0, 0, size, size), 6)

    return surf

def load_gl_textures():
    global textures
    tex_specs = {
        "snake_head": ((10, 45, 35), (0, 255, 190), (120, 255, 240), "frame"),
        "snake_body": ((12, 35, 45), (0, 180, 230), (0, 120, 180), "frame"),
        "food": ((60, 10, 20), (255, 40, 70), (255, 210, 80), "crystal"),
        "obstacle": ((30, 20, 15), (255, 90, 0), (255, 160, 20), "hazard")
    }

    for name, (bg, border, accent, pat) in tex_specs.items():
        surf = create_cyber_texture(bg, border, accent, pat)
        data = pygame.image.tostring(surf, "RGB", True)
        w, h = surf.get_size()
        
        tid = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tid)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        gluBuild2DMipmaps(GL_TEXTURE_2D, GL_RGB, w, h, GL_RGB, GL_UNSIGNED_BYTE, data)
        textures[name] = tid

def compile_display_lists():
    global DL_CUBE, DL_FLOOR_GRID, DL_BOUNDS
    
    # 1. Standard Unit Cube [-0.5, 0.5]^3
    DL_CUBE = glGenLists(1)
    glNewList(DL_CUBE, GL_COMPILE)
    s = 0.5
    glBegin(GL_QUADS)
    # Front Face
    glNormal3f(0, 0, 1)
    glTexCoord2f(0, 0); glVertex3f(-s, -s,  s)
    glTexCoord2f(1, 0); glVertex3f( s, -s,  s)
    glTexCoord2f(1, 1); glVertex3f( s,  s,  s)
    glTexCoord2f(0, 1); glVertex3f(-s,  s,  s)
    # Back Face
    glNormal3f(0, 0, -1)
    glTexCoord2f(1, 0); glVertex3f(-s, -s, -s)
    glTexCoord2f(1, 1); glVertex3f(-s,  s, -s)
    glTexCoord2f(0, 1); glVertex3f( s,  s, -s)
    glTexCoord2f(0, 0); glVertex3f( s, -s, -s)
    # Top Face
    glNormal3f(0, 1, 0)
    glTexCoord2f(0, 1); glVertex3f(-s,  s, -s)
    glTexCoord2f(0, 0); glVertex3f(-s,  s,  s)
    glTexCoord2f(1, 0); glVertex3f( s,  s,  s)
    glTexCoord2f(1, 1); glVertex3f( s,  s, -s)
    # Bottom Face
    glNormal3f(0, -1, 0)
    glTexCoord2f(1, 1); glVertex3f(-s, -s, -s)
    glTexCoord2f(0, 1); glVertex3f( s, -s, -s)
    glTexCoord2f(0, 0); glVertex3f( s, -s,  s)
    glTexCoord2f(1, 0); glVertex3f(-s, -s,  s)
    # Right Face
    glNormal3f(1, 0, 0)
    glTexCoord2f(1, 0); glVertex3f( s, -s, -s)
    glTexCoord2f(1, 1); glVertex3f( s,  s, -s)
    glTexCoord2f(0, 1); glVertex3f( s,  s,  s)
    glTexCoord2f(0, 0); glVertex3f( s, -s,  s)
    # Left Face
    glNormal3f(-1, 0, 0)
    glTexCoord2f(0, 0); glVertex3f(-s, -s, -s)
    glTexCoord2f(1, 0); glVertex3f(-s, -s,  s)
    glTexCoord2f(1, 1); glVertex3f(-s,  s,  s)
    glTexCoord2f(0, 1); glVertex3f(-s,  s, -s)
    glEnd()
    glEndList()

    # 2. Floor Grid & Arena Boundary Wireframe
    DL_FLOOR_GRID = glGenLists(1)
    glNewList(DL_FLOOR_GRID, GL_COMPILE)
    glDisable(GL_TEXTURE_2D)
    glDisable(GL_LIGHTING)
    
    # Semi-transparent floor plane
    glBegin(GL_QUADS)
    glColor4f(0.03, 0.06, 0.12, 0.55)
    glVertex3f(ARENA_MIN, ARENA_MIN, ARENA_MIN)
    glVertex3f(ARENA_MAX, ARENA_MIN, ARENA_MIN)
    glVertex3f(ARENA_MAX, ARENA_MIN, ARENA_MAX)
    glVertex3f(ARENA_MIN, ARENA_MIN, ARENA_MAX)
    glEnd()

    # Floor grid lines (cyan/indigo)
    glLineWidth(1.0)
    glColor4f(0.12, 0.28, 0.48, 0.55)
    glBegin(GL_LINES)
    for i in range(GRID_SIZE + 1):
        pos = i - 0.5
        glVertex3f(ARENA_MIN, ARENA_MIN, pos)
        glVertex3f(ARENA_MAX, ARENA_MIN, pos)
        glVertex3f(pos, ARENA_MIN, ARENA_MIN)
        glVertex3f(pos, ARENA_MIN, ARENA_MAX)
    glEnd()

    # 12 Outer Boundary Edge Rails (Glowing Cyan Cage)
    glLineWidth(2.2)
    glColor4f(0.20, 0.65, 0.95, 0.85)
    mi = ARENA_MIN
    ma = ARENA_MAX
    glBegin(GL_LINES)
    # Bottom
    glVertex3f(mi, mi, mi); glVertex3f(ma, mi, mi)
    glVertex3f(ma, mi, mi); glVertex3f(ma, mi, ma)
    glVertex3f(ma, mi, ma); glVertex3f(mi, mi, ma)
    glVertex3f(mi, mi, ma); glVertex3f(mi, mi, mi)
    # Top
    glVertex3f(mi, ma, mi); glVertex3f(ma, ma, mi)
    glVertex3f(ma, ma, mi); glVertex3f(ma, ma, ma)
    glVertex3f(ma, ma, ma); glVertex3f(mi, ma, ma)
    glVertex3f(mi, ma, ma); glVertex3f(mi, ma, mi)
    # Vertical Pillars
    glVertex3f(mi, mi, mi); glVertex3f(mi, ma, mi)
    glVertex3f(ma, mi, mi); glVertex3f(ma, ma, mi)
    glVertex3f(ma, mi, ma); glVertex3f(ma, ma, ma)
    glVertex3f(mi, mi, ma); glVertex3f(mi, ma, ma)
    glEnd()

    glEnable(GL_LIGHTING)
    glEnable(GL_TEXTURE_2D)
    glEndList()

# =============================================================================
# OPTIMIZED TEXT & 2D HUD RENDERER
# =============================================================================
_font_cache = {}
_text_surface_cache = {}

def get_font(size=18, bold=True):
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.SysFont("Consolas, Arial, sans-serif", size, bold=bold)
    return _font_cache[key]

def draw_text(pos, text_str, color=(255, 255, 255, 255), size=18, bold=True):
    """Cached high-performance text rasterization."""
    key = (text_str, color, size, bold)
    if key not in _text_surface_cache:
        font = get_font(size, bold)
        surf = font.render(text_str, True, color)
        data = pygame.image.tostring(surf, "RGBA", True)
        _text_surface_cache[key] = (surf.get_width(), surf.get_height(), data)
        if len(_text_surface_cache) > 400:
            _text_surface_cache.clear()
            
    w, h, data = _text_surface_cache[key]
    glWindowPos2d(pos[0], pos[1])
    glDrawPixels(w, h, GL_RGBA, GL_UNSIGNED_BYTE, data)

def draw_panel(x, y, w, h, bg_color=(10, 20, 36, 210), border_color=(45, 100, 180, 230)):
    glDisable(GL_TEXTURE_2D)
    glBegin(GL_QUADS)
    glColor4ub(*bg_color)
    glVertex2f(x, y)
    glVertex2f(x + w, y)
    glVertex2f(x + w, y + h)
    glVertex2f(x, y + h)
    glEnd()

    glLineWidth(1.5)
    glBegin(GL_LINE_LOOP)
    glColor4ub(*border_color)
    glVertex2f(x, y)
    glVertex2f(x + w, y)
    glVertex2f(x + w, y + h)
    glVertex2f(x, y + h)
    glEnd()
    glEnable(GL_TEXTURE_2D)

def draw_progress_bar(x, y, w, h, fraction, fill_color=(0, 230, 180, 240)):
    draw_panel(x, y, w, h, bg_color=(15, 26, 42, 220), border_color=(40, 80, 130, 180))
    glDisable(GL_TEXTURE_2D)
    fill_w = max(0, min(w - 4, int((w - 4) * fraction)))
    if fill_w > 0:
        glBegin(GL_QUADS)
        glColor4ub(*fill_color)
        glVertex2f(x + 2, y + 2)
        glVertex2f(x + 2 + fill_w, y + 2)
        glVertex2f(x + 2 + fill_w, y + h - 2)
        glVertex2f(x + 2, y + h - 2)
        glEnd()
    glEnable(GL_TEXTURE_2D)

# =============================================================================
# 3D BILLBOARDED PARTICLE SYSTEM
# =============================================================================
class Particle:
    def __init__(self, position, color, max_life=0.8, vel_scale=2.2):
        self.pos = np.array(position, dtype=float)
        # Uniform spherical velocity burst
        theta = random.uniform(0, 2 * math.pi)
        phi = random.uniform(0, math.pi)
        speed = random.uniform(0.8, vel_scale)
        self.vel = np.array([
            speed * math.sin(phi) * math.cos(theta),
            speed * math.cos(phi),
            speed * math.sin(phi) * math.sin(theta)
        ])
        self.color = color
        self.life = max_life
        self.max_life = max_life
        self.size = random.uniform(0.12, 0.22)

    def update(self, dt):
        self.pos += self.vel * dt
        self.vel *= (0.96 ** (dt * 60))
        self.life -= dt

# =============================================================================
# GAME CORE & STATE
# =============================================================================
class Game3D:
    def __init__(self):
        self.sound_mgr = SoundManager()
        self.state = STATE_MENU
        self.score = 0
        self.high_score = self.load_high_score()
        self.level = 1
        self.apples_eaten = 0
        self.selected_diff_idx = 1 # Normal
        self.base_speed = DIFFICULTIES[DIFF_KEYS[self.selected_diff_idx]]
        
        # Camera
        self.cam_mode = CAM_ORBIT
        self.cam_angle_x = 45.0
        self.cam_angle_y = 35.0
        self.cam_distance = 58.0
        self.mouse_dragging = False
        self.last_mouse_pos = (0, 0)
        self.chase_cam_pos = np.array([ARENA_CENTER, ARENA_CENTER, ARENA_CENTER], dtype=float)
        self.chase_look_pos = np.array([ARENA_CENTER, ARENA_CENTER, ARENA_CENTER], dtype=float)
        
        # 3D Visual Aids
        self.show_guide_lines = True
        self.near_wall_warning = False
        
        # Game Entities
        self.snake = []
        self.prev_snake = []
        self.direction = DIR_FORWARD.copy()
        self.input_queue = []
        self.food = np.array([5, 5, 5])
        self.obstacles = []
        self.particles = []
        
        # Timing & Interpolation
        self.step_timer = 0.0
        self.step_interval = 1.0 / self.base_speed
        self.game_time = 0.0
        self.level_up_banner_timer = 0.0
        self.new_high_score_achieved = False

    def load_high_score(self):
        if os.path.exists(HIGH_SCORE_FILE):
            try:
                with open(HIGH_SCORE_FILE, "r") as f:
                    return int(f.read().strip())
            except Exception:
                return 0
        return 0

    def save_high_score(self):
        try:
            with open(HIGH_SCORE_FILE, "w") as f:
                f.write(str(self.high_score))
        except Exception:
            pass

    def reset_game(self):
        self.score = 0
        self.level = 1
        self.apples_eaten = 0
        self.new_high_score_achieved = False
        self.level_up_banner_timer = 0.0
        self.particles.clear()
        self.input_queue.clear()
        
        start_x = GRID_SIZE // 2
        start_y = GRID_SIZE // 2
        start_z = GRID_SIZE // 2
        
        self.snake = [
            np.array([start_x, start_y, start_z - 2]),
            np.array([start_x, start_y, start_z - 1]),
            np.array([start_x, start_y, start_z])
        ]
        self.prev_snake = [s.copy() for s in self.snake]
        self.direction = DIR_FORWARD.copy()
        
        self.base_speed = DIFFICULTIES[DIFF_KEYS[self.selected_diff_idx]]
        self.step_interval = 1.0 / self.base_speed
        self.step_timer = 0.0
        
        self.spawn_food()
        self.generate_obstacles()
        
        # Initialize chase camera
        self.chase_cam_pos = self.snake[-1] - self.direction * 8.0 + np.array([0, 3.0, 0])
        self.chase_look_pos = self.snake[-1] + self.direction * 3.0

    def generate_obstacles(self):
        self.obstacles = []
        # Level 1 has 0 obstacles for clean practice; increments afterwards
        num_obstacles = 0 if self.level == 1 else (self.level - 1) * 4
        
        head = self.snake[-1]
        attempts = 0
        while len(self.obstacles) < num_obstacles and attempts < 1000:
            attempts += 1
            obs = np.random.randint(1, GRID_SIZE - 1, size=3)
            # Safe zone: never spawn within 4 blocks Manhattan distance of snake head
            if np.sum(np.abs(obs - head)) <= 4:
                continue
            if any((obs == s).all() for s in self.snake):
                continue
            if (obs == self.food).all():
                continue
            if any((obs == o).all() for o in self.obstacles):
                continue
            self.obstacles.append(obs)

    def spawn_food(self):
        while True:
            pos = np.random.randint(1, GRID_SIZE - 1, size=3)
            if not any((pos == s).all() for s in self.snake) and not any((pos == o).all() for o in self.obstacles):
                self.food = pos
                break

    def enqueue_turn(self, new_dir):
        """Enqueue move with anti-180-suicide guard."""
        ref_dir = self.input_queue[-1] if self.input_queue else self.direction
        if np.array_equal(new_dir, ref_dir):
            return
        if np.array_equal(new_dir, -ref_dir):
            return
        if len(self.input_queue) < 3:
            self.input_queue.append(new_dir)
            self.sound_mgr.play('turn')

    def get_camera_relative_dir(self, action):
        """Maps WASD / Space / Shift seamlessly to screen-relative directions."""
        rad = math.radians(self.cam_angle_x)
        # Vector from camera to center on horizontal XZ plane
        fx = -math.cos(rad)
        fz = -math.sin(rad)
        # Perpendicular right vector on XZ plane: (Forward x Up)
        rx = -fz
        rz = fx
        
        if action == 'FORWARD':
            target = np.array([fx, 0.0, fz])
            return max(CARDINAL_HORIZONTAL, key=lambda c: np.dot(target, c))
        elif action == 'BACKWARD':
            target = np.array([-fx, 0.0, -fz])
            return max(CARDINAL_HORIZONTAL, key=lambda c: np.dot(target, c))
        elif action == 'RIGHT':
            target = np.array([rx, 0.0, rz])
            return max(CARDINAL_HORIZONTAL, key=lambda c: np.dot(target, c))
        elif action == 'LEFT':
            target = np.array([-rx, 0.0, -rz])
            return max(CARDINAL_HORIZONTAL, key=lambda c: np.dot(target, c))
        elif action == 'UP':
            return DIR_UP
        elif action == 'DOWN':
            return DIR_DOWN
        return None

    def update_logic(self, dt):
        self.game_time += dt
        
        # Update particles
        for p in self.particles[:]:
            p.update(dt)
            if p.life <= 0:
                self.particles.remove(p)
                
        if self.level_up_banner_timer > 0:
            self.level_up_banner_timer -= dt

        # Step timer accumulator
        self.step_timer += dt
        if self.step_timer < self.step_interval:
            return

        self.step_timer -= self.step_interval

        # Apply queued direction
        if self.input_queue:
            self.direction = self.input_queue.pop(0)

        # Store previous positions for smooth 60 FPS interpolation
        self.prev_snake = [s.copy() for s in self.snake]

        new_head = self.snake[-1] + self.direction

        # Boundary collision check
        hit_boundary = any((new_head < 0) | (new_head >= GRID_SIZE))
        # Self collision check
        hit_self = any((new_head == s).all() for s in self.snake[:-1])
        # Obstacle collision check
        hit_obstacle = any((new_head == o).all() for o in self.obstacles)

        if hit_boundary or hit_self or hit_obstacle:
            self.sound_mgr.play('crash')
            # Spawn dramatic explosion particles from all snake segments
            for seg in self.snake:
                for _ in range(8):
                    self.particles.append(Particle(seg + 0.5, (0.0, 0.8, 1.0), max_life=1.4, vel_scale=3.5))
            for _ in range(30):
                self.particles.append(Particle(new_head + 0.5, (1.0, 0.3, 0.1), max_life=1.6, vel_scale=4.5))
                
            self.save_high_score()
            self.state = STATE_GAME_OVER
            return

        self.snake.append(new_head.copy())

        # Proximity warning (1 block from wall)
        self.near_wall_warning = any((new_head <= 1) | (new_head >= GRID_SIZE - 2))

        # Check Food
        if (new_head == self.food).all():
            self.score += 1
            self.apples_eaten += 1
            self.sound_mgr.play('eat')
            
            # Burst of celebratory sparks
            for _ in range(35):
                color = random.choice([(1.0, 0.2, 0.3), (1.0, 0.8, 0.2), (0.2, 1.0, 0.6)])
                self.particles.append(Particle(self.food + 0.5, color, max_life=0.9, vel_scale=3.0))

            # High score update
            if self.score > self.high_score:
                self.high_score = self.score
                self.new_high_score_achieved = True

            # Level up check
            old_level = self.level
            for i, threshold in enumerate(LEVEL_THRESHOLDS):
                if self.score >= threshold:
                    self.level = i + 2
                    
            if self.level > old_level:
                self.sound_mgr.play('levelup')
                self.level_up_banner_timer = 2.5
                self.generate_obstacles()
                
            # Speed scaling
            current_speed = self.base_speed + (self.level - 1) * 0.75
            self.step_interval = 1.0 / current_speed

            self.spawn_food()
        else:
            self.snake.pop(0)
            if len(self.prev_snake) > len(self.snake):
                self.prev_snake.pop(0)

# =============================================================================
# RENDERING SYSTEM
# =============================================================================
def draw_cube_at(position, scale, texture_id, emissive_color=None):
    glPushMatrix()
    glTranslatef(*position)
    glScalef(*scale)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    
    if emissive_color:
        glMaterialfv(GL_FRONT, GL_EMISSION, [*emissive_color, 1.0])
    else:
        glMaterialfv(GL_FRONT, GL_EMISSION, [0.0, 0.0, 0.0, 1.0])
        
    glCallList(DL_CUBE)
    
    if emissive_color:
        glMaterialfv(GL_FRONT, GL_EMISSION, [0.0, 0.0, 0.0, 1.0])
        
    glPopMatrix()

def draw_snake_head_with_eyes(position, scale, direction):
    """Draws head cube with front-facing glowing visor eyes."""
    draw_cube_at(position, scale, textures["snake_head"], emissive_color=(0.0, 0.35, 0.3))
    
    # Glowing eyes on front face
    glDisable(GL_TEXTURE_2D)
    glPushMatrix()
    glTranslatef(*position)
    
    eye_offset = 0.51
    glBegin(GL_QUADS)
    glColor4f(0.2, 1.0, 0.9, 1.0) # Bright neon cyan eyes
    
    dx, dy, dz = direction
    if dx != 0:
        x = dx * eye_offset
        for sign in [-0.22, 0.22]:
            glVertex3f(x, sign - 0.08, -0.15)
            glVertex3f(x, sign + 0.08, -0.15)
            glVertex3f(x, sign + 0.08,  0.15)
            glVertex3f(x, sign - 0.08,  0.15)
    elif dy != 0:
        y = dy * eye_offset
        for sign in [-0.22, 0.22]:
            glVertex3f(sign - 0.08, y, -0.15)
            glVertex3f(sign + 0.08, y, -0.15)
            glVertex3f(sign + 0.08, y,  0.15)
            glVertex3f(sign - 0.08, y,  0.15)
    else: # dz != 0
        z = dz * eye_offset
        for sign in [-0.22, 0.22]:
            glVertex3f(sign - 0.12, -0.06, z)
            glVertex3f(sign + 0.12, -0.06, z)
            glVertex3f(sign + 0.12,  0.10, z)
            glVertex3f(sign - 0.12,  0.10, z)
    glEnd()
    
    glPopMatrix()
    glEnable(GL_TEXTURE_2D)

def draw_particles(game):
    if not game.particles:
        return
        
    glDisable(GL_TEXTURE_2D)
    glDisable(GL_LIGHTING)
    
    # Extract camera right & up vectors from ModelView matrix for billboard alignment
    m = glGetFloatv(GL_MODELVIEW_MATRIX)
    cam_r = np.array([m[0][0], m[1][0], m[2][0]])
    cam_u = np.array([m[0][1], m[1][1], m[2][1]])
    
    glBegin(GL_QUADS)
    for p in game.particles:
        alpha = max(0.0, min(1.0, p.life / p.max_life))
        glColor4f(p.color[0], p.color[1], p.color[2], alpha)
        s = p.size * alpha
        p1 = p.pos - cam_r * s - cam_u * s
        p2 = p.pos + cam_r * s - cam_u * s
        p3 = p.pos + cam_r * s + cam_u * s
        p4 = p.pos - cam_r * s + cam_u * s
        glVertex3fv(p1)
        glVertex3fv(p2)
        glVertex3fv(p3)
        glVertex3fv(p4)
    glEnd()
    
    glEnable(GL_LIGHTING)
    glEnable(GL_TEXTURE_2D)

def draw_spatial_depth_cues(game, head_pos):
    """3D Depth Guides: Floor Drop Shadows, Vertical Beacons, Wall Indicators."""
    glDisable(GL_TEXTURE_2D)
    glDisable(GL_LIGHTING)
    
    fx, fy, fz = game.food
    
    # 1. Food Floor Drop Shadow & Target Ring
    pulse = 0.75 + 0.25 * math.sin(game.game_time * 6.0)
    glLineWidth(2.5)
    glColor4f(1.0, 0.35, 0.2, 0.85 * pulse)
    
    # Concentric floor marker at y = ARENA_MIN + 0.02
    floor_y = ARENA_MIN + 0.02
    glBegin(GL_LINE_LOOP)
    for ang in range(0, 360, 20):
        rad = math.radians(ang)
        glVertex3f(fx + 0.45 * math.cos(rad), floor_y, fz + 0.45 * math.sin(rad))
    glEnd()
    
    # Crosshair on floor marker
    glBegin(GL_LINES)
    glVertex3f(fx - 0.5, floor_y, fz); glVertex3f(fx + 0.5, floor_y, fz)
    glVertex3f(fx, floor_y, fz - 0.5); glVertex3f(fx, floor_y, fz + 0.5)
    glEnd()
    
    # 2. Vertical Neon Beacon Beam connecting floor marker to floating food
    glLineWidth(1.8)
    glColor4f(1.0, 0.4, 0.25, 0.65 * pulse)
    glBegin(GL_LINES)
    glVertex3f(fx, floor_y, fz)
    glVertex3f(fx, fy, fz)
    glEnd()

    # 3. Side Wall Depth Projection Dots (Back & Left walls)
    glColor4f(1.0, 0.5, 0.2, 0.6)
    glPointSize(5.0)
    glBegin(GL_POINTS)
    glVertex3f(fx, fy, ARENA_MIN + 0.05) # Back wall
    glVertex3f(ARENA_MIN + 0.05, fy, fz) # Left wall
    glEnd()

    # 4. Snake Head Floor Drop Shadow
    hx, hy, hz = head_pos
    glColor4f(0.0, 0.0, 0.0, 0.45)
    glBegin(GL_QUADS)
    s = 0.42
    glVertex3f(hx - s, floor_y, hz - s)
    glVertex3f(hx + s, floor_y, hz - s)
    glVertex3f(hx + s, floor_y, hz + s)
    glVertex3f(hx - s, floor_y, hz + s)
    glEnd()
    
    # Faint head-to-floor drop line
    glLineWidth(1.0)
    glColor4f(0.0, 0.8, 0.9, 0.35)
    glBegin(GL_LINES)
    glVertex3f(hx, floor_y, hz)
    glVertex3f(hx, hy, hz)
    glEnd()

    # 5. Food Trajectory Guide Line (Toggleable with 'G')
    if game.show_guide_lines:
        glLineWidth(1.5)
        glColor4f(0.0, 1.0, 0.7, 0.45 + 0.2 * math.sin(game.game_time * 8.0))
        glBegin(GL_LINES)
        glVertex3fv(head_pos)
        glVertex3f(fx, fy, fz)
        glEnd()

    glEnable(GL_LIGHTING)
    glEnable(GL_TEXTURE_2D)

def render_3d_scene(game):
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()

    # Calculate smooth visual head position
    interp = min(1.0, game.step_timer / game.step_interval) if game.state == STATE_PLAYING else 1.0
    
    if len(game.prev_snake) == len(game.snake) and len(game.snake) > 0:
        head_vis = game.prev_snake[-1] * (1.0 - interp) + game.snake[-1] * interp
    elif len(game.snake) > 0:
        head_vis = game.snake[-1].astype(float)
    else:
        head_vis = np.array([ARENA_CENTER, ARENA_CENTER, ARENA_CENTER], dtype=float)

    # -------------------------------------------------------------------------
    # Camera Positioning
    # -------------------------------------------------------------------------
    if game.cam_mode == CAM_ORBIT or game.state == STATE_MENU:
        # Orbital camera with spherical coords
        rad_x = math.radians(game.cam_angle_x)
        rad_y = math.radians(game.cam_angle_y)
        cx = ARENA_CENTER + game.cam_distance * math.sin(rad_y) * math.cos(rad_x)
        cy = ARENA_CENTER + game.cam_distance * math.cos(rad_y)
        cz = ARENA_CENTER + game.cam_distance * math.sin(rad_y) * math.sin(rad_x)
        gluLookAt(cx, cy, cz, ARENA_CENTER, ARENA_CENTER, ARENA_CENTER, 0, 1, 0)
    elif game.cam_mode == CAM_CHASE and game.state == STATE_PLAYING:
        # Dynamic 3D Chase Camera following behind head
        target_cam = head_vis - game.direction * 7.5 + np.array([0.0, 2.8, 0.0])
        target_look = head_vis + game.direction * 3.5
        # Smooth interpolation
        game.chase_cam_pos += (target_cam - game.chase_cam_pos) * 0.18
        game.chase_look_pos += (target_look - game.chase_look_pos) * 0.25
        gluLookAt(*game.chase_cam_pos, *game.chase_look_pos, 0, 1, 0)
    else: # CAM_AUTO
        # Auto-tracks midpoint between snake head and food
        mid = (head_vis + game.food) * 0.5
        dist = max(32.0, np.linalg.norm(head_vis - game.food) * 1.8)
        rad_x = math.radians(game.cam_angle_x)
        cx = mid[0] + dist * 0.7 * math.cos(rad_x)
        cy = mid[1] + dist * 0.6
        cz = mid[2] + dist * 0.7 * math.sin(rad_x)
        gluLookAt(cx, cy, cz, mid[0], mid[1], mid[2], 0, 1, 0)

    # -------------------------------------------------------------------------
    # 3D Objects
    # -------------------------------------------------------------------------
    # 1. Floor Grid and Boundary Cage
    glCallList(DL_FLOOR_GRID)

    # 2. Food with floating bob and rotation animation
    bob_y = 0.12 * math.sin(game.game_time * 5.0)
    food_render_pos = np.array([game.food[0], game.food[1] + bob_y, game.food[2]])
    
    glPushMatrix()
    glTranslatef(*food_render_pos)
    glRotatef(game.game_time * 75.0, 0, 1, 0)
    glRotatef(game.game_time * 40.0, 1, 0, 1)
    pulse_scale = 0.9 + 0.1 * math.sin(game.game_time * 8.0)
    glScalef(pulse_scale, pulse_scale, pulse_scale)
    draw_cube_at((0, 0, 0), (1, 1, 1), textures["food"], emissive_color=(0.9, 0.35, 0.15))
    glPopMatrix()

    # 3. Obstacles
    for obs in game.obstacles:
        draw_cube_at(obs, (1, 1, 1), textures["obstacle"], emissive_color=(0.35, 0.12, 0.0))

    # 4. Snake Body & Head (Smooth 60 FPS Visual Interpolation)
    if game.snake:
        n_segs = len(game.snake)
        for i in range(n_segs - 1):
            if i < len(game.prev_snake):
                vis_pos = game.prev_snake[i] * (1.0 - interp) + game.snake[i] * interp
            else:
                vis_pos = game.snake[i].astype(float)
                
            # Subtle organic taper towards tail
            scale_factor = 0.82 + 0.18 * (i / max(1, n_segs - 1))
            draw_cube_at(vis_pos, (scale_factor, scale_factor, scale_factor), textures["snake_body"])

        # Head
        draw_snake_head_with_eyes(head_vis, (1.02, 1.02, 1.02), game.direction)

    # 5. Spatial Depth Cues (Shadows, Floor Ring, Neon Beacon Beam)
    draw_spatial_depth_cues(game, head_vis)

    # 6. Particles
    draw_particles(game)

# =============================================================================
# 2D HUD & OVERLAYS
# =============================================================================
def render_hud_overlay(game, fps_val):
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glDisable(GL_DEPTH_TEST)
    glDisable(GL_LIGHTING)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    # -------------------------------------------------------------------------
    # STATE: MENU SCREEN
    # -------------------------------------------------------------------------
    if game.state == STATE_MENU:
        # Title Card Panel
        cw, ch = 540, 360
        cx = (WINDOW_WIDTH - cw) // 2
        cy = (WINDOW_HEIGHT - ch) // 2
        draw_panel(cx, cy, cw, ch, bg_color=(12, 22, 38, 235), border_color=(0, 210, 255, 240))
        
        draw_text((cx + 145, cy + ch - 50), "SNAKE 3D", (0, 255, 220), size=36, bold=True)
        draw_text((cx + 175, cy + ch - 80), "CYBER GRID EDITION", (120, 180, 255), size=16, bold=True)
        
        # Difficulty Selector
        diff_name = DIFF_KEYS[game.selected_diff_idx]
        draw_text((cx + 60, cy + ch - 125), f"Difficulty:  < {diff_name} >  (Keys: LEFT / RIGHT)", (255, 230, 100), size=17)
        
        # Controls summary
        draw_text((cx + 60, cy + ch - 170), "CONTROLS & 3D STEERING:", (0, 210, 255), size=16, bold=True)
        draw_text((cx + 60, cy + ch - 195), "  WASD: Move Snake (Screen-Relative)", (220, 230, 240), size=15)
        draw_text((cx + 60, cy + ch - 220), "  SPACE / Q: Climb UP  |  SHIFT / E: Dive DOWN", (220, 230, 240), size=15)
        draw_text((cx + 60, cy + ch - 245), "  Mouse Drag / Arrows: Rotate 3D Camera", (220, 230, 240), size=15)
        draw_text((cx + 60, cy + ch - 270), "  C: Camera Mode  |  G: Food Guide  |  M: Mute", (220, 230, 240), size=15)
        
        # High Score & Prompt
        draw_text((cx + 190, cy + 55), f"All-Time High Score: {game.high_score}", (255, 215, 0), size=17, bold=True)
        pulse_col = int(180 + 75 * math.sin(game.game_time * 6.0))
        draw_text((cx + 115, cy + 20), "PRESS  [ENTER]  OR  [SPACE]  TO  START", (pulse_col, 255, pulse_col), size=18, bold=True)

    # -------------------------------------------------------------------------
    # STATE: IN-GAME HUD
    # -------------------------------------------------------------------------
    elif game.state in (STATE_PLAYING, STATE_PAUSED):
        # Top-Left Stats Panel
        draw_panel(15, WINDOW_HEIGHT - 85, 330, 70, bg_color=(10, 20, 36, 210), border_color=(40, 110, 190, 220))
        draw_text((25, WINDOW_HEIGHT - 40), f"SCORE: {game.score}", (0, 255, 200), size=20, bold=True)
        draw_text((180, WINDOW_HEIGHT - 40), f"HIGH: {game.high_score}", (255, 215, 80), size=18, bold=True)
        
        # Level Progress Bar
        next_threshold = LEVEL_THRESHOLDS[min(game.level - 1, len(LEVEL_THRESHOLDS) - 1)]
        prev_threshold = LEVEL_THRESHOLDS[game.level - 2] if game.level > 1 else 0
        lvl_frac = max(0.0, min(1.0, (game.score - prev_threshold) / max(1, next_threshold - prev_threshold)))
        draw_progress_bar(25, WINDOW_HEIGHT - 75, 180, 18, lvl_frac)
        draw_text((215, WINDOW_HEIGHT - 75), f"LVL {game.level}", (140, 220, 255), size=16, bold=True)

        # Top-Right 3D Spatial Radar & Camera Info
        draw_panel(WINDOW_WIDTH - 365, WINDOW_HEIGHT - 85, 350, 70, bg_color=(10, 20, 36, 210), border_color=(40, 110, 190, 220))
        cam_text = f"[C] Cam: {CAM_MODE_NAMES[game.cam_mode]}"
        draw_text((WINDOW_WIDTH - 355, WINDOW_HEIGHT - 40), cam_text, (255, 230, 100), size=16, bold=True)
        
        # Food coordinate distance vector
        if game.snake:
            head = game.snake[-1]
            dx, dy, dz = game.food - head
            dist = int(np.sum(np.abs(game.food - head)))
            hud_target = f"Food Δ: [{dx:+d}, {dy:+d}, {dz:+d}]  (Dist: {dist})"
            draw_text((WINDOW_WIDTH - 355, WINDOW_HEIGHT - 72), hud_target, (0, 240, 255), size=15)

        # Bottom Bar: Controls Cheat Sheet
        draw_panel(15, 12, WINDOW_WIDTH - 30, 34, bg_color=(10, 18, 30, 190), border_color=(35, 75, 130, 180))
        guide_status = "ON" if game.show_guide_lines else "OFF"
        mute_status = "MUTED" if not game.sound_mgr.enabled else "ON"
        cheat_sheet = (
            f"WASD: Steer  |  Space/Shift: Up/Down  |  Mouse Drag: Orbit  |  "
            f"[C] Cam  |  [G] Guide: {guide_status}  |  [P] Pause  |  [R] Reset Cam  |  [M] Sound: {mute_status}"
        )
        draw_text((25, 20), cheat_sheet, (190, 215, 240), size=14)

        # Level Up Celebration Banner
        if game.level_up_banner_timer > 0:
            bw, bh = 340, 60
            bx = (WINDOW_WIDTH - bw) // 2
            by = WINDOW_HEIGHT - 170
            draw_panel(bx, by, bw, bh, bg_color=(15, 40, 30, 240), border_color=(0, 255, 180, 255))
            draw_text((bx + 40, by + 18), f"★ LEVEL UP! LEVEL {game.level} ★", (0, 255, 200), size=22, bold=True)

        # Near Wall Hazard Indicator
        if game.near_wall_warning:
            draw_text((WINDOW_WIDTH // 2 - 80, WINDOW_HEIGHT - 110), "! WALL HAZARD !", (255, 70, 70), size=16, bold=True)

        # PAUSED Overlay
        if game.state == STATE_PAUSED:
            pw, ph = 360, 180
            px = (WINDOW_WIDTH - pw) // 2
            py = (WINDOW_HEIGHT - ph) // 2
            draw_panel(px, py, pw, ph, bg_color=(15, 22, 35, 245), border_color=(0, 200, 255, 255))
            draw_text((px + 105, py + ph - 55), "PAUSED", (0, 240, 255), size=32, bold=True)
            draw_text((px + 60, py + 75), "Press [P] or [SPACE] to Resume", (230, 240, 255), size=16)
            draw_text((px + 85, py + 40), "Press [M] for Main Menu", (255, 215, 100), size=16)

    # -------------------------------------------------------------------------
    # STATE: GAME OVER SCREEN
    # -------------------------------------------------------------------------
    elif game.state == STATE_GAME_OVER:
        gow, goh = 480, 310
        gox = (WINDOW_WIDTH - gow) // 2
        goy = (WINDOW_HEIGHT - goh) // 2
        draw_panel(gox, goy, gow, goh, bg_color=(20, 14, 25, 245), border_color=(255, 60, 80, 255))
        
        draw_text((gox + 130, goy + goh - 55), "GAME OVER", (255, 60, 80), size=36, bold=True)
        
        draw_text((gox + 90, goy + goh - 105), f"Final Score: {game.score}    (Level {game.level})", (240, 245, 255), size=20, bold=True)
        draw_text((gox + 90, goy + goh - 135), f"All-Time High Score: {game.high_score}", (255, 215, 80), size=17)
        draw_text((gox + 90, goy + goh - 165), f"Total Food Eaten: {game.apples_eaten}", (0, 230, 210), size=16)
        
        if game.new_high_score_achieved:
            draw_text((gox + 100, goy + goh - 200), "★ NEW HIGH SCORE! ★", (255, 225, 50), size=20, bold=True)
            
        draw_text((gox + 65, goy + 55), "Press [SPACE] or [ENTER] to Play Again", (0, 255, 180), size=17, bold=True)
        draw_text((gox + 130, goy + 20), "Press [M] for Main Menu  |  [ESC] Quit", (160, 180, 210), size=15)

    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()

# =============================================================================
# INPUT & EVENT PROCESSING
# =============================================================================
def process_events(game):
    for event in pygame.event.get():
        if event.type == QUIT:
            game.save_high_score()
            pygame.quit()
            sys.exit()

        # Mouse Drag Orbiting
        elif event.type == MOUSEBUTTONDOWN:
            if event.button in (1, 3): # Left or Right Click
                game.mouse_dragging = True
                game.last_mouse_pos = event.pos
            elif event.button == 4: # Scroll Up (Zoom In)
                game.cam_distance = max(18.0, game.cam_distance - 2.5)
            elif event.button == 5: # Scroll Down (Zoom Out)
                game.cam_distance = min(75.0, game.cam_distance + 2.5)

        elif event.type == MOUSEBUTTONUP:
            if event.button in (1, 3):
                game.mouse_dragging = False

        elif event.type == MOUSEMOTION:
            if game.mouse_dragging:
                dx = event.pos[0] - game.last_mouse_pos[0]
                dy = event.pos[1] - game.last_mouse_pos[1]
                game.cam_angle_x += dx * 0.4
                game.cam_angle_y = max(8.0, min(82.0, game.cam_angle_y - dy * 0.4))
                game.last_mouse_pos = event.pos

        # Keypress Events
        elif event.type == KEYDOWN:
            if event.key == K_ESCAPE:
                if game.state == STATE_PLAYING:
                    game.state = STATE_PAUSED
                    game.sound_mgr.play('pause')
                elif game.state in (STATE_PAUSED, STATE_GAME_OVER):
                    game.state = STATE_MENU
                else:
                    game.save_high_score()
                    pygame.quit()
                    sys.exit()

            # Menu navigation
            elif game.state == STATE_MENU:
                if event.key in (K_RETURN, K_SPACE):
                    game.reset_game()
                    game.state = STATE_PLAYING
                elif event.key == K_LEFT:
                    game.selected_diff_idx = (game.selected_diff_idx - 1) % len(DIFF_KEYS)
                elif event.key == K_RIGHT:
                    game.selected_diff_idx = (game.selected_diff_idx + 1) % len(DIFF_KEYS)

            # In-Game Controls
            elif game.state == STATE_PLAYING:
                # Pause Toggle
                if event.key == K_p:
                    game.state = STATE_PAUSED
                    game.sound_mgr.play('pause')
                # Camera Mode Toggle
                elif event.key == K_c:
                    game.cam_mode = (game.cam_mode + 1) % 3
                # Guide Line Toggle
                elif event.key == K_g:
                    game.show_guide_lines = not game.show_guide_lines
                # Sound Mute Toggle
                elif event.key == K_m:
                    game.sound_mgr.toggle_mute()
                # Camera Reset
                elif event.key == K_r:
                    game.cam_angle_x = 45.0
                    game.cam_angle_y = 35.0
                    game.cam_distance = 42.0

                # 3D Directional Steering (Seamless Camera-Relative)
                elif event.key == K_w:
                    d = game.get_camera_relative_dir('FORWARD')
                    if d is not None: game.enqueue_turn(d)
                elif event.key == K_s:
                    d = game.get_camera_relative_dir('BACKWARD')
                    if d is not None: game.enqueue_turn(d)
                elif event.key == K_a:
                    d = game.get_camera_relative_dir('LEFT')
                    if d is not None: game.enqueue_turn(d)
                elif event.key == K_d:
                    d = game.get_camera_relative_dir('RIGHT')
                    if d is not None: game.enqueue_turn(d)
                elif event.key in (K_SPACE, K_q):
                    game.enqueue_turn(DIR_UP)
                elif event.key in (K_LSHIFT, K_RSHIFT, K_e):
                    game.enqueue_turn(DIR_DOWN)

            # Paused Controls
            elif game.state == STATE_PAUSED:
                if event.key in (K_p, K_SPACE):
                    game.state = STATE_PLAYING
                elif event.key == K_m:
                    game.state = STATE_MENU

            # Game Over Controls
            elif game.state == STATE_GAME_OVER:
                if event.key in (K_SPACE, K_RETURN):
                    game.reset_game()
                    game.state = STATE_PLAYING
                elif event.key == K_m:
                    game.state = STATE_MENU

    # Keyboard camera rotation with arrow keys (smooth continuous)
    keys = pygame.key.get_pressed()
    rot_speed = 1.2
    if keys[K_LEFT]:  game.cam_angle_x -= rot_speed
    if keys[K_RIGHT]: game.cam_angle_x += rot_speed
    if keys[K_UP]:    game.cam_angle_y = max(8.0, game.cam_angle_y - rot_speed)
    if keys[K_DOWN]:  game.cam_angle_y = min(82.0, game.cam_angle_y + rot_speed)

# =============================================================================
# MAIN INITIALIZATION & GAME LOOP
# =============================================================================
def init_opengl():
    pygame.init()
    pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("Snake 3D - Cyber Grid Edition")
    
    glEnable(GL_DEPTH_TEST)
    glDepthFunc(GL_LEQUAL)
    
    # Lighting setup
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glLightfv(GL_LIGHT0, GL_POSITION, (25.0, 45.0, 35.0, 1.0))
    glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.9, 0.9, 1.0, 1.0))
    glLightfv(GL_LIGHT0, GL_AMBIENT, (0.28, 0.28, 0.35, 1.0))
    
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    glEnable(GL_TEXTURE_2D)
    
    # Transparency & Blending
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glShadeModel(GL_SMOOTH)

    glMatrixMode(GL_PROJECTION)
    gluPerspective(45.0, (WINDOW_WIDTH / WINDOW_HEIGHT), 0.1, 150.0)
    glMatrixMode(GL_MODELVIEW)
    
    load_gl_textures()
    compile_display_lists()

def main():
    init_opengl()
    game = Game3D()
    clock = pygame.time.Clock()
    fps_counter = 60

    while True:
        dt = clock.tick(TARGET_FPS) / 1000.0
        # Prevent huge dt spikes during window move/drag
        dt = min(dt, 0.05)
        fps_counter = int(clock.get_fps())

        process_events(game)

        # In menu, gently auto-orbit camera for preview
        if game.state == STATE_MENU and not game.mouse_dragging:
            game.cam_angle_x += 15.0 * dt

        if game.state == STATE_PLAYING:
            game.update_logic(dt)
        elif game.state == STATE_GAME_OVER:
            # Keep updating explosion particles after game over
            for p in game.particles[:]:
                p.update(dt)
                if p.life <= 0:
                    game.particles.remove(p)

        render_3d_scene(game)
        render_hud_overlay(game, fps_counter)
        pygame.display.flip()

if __name__ == "__main__":
    main()
