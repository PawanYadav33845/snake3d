/**
 * SNAKE 3D — CYBER GRID EDITION (WebGL / Three.js Engine)
 * Full 3D spatial simulation, camera-relative steering, depth cues, and leaderboard.
 */

// ============================================================================
// AUDIO SYNTHESIZER (Web Audio API)
// ============================================================================
class WebAudioSynth {
  constructor() {
    this.ctx = null;
    this.enabled = true;
  }

  init() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) this.ctx = new AudioCtx();
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
  }

  playTone(freq, duration, type = 'sine', decay = true) {
    if (!this.enabled || !this.ctx) return;
    try {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
      gain.gain.setValueAtTime(0.18, this.ctx.currentTime);
      if (decay) {
        gain.gain.exponentialRampToValueAtTime(0.0001, this.ctx.currentTime + duration);
      }
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + duration);
    } catch (e) {}
  }

  playEat() {
    if (!this.enabled || !this.ctx) return;
    this.playTone(659.25, 0.06, 'sine');
    setTimeout(() => this.playTone(987.77, 0.12, 'sine'), 50);
  }

  playTurn() {
    if (!this.enabled || !this.ctx) return;
    this.playTone(420, 0.02, 'triangle');
  }

  playLevelUp() {
    if (!this.enabled || !this.ctx) return;
    const notes = [523.25, 659.25, 783.99, 1046.50];
    notes.forEach((n, idx) => {
      setTimeout(() => this.playTone(n, 0.08, 'triangle'), idx * 70);
    });
  }

  playCrash() {
    if (!this.enabled || !this.ctx) return;
    try {
      // White noise buffer
      const bufferSize = this.ctx.sampleRate * 0.35;
      const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
      const data = buffer.getChannelData(0);
      for (let i = 0; i < bufferSize; i++) {
        data[i] = Math.random() * 2 - 1;
      }
      const noise = this.ctx.createBufferSource();
      noise.buffer = buffer;
      const filter = this.ctx.createBiquadFilter();
      filter.type = 'lowpass';
      filter.frequency.setValueAtTime(400, this.ctx.currentTime);
      filter.frequency.exponentialRampToValueAtTime(30, this.ctx.currentTime + 0.35);

      const gain = this.ctx.createGain();
      gain.gain.setValueAtTime(0.3, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.35);

      noise.connect(filter);
      filter.connect(gain);
      gain.connect(this.ctx.destination);
      noise.start();
    } catch (e) {}
  }
}

// ============================================================================
// GAME LOGIC & THREE.JS ENGINE
// ============================================================================
class Snake3DApp {
  constructor() {
    // Config
    this.gridSize = 32; // Default large area
    this.difficulty = 'Normal';
    this.baseSpeeds = { Casual: 4.5, Normal: 6.5, Fast: 9.5, Insane: 13.5 };
    this.playerName = localStorage.getItem('snake3d_player_name') || 'CyberSnake';
    this.highScore = parseInt(localStorage.getItem('snake3d_high_score')) || 0;

    // States: 'MENU', 'PLAYING', 'PAUSED', 'GAMEOVER'
    this.state = 'MENU';
    this.score = 0;
    this.level = 1;
    this.applesEaten = 0;
    this.showGuide = true;

    // Camera Modes: 'ORBIT', 'CHASE', 'AUTO'
    this.camMode = 'ORBIT';
    this.camAngleX = 45.0; // Azimuth deg
    this.camAngleY = 32.0; // Pitch deg
    this.camDistance = 64.0;
    this.isDragging = false;
    this.lastMouse = { x: 0, y: 0 };
    this.chaseCamPos = new THREE.Vector3();
    this.chaseLookPos = new THREE.Vector3();

    // Game Entities
    this.snake = []; // array of {x, y, z}
    this.prevSnake = [];
    this.direction = { x: 0, y: 0, z: 1 };
    this.inputQueue = [];
    this.food = { x: 5, y: 5, z: 5 };
    this.obstacles = [];
    this.particles = [];

    // Timing
    this.stepTimer = 0.0;
    this.stepInterval = 1.0 / this.baseSpeeds[this.difficulty];
    this.lastTime = performance.now();
    this.gameTime = 0.0;

    // Audio
    this.audio = new WebAudioSynth();

    // Setup Three.js and DOM
    this.initThree();
    this.initDOM();
    this.bindEvents();

    // Load initial leaderboard
    this.fetchLeaderboard('all');

    // Start Animation Loop
    requestAnimationFrame((t) => this.renderLoop(t));
  }

  // --------------------------------------------------------------------------
  // THREE.JS INITIALIZATION
  // --------------------------------------------------------------------------
  initThree() {
    const container = document.getElementById('canvas-container');
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x070b12);

    this.camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 300);
    this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(this.renderer.domElement);

    // Lighting
    const ambLight = new THREE.AmbientLight(0x3a4f66, 0.85);
    this.scene.add(ambLight);

    this.dirLight = new THREE.DirectionalLight(0xaad8ff, 1.2);
    this.dirLight.position.set(40, 60, 50);
    this.scene.add(this.dirLight);

    // Root Group for 3D Game World
    this.worldGroup = new THREE.Group();
    this.scene.add(this.worldGroup);

    // Materials
    this.initMaterials();
    this.rebuildArena();
  }

  initMaterials() {
    this.matSnakeHead = new THREE.MeshStandardMaterial({
      color: 0x00ffb7,
      emissive: 0x004d36,
      roughness: 0.25,
      metalness: 0.6
    });

    this.matSnakeBody = new THREE.MeshStandardMaterial({
      color: 0x00b4d8,
      emissive: 0x002444,
      roughness: 0.35,
      metalness: 0.45
    });

    this.matFood = new THREE.MeshStandardMaterial({
      color: 0xff0055,
      emissive: 0xff1a40,
      emissiveIntensity: 0.8,
      roughness: 0.2,
      metalness: 0.7
    });

    this.matObstacle = new THREE.MeshStandardMaterial({
      color: 0xff6600,
      emissive: 0x551100,
      roughness: 0.6,
      metalness: 0.3
    });

    this.cubeGeo = new THREE.BoxGeometry(0.96, 0.96, 0.96);
  }

  rebuildArena() {
    // Clear old arena elements
    if (this.arenaGroup) this.worldGroup.remove(this.arenaGroup);
    this.arenaGroup = new THREE.Group();
    this.worldGroup.add(this.arenaGroup);

    const minC = -0.5;
    const maxC = this.gridSize - 0.5;
    const center = (this.gridSize - 1) / 2.0;

    // Dynamic camera distance based on arena size
    this.camDistance = this.gridSize * 1.85;

    // 1. Floor Plane
    const floorGeo = new THREE.PlaneGeometry(this.gridSize, this.gridSize);
    const floorMat = new THREE.MeshBasicMaterial({
      color: 0x0a1424,
      transparent: true,
      opacity: 0.75,
      side: THREE.DoubleSide
    });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.rotation.x = Math.PI / 2;
    floor.position.set(center, minC, center);
    this.arenaGroup.add(floor);

    // 2. Floor Grid Lines
    const gridHelper = new THREE.GridHelper(this.gridSize, this.gridSize, 0x00f3ff, 0x1e3a5f);
    gridHelper.position.set(center, minC + 0.01, center);
    this.arenaGroup.add(gridHelper);

    // 3. 12 Outer Boundary Edge Rails (Glowing Cyan Wireframe Box)
    const boxGeo = new THREE.BoxGeometry(this.gridSize, this.gridSize, this.gridSize);
    const edges = new THREE.EdgesGeometry(boxGeo);
    const lineMat = new THREE.LineBasicMaterial({
      color: 0x00f3ff,
      linewidth: 2,
      transparent: true,
      opacity: 0.85
    });
    const boxWire = new THREE.LineSegments(edges, lineMat);
    boxWire.position.set(center, center, center);
    this.arenaGroup.add(boxWire);

    // 4. Food Floor Drop Target Ring
    const ringGeo = new THREE.RingGeometry(0.3, 0.5, 24);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0xff0055,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.8
    });
    this.foodFloorRing = new THREE.Mesh(ringGeo, ringMat);
    this.foodFloorRing.rotation.x = Math.PI / 2;
    this.arenaGroup.add(this.foodFloorRing);

    // 5. Food Vertical Beacon Beam
    const beamMat = new THREE.LineBasicMaterial({
      color: 0xff0055,
      transparent: true,
      opacity: 0.65
    });
    const beamGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, minC, 0),
      new THREE.Vector3(0, 0, 0)
    ]);
    this.foodBeacon = new THREE.Line(beamGeo, beamMat);
    this.arenaGroup.add(this.foodBeacon);

    // 6. Food Wall Projection Markers (Back & Left walls)
    const dotGeo = new THREE.SphereGeometry(0.25, 8, 8);
    const dotMat = new THREE.MeshBasicMaterial({ color: 0xffaa00 });
    this.foodBackWallDot = new THREE.Mesh(dotGeo, dotMat);
    this.foodLeftWallDot = new THREE.Mesh(dotGeo, dotMat);
    this.arenaGroup.add(this.foodBackWallDot);
    this.arenaGroup.add(this.foodLeftWallDot);

    // 7. Head Drop Shadow Marker
    const headShadowGeo = new THREE.CircleGeometry(0.45, 16);
    const headShadowMat = new THREE.MeshBasicMaterial({
      color: 0x000000,
      transparent: true,
      opacity: 0.55
    });
    this.headShadow = new THREE.Mesh(headShadowGeo, headShadowMat);
    this.headShadow.rotation.x = Math.PI / 2;
    this.arenaGroup.add(this.headShadow);

    // 8. Trajectory Guide Line
    const guideMat = new THREE.LineBasicMaterial({
      color: 0x00ffb7,
      transparent: true,
      opacity: 0.45
    });
    const guideGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(0, 0, 0)
    ]);
    this.guideLine = new THREE.Line(guideGeo, guideMat);
    this.arenaGroup.add(this.guideLine);

    // 9. Snake and Obstacle Mesh Groups
    if (this.snakeGroup) this.worldGroup.remove(this.snakeGroup);
    this.snakeGroup = new THREE.Group();
    this.worldGroup.add(this.snakeGroup);

    if (this.foodMesh) this.worldGroup.remove(this.foodMesh);
    this.foodMesh = new THREE.Mesh(this.cubeGeo, this.matFood);
    this.worldGroup.add(this.foodMesh);

    if (this.obsGroup) this.worldGroup.remove(this.obsGroup);
    this.obsGroup = new THREE.Group();
    this.worldGroup.add(this.obsGroup);
  }

  // --------------------------------------------------------------------------
  // DOM & UI BINDINGS
  // --------------------------------------------------------------------------
  initDOM() {
    document.getElementById('player-name-input').value = this.playerName;
    document.getElementById('go-player-name').value = this.playerName;
    document.getElementById('hud-player-name').innerText = this.playerName;
    document.getElementById('high-score-val').innerText = this.highScore;
    document.getElementById('hud-arena-size').innerText = `Arena: ${this.gridSize}³`;

    // Selector: Arena Size
    document.querySelectorAll('#arena-selector .choice-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#arena-selector .choice-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        this.gridSize = parseInt(btn.dataset.size);
        this.rebuildArena();
        document.getElementById('hud-arena-size').innerText = `Arena: ${this.gridSize}³`;
      });
    });

    // Selector: Difficulty
    document.querySelectorAll('#diff-selector .choice-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#diff-selector .choice-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        this.difficulty = btn.dataset.diff;
        this.stepInterval = 1.0 / this.baseSpeeds[this.difficulty];
      });
    });

    // Start Game Button
    document.getElementById('btn-start-game').addEventListener('click', () => {
      this.audio.init();
      const nameInput = document.getElementById('player-name-input').value.trim();
      this.playerName = nameInput || 'CyberSnake';
      localStorage.setItem('snake3d_player_name', this.playerName);
      document.getElementById('hud-player-name').innerText = this.playerName;
      document.getElementById('go-player-name').value = this.playerName;
      this.startNewGame();
    });

    // Leaderboard Open / Close
    document.getElementById('btn-open-leaderboard').addEventListener('click', () => {
      this.fetchLeaderboard('all');
      document.getElementById('leaderboard-modal').classList.remove('hidden');
    });

    document.getElementById('btn-view-leaderboard-go').addEventListener('click', () => {
      this.fetchLeaderboard('all');
      document.getElementById('leaderboard-modal').classList.remove('hidden');
    });

    document.getElementById('btn-close-leaderboard').addEventListener('click', () => {
      document.getElementById('leaderboard-modal').classList.add('hidden');
    });

    // Filter Buttons in Leaderboard
    document.querySelectorAll('.leaderboard-filters .filter-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.leaderboard-filters .filter-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        this.fetchLeaderboard(btn.dataset.grid);
      });
    });

    // Resume / Pause Buttons
    document.getElementById('btn-resume').addEventListener('click', () => this.togglePause());
    document.getElementById('btn-pause-toggle').addEventListener('click', () => this.togglePause());
    document.getElementById('btn-pause-menu').addEventListener('click', () => this.showMenu());

    // Play Again Button
    document.getElementById('btn-play-again').addEventListener('click', () => {
      document.getElementById('gameover-modal').classList.add('hidden');
      this.startNewGame();
    });

    document.getElementById('btn-go-menu').addEventListener('click', () => {
      document.getElementById('gameover-modal').classList.add('hidden');
      this.showMenu();
    });

    // Save Score to Server
    document.getElementById('btn-submit-score').addEventListener('click', () => this.submitScore());

    // Sound Toggle Button
    document.getElementById('btn-sound-toggle').addEventListener('click', () => {
      this.audio.enabled = !this.audio.enabled;
      document.getElementById('btn-sound-toggle').innerText = this.audio.enabled ? '🔊' : '🔇';
    });

    // Touch Controls
    const addTouch = (id, action) => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('touchstart', (e) => {
          e.preventDefault();
          this.handleActionInput(action);
        });
        el.addEventListener('click', () => this.handleActionInput(action));
      }
    };
    addTouch('tbtn-fwd', 'FORWARD');
    addTouch('tbtn-back', 'BACKWARD');
    addTouch('tbtn-left', 'LEFT');
    addTouch('tbtn-right', 'RIGHT');
    addTouch('tbtn-up', 'UP');
    addTouch('tbtn-down', 'DOWN');
  }

  // --------------------------------------------------------------------------
  // INPUT & EVENT BINDINGS
  // --------------------------------------------------------------------------
  bindEvents() {
    window.addEventListener('resize', () => {
      this.camera.aspect = window.innerWidth / window.innerHeight;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(window.innerWidth, window.innerHeight);
    });

    // Keyboard controls
    window.addEventListener('keydown', (e) => {
      this.audio.init();

      // In Game Over or Menu
      if (this.state === 'GAMEOVER') {
        if (e.code === 'Space' || e.code === 'Enter') {
          document.getElementById('gameover-modal').classList.add('hidden');
          this.startNewGame();
        }
        return;
      }

      if (this.state === 'MENU') {
        if (e.code === 'Space' || e.code === 'Enter') {
          document.getElementById('btn-start-game').click();
        }
        return;
      }

      // Playing or Paused
      if (e.code === 'KeyP') {
        this.togglePause();
        return;
      }

      if (this.state === 'PAUSED') {
        if (e.code === 'Space') this.togglePause();
        return;
      }

      // Camera Mode Toggle
      if (e.code === 'KeyC') {
        const modes = ['ORBIT', 'CHASE', 'AUTO'];
        const nextIdx = (modes.indexOf(this.camMode) + 1) % modes.length;
        this.camMode = modes[nextIdx];
        document.getElementById('hud-cam-mode').innerText = `Cam: ${this.camMode}`;
        return;
      }

      // Target Guide Line Toggle
      if (e.code === 'KeyG') {
        this.showGuide = !this.showGuide;
        document.getElementById('guide-status').innerText = this.showGuide ? 'ON' : 'OFF';
        return;
      }

      // Reset Camera
      if (e.code === 'KeyR') {
        this.camAngleX = 45.0;
        this.camAngleY = 32.0;
        this.camDistance = this.gridSize * 1.85;
        return;
      }

      // Sound Mute
      if (e.code === 'KeyM') {
        document.getElementById('btn-sound-toggle').click();
        return;
      }

      // Movement Keys (WASD + Space/Shift)
      switch (e.code) {
        case 'KeyW': this.handleActionInput('FORWARD'); break;
        case 'KeyS': this.handleActionInput('BACKWARD'); break;
        case 'KeyA': this.handleActionInput('LEFT'); break;
        case 'KeyD': this.handleActionInput('RIGHT'); break;
        case 'Space':
        case 'KeyQ': this.handleActionInput('UP'); break;
        case 'ShiftLeft':
        case 'ShiftRight':
        case 'KeyE': this.handleActionInput('DOWN'); break;
      }
    });

    // Mouse Orbit Controls
    const container = document.getElementById('canvas-container');
    container.addEventListener('mousedown', (e) => {
      this.isDragging = true;
      this.lastMouse = { x: e.clientX, y: e.clientY };
    });

    window.addEventListener('mouseup', () => {
      this.isDragging = false;
    });

    window.addEventListener('mousemove', (e) => {
      if (this.isDragging) {
        const dx = e.clientX - this.lastMouse.x;
        const dy = e.clientY - this.lastMouse.y;
        this.camAngleX += dx * 0.4;
        this.camAngleY = Math.max(8.0, Math.min(84.0, this.camAngleY - dy * 0.4));
        this.lastMouse = { x: e.clientX, y: e.clientY };
      }
    });

    // Zoom via Scroll Wheel
    window.addEventListener('wheel', (e) => {
      const zoomSpeed = this.gridSize * 0.08;
      if (e.deltaY < 0) {
        this.camDistance = Math.max(this.gridSize * 0.6, this.camDistance - zoomSpeed);
      } else {
        this.camDistance = Math.min(this.gridSize * 3.5, this.camDistance + zoomSpeed);
      }
    });
  }

  // --------------------------------------------------------------------------
  // CAMERA-RELATIVE DIRECTION LOGIC
  // --------------------------------------------------------------------------
  handleActionInput(action) {
    if (this.state !== 'PLAYING') return;

    // Up and Down are absolute vertical
    if (action === 'UP') {
      this.enqueueDirection({ x: 0, y: 1, z: 0 });
      return;
    }
    if (action === 'DOWN') {
      this.enqueueDirection({ x: 0, y: -1, z: 0 });
      return;
    }

    // Camera Horizontal Azimuth
    const rad = (this.camAngleX * Math.PI) / 180.0;
    const fx = -Math.cos(rad);
    const fz = -Math.sin(rad);
    const rx = -fz;
    const rz = fx;

    const cardinals = [
      { x: 1, y: 0, z: 0 },
      { x: -1, y: 0, z: 0 },
      { x: 0, y: 0, z: 1 },
      { x: 0, y: 0, z: -1 }
    ];

    let target = { x: 0, y: 0, z: 0 };
    if (action === 'FORWARD') target = { x: fx, y: 0, z: fz };
    else if (action === 'BACKWARD') target = { x: -fx, y: 0, z: -fz };
    else if (action === 'RIGHT') target = { x: rx, y: 0, z: rz };
    else if (action === 'LEFT') target = { x: -rx, y: 0, z: -rz };

    let bestDir = cardinals[0];
    let maxDot = -Infinity;
    cardinals.forEach((c) => {
      const dot = target.x * c.x + target.z * c.z;
      if (dot > maxDot) {
        maxDot = dot;
        bestDir = c;
      }
    });

    this.enqueueDirection(bestDir);
  }

  enqueueDirection(newDir) {
    const refDir = this.inputQueue.length > 0 ? this.inputQueue[this.inputQueue.length - 1] : this.direction;

    // Reject identical or 180-degree suicide
    if (newDir.x === refDir.x && newDir.y === refDir.y && newDir.z === refDir.z) return;
    if (newDir.x === -refDir.x && newDir.y === -refDir.y && newDir.z === -refDir.z) return;

    if (this.inputQueue.length < 3) {
      this.inputQueue.push(newDir);
      this.audio.playTurn();
    }
  }

  // --------------------------------------------------------------------------
  // GAME STATES
  // --------------------------------------------------------------------------
  startNewGame() {
    this.score = 0;
    this.level = 1;
    this.applesEaten = 0;
    this.state = 'PLAYING';
    this.inputQueue = [];

    document.getElementById('menu-modal').classList.add('hidden');
    document.getElementById('gameover-modal').classList.add('hidden');
    document.getElementById('hud').classList.remove('hidden');
    document.getElementById('score-val').innerText = '0';
    document.getElementById('level-val').innerText = '1';
    document.getElementById('level-progress-bar').style.width = '0%';

    // Snake starts in the center of the large arena
    const mid = Math.floor(this.gridSize / 2);
    this.snake = [
      { x: mid, y: mid, z: mid - 2 },
      { x: mid, y: mid, z: mid - 1 },
      { x: mid, y: mid, z: mid }
    ];
    this.prevSnake = JSON.parse(JSON.stringify(this.snake));
    this.direction = { x: 0, y: 0, z: 1 };

    this.stepTimer = 0.0;
    this.stepInterval = 1.0 / this.baseSpeeds[this.difficulty];

    this.spawnFood();
    this.generateObstacles();

    // Reset chase camera
    this.chaseCamPos.set(mid, mid + 3, mid - 8);
    this.chaseLookPos.set(mid, mid, mid + 3);
  }

  togglePause() {
    if (this.state === 'PLAYING') {
      this.state = 'PAUSED';
      document.getElementById('pause-modal').classList.remove('hidden');
    } else if (this.state === 'PAUSED') {
      this.state = 'PLAYING';
      document.getElementById('pause-modal').classList.add('hidden');
    }
  }

  showMenu() {
    this.state = 'MENU';
    document.getElementById('hud').classList.add('hidden');
    document.getElementById('pause-modal').classList.add('hidden');
    document.getElementById('gameover-modal').classList.add('hidden');
    document.getElementById('menu-modal').classList.remove('hidden');
  }

  generateObstacles() {
    // Clear old meshes
    while (this.obsGroup.children.length > 0) {
      this.obsGroup.remove(this.obsGroup.children[0]);
    }
    this.obstacles = [];

    // Scale obstacles with arena volume and level
    const count = this.level === 1 ? 0 : Math.floor((this.level - 1) * (this.gridSize / 6));
    const head = this.snake[this.snake.length - 1];

    for (let i = 0; i < count; i++) {
      let attempts = 0;
      while (attempts++ < 300) {
        const obs = {
          x: Math.floor(Math.random() * (this.gridSize - 2)) + 1,
          y: Math.floor(Math.random() * (this.gridSize - 2)) + 1,
          z: Math.floor(Math.random() * (this.gridSize - 2)) + 1
        };

        // Keep 4-block buffer away from snake head
        const dist = Math.abs(obs.x - head.x) + Math.abs(obs.y - head.y) + Math.abs(obs.z - head.z);
        if (dist <= 4) continue;
        if (this.snake.some((s) => s.x === obs.x && s.y === obs.y && s.z === obs.z)) continue;
        if (this.food.x === obs.x && this.food.y === obs.y && this.food.z === obs.z) continue;
        if (this.obstacles.some((o) => o.x === obs.x && o.y === obs.y && o.z === obs.z)) continue;

        this.obstacles.push(obs);
        const m = new THREE.Mesh(this.cubeGeo, this.matObstacle);
        m.position.set(obs.x, obs.y, obs.z);
        this.obsGroup.add(m);
        break;
      }
    }
  }

  spawnFood() {
    while (true) {
      const pos = {
        x: Math.floor(Math.random() * (this.gridSize - 2)) + 1,
        y: Math.floor(Math.random() * (this.gridSize - 2)) + 1,
        z: Math.floor(Math.random() * (this.gridSize - 2)) + 1
      };
      if (this.snake.some((s) => s.x === pos.x && s.y === pos.y && s.z === pos.z)) continue;
      if (this.obstacles.some((o) => o.x === pos.x && o.y === pos.y && o.z === pos.z)) continue;
      this.food = pos;
      break;
    }
  }

  // --------------------------------------------------------------------------
  // GAME STEP LOGIC
  // --------------------------------------------------------------------------
  stepGame() {
    if (this.inputQueue.length > 0) {
      this.direction = this.inputQueue.shift();
    }

    this.prevSnake = JSON.parse(JSON.stringify(this.snake));
    const head = this.snake[this.snake.length - 1];
    const newHead = {
      x: head.x + this.direction.x,
      y: head.y + this.direction.y,
      z: head.z + this.direction.z
    };

    // Boundary check
    const hitWall =
      newHead.x < 0 || newHead.x >= this.gridSize ||
      newHead.y < 0 || newHead.y >= this.gridSize ||
      newHead.z < 0 || newHead.z >= this.gridSize;

    // Self check
    const hitSelf = this.snake.slice(0, -1).some((s) => s.x === newHead.x && s.y === newHead.y && s.z === newHead.z);

    // Obstacle check
    const hitObs = this.obstacles.some((o) => o.x === newHead.x && o.y === newHead.y && o.z === newHead.z);

    if (hitWall || hitSelf || hitObs) {
      this.gameOver();
      return;
    }

    this.snake.push(newHead);

    // Near-wall hazard indicator
    const nearWall =
      newHead.x <= 1 || newHead.x >= this.gridSize - 2 ||
      newHead.y <= 1 || newHead.y >= this.gridSize - 2 ||
      newHead.z <= 1 || newHead.z >= this.gridSize - 2;
    document.getElementById('wall-warning').classList.toggle('hidden', !nearWall);

    // Food check
    if (newHead.x === this.food.x && newHead.y === this.food.y && newHead.z === this.food.z) {
      this.score += 1;
      this.applesEaten += 1;
      this.audio.playEat();

      // Spawn burst of particles
      this.spawnParticles(this.food, 35, 0xff0055);

      if (this.score > this.highScore) {
        this.highScore = this.score;
        localStorage.setItem('snake3d_high_score', this.highScore);
        document.getElementById('high-score-val').innerText = this.highScore;
      }

      // Level progression thresholds: [5, 12, 22, 35, 50]
      const thresholds = [5, 12, 22, 35, 50];
      const oldLevel = this.level;
      for (let i = 0; i < thresholds.length; i++) {
        if (this.score >= thresholds[i]) this.level = i + 2;
      }

      if (this.level > oldLevel) {
        this.audio.playLevelUp();
        this.showLevelBanner(this.level);
        this.generateObstacles();
      }

      // Update UI
      document.getElementById('score-val').innerText = this.score;
      document.getElementById('level-val').innerText = this.level;

      const prevT = this.level > 1 ? thresholds[this.level - 2] : 0;
      const nextT = thresholds[Math.min(this.level - 1, thresholds.length - 1)];
      const frac = Math.min(1.0, (this.score - prevT) / Math.max(1, nextT - prevT));
      document.getElementById('level-progress-bar').style.width = `${Math.floor(frac * 100)}%`;

      // Speed up slightly
      const currentSpeed = this.baseSpeeds[this.difficulty] + (this.level - 1) * 0.7;
      this.stepInterval = 1.0 / currentSpeed;

      this.spawnFood();
    } else {
      this.snake.shift();
      if (this.prevSnake.length > this.snake.length) this.prevSnake.shift();
    }
  }

  showLevelBanner(lvl) {
    const banner = document.getElementById('level-up-banner');
    document.getElementById('banner-level-num').innerText = lvl;
    banner.classList.remove('hidden');
    setTimeout(() => banner.classList.add('hidden'), 2500);
  }

  gameOver() {
    this.state = 'GAMEOVER';
    this.audio.playCrash();
    this.spawnParticles(this.snake[this.snake.length - 1], 60, 0x00f3ff);

    document.getElementById('go-score').innerText = this.score;
    document.getElementById('go-level').innerText = this.level;
    document.getElementById('go-food').innerText = this.applesEaten;
    document.getElementById('go-high').innerText = this.highScore;
    document.getElementById('save-status-msg').innerText = '';
    document.getElementById('gameover-modal').classList.remove('hidden');

    // Auto-prompt to submit score
    this.submitScore(false);
  }

  // --------------------------------------------------------------------------
  // LEADERBOARD & SERVER SYNC
  // --------------------------------------------------------------------------
  async fetchLeaderboard(gridFilter = 'all') {
    const tbody = document.getElementById('leaderboard-body');
    tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">Loading pilot records...</td></tr>';

    try {
      let url = '/api/leaderboard?limit=25';
      if (gridFilter !== 'all') {
        url += `&grid_size=${gridFilter}`;
      }
      const res = await fetch(url);
      const data = await res.json();

      if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading-cell">No pilot scores yet. Be the first!</td></tr>';
        return;
      }

      let html = '';
      data.forEach((entry, idx) => {
        const rank = idx + 1;
        let rankClass = '';
        let medal = `#${rank}`;
        if (rank === 1) { medal = '🥇 #1'; rankClass = 'rank-gold'; }
        else if (rank === 2) { medal = '🥈 #2'; rankClass = 'rank-silver'; }
        else if (rank === 3) { medal = '🥉 #3'; rankClass = 'rank-bronze'; }

        const isMe = entry.player_name.toLowerCase() === this.playerName.toLowerCase();
        const dateStr = entry.created_at ? entry.created_at.split(' ')[0] : 'Today';

        html += `
          <tr class="${isMe ? 'pilot-highlight' : ''}">
            <td class="${rankClass}">${medal}</td>
            <td><b>${this.escapeHtml(entry.player_name)}</b></td>
            <td class="neon-cyan"><b>${entry.score}</b></td>
            <td>Lvl ${entry.level}</td>
            <td>${entry.grid_size}³</td>
            <td>${entry.difficulty}</td>
            <td style="color: #64748b;">${dateStr}</td>
          </tr>
        `;
      });
      tbody.innerHTML = html;
    } catch (e) {
      tbody.innerHTML = '<tr><td colspan="7" class="loading-cell" style="color: #ff0055;">Failed to reach server leaderboard.</td></tr>';
    }
  }

  async submitScore(manual = true) {
    const nameInput = document.getElementById('go-player-name').value.trim();
    const finalName = nameInput || this.playerName || 'CyberSnake';
    this.playerName = finalName;
    localStorage.setItem('snake3d_player_name', this.playerName);

    const statusEl = document.getElementById('save-status-msg');
    statusEl.className = 'status-msg';
    statusEl.innerText = 'Transmitting score to cyber mainframe...';

    try {
      const res = await fetch('/api/score', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          player_name: finalName,
          score: this.score,
          level: this.level,
          grid_size: this.gridSize,
          difficulty: this.difficulty
        })
      });
      const data = await res.json();
      if (res.ok) {
        statusEl.className = 'status-msg success';
        statusEl.innerText = `✓ Score confirmed! Ranked on global leaderboard.`;
        this.fetchLeaderboard('all');
      } else {
        statusEl.className = 'status-msg error';
        statusEl.innerText = data.detail || 'Could not record score.';
      }
    } catch (e) {
      statusEl.className = 'status-msg error';
      statusEl.innerText = 'Offline or server unreachable.';
    }
  }

  escapeHtml(str) {
    return str.replace(/[&<>"']/g, (m) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[m]));
  }

  // --------------------------------------------------------------------------
  // PARTICLES
  // --------------------------------------------------------------------------
  spawnParticles(pos, count = 25, colorHex = 0x00f3ff) {
    const pGeo = new THREE.BufferGeometry();
    const positions = new Float32Array(count * 3);
    const velocities = [];

    for (let i = 0; i < count; i++) {
      positions[i * 3] = pos.x;
      positions[i * 3 + 1] = pos.y;
      positions[i * 3 + 2] = pos.z;

      const theta = Math.random() * Math.PI * 2;
      const phi = Math.random() * Math.PI;
      const spd = 2.0 + Math.random() * 4.5;
      velocities.push(
        spd * Math.sin(phi) * Math.cos(theta),
        spd * Math.cos(phi),
        spd * Math.sin(phi) * Math.sin(theta)
      );
    }
    pGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const pMat = new THREE.PointsMaterial({
      color: colorHex,
      size: 0.35,
      transparent: true,
      opacity: 1.0
    });

    const points = new THREE.Points(pGeo, pMat);
    this.worldGroup.add(points);

    this.particles.push({
      mesh: points,
      geo: pGeo,
      velocities: velocities,
      life: 0.8,
      maxLife: 0.8
    });
  }

  // --------------------------------------------------------------------------
  // RENDER & ANIMATION LOOP
  // --------------------------------------------------------------------------
  renderLoop(time) {
    requestAnimationFrame((t) => this.renderLoop(t));

    const dt = Math.min((time - this.lastTime) / 1000.0, 0.05);
    this.lastTime = time;
    this.gameTime += dt;

    // Update Particles
    for (let i = this.particles.length - 1; i >= 0; i--) {
      const p = this.particles[i];
      p.life -= dt;
      if (p.life <= 0) {
        this.worldGroup.remove(p.mesh);
        p.geo.dispose();
        p.mesh.material.dispose();
        this.particles.splice(i, 1);
        continue;
      }
      const posArr = p.geo.attributes.position.array;
      for (let j = 0; j < p.velocities.length / 3; j++) {
        posArr[j * 3] += p.velocities[j * 3] * dt;
        posArr[j * 3 + 1] += p.velocities[j * 3 + 1] * dt;
        posArr[j * 3 + 2] += p.velocities[j * 3 + 2] * dt;
      }
      p.geo.attributes.position.needsUpdate = true;
      p.mesh.material.opacity = p.life / p.maxLife;
    }

    // Auto-orbit in Menu
    if (this.state === 'MENU' && !this.isDragging) {
      this.camAngleX += 12.0 * dt;
    }

    // Game Step Accumulator
    if (this.state === 'PLAYING') {
      this.stepTimer += dt;
      if (this.stepTimer >= this.stepInterval) {
        this.stepTimer -= this.stepInterval;
        this.stepGame();
      }
    }

    // Sub-cell Visual Interpolation factor
    const interp = this.state === 'PLAYING' ? Math.min(1.0, this.stepTimer / this.stepInterval) : 1.0;

    // 1. Update Snake Meshes
    if (this.snake.length > 0) {
      while (this.snakeGroup.children.length < this.snake.length) {
        const isHead = this.snakeGroup.children.length === this.snake.length - 1;
        const mesh = new THREE.Mesh(this.cubeGeo, isHead ? this.matSnakeHead : this.matSnakeBody);
        this.snakeGroup.add(mesh);
      }
      while (this.snakeGroup.children.length > this.snake.length) {
        this.snakeGroup.remove(this.snakeGroup.children[this.snakeGroup.children.length - 1]);
      }

      for (let i = 0; i < this.snake.length; i++) {
        const mesh = this.snakeGroup.children[i];
        const isHead = i === this.snake.length - 1;
        mesh.material = isHead ? this.matSnakeHead : this.matSnakeBody;

        let curX = this.snake[i].x;
        let curY = this.snake[i].y;
        let curZ = this.snake[i].z;

        if (i < this.prevSnake.length) {
          curX = this.prevSnake[i].x * (1 - interp) + this.snake[i].x * interp;
          curY = this.prevSnake[i].y * (1 - interp) + this.snake[i].y * interp;
          curZ = this.prevSnake[i].z * (1 - interp) + this.snake[i].z * interp;
        }

        mesh.position.set(curX, curY, curZ);
        const scale = isHead ? 1.02 : 0.85 + 0.15 * (i / Math.max(1, this.snake.length - 1));
        mesh.scale.set(scale, scale, scale);
      }
    }

    // 2. Food Animation (Bob + Rotate)
    const bob = Math.sin(this.gameTime * 5.0) * 0.15;
    this.foodMesh.position.set(this.food.x, this.food.y + bob, this.food.z);
    this.foodMesh.rotation.y += 1.5 * dt;
    this.foodMesh.rotation.x += 0.8 * dt;

    // 3. 3D Spatial Cues (Floor Target, Beacon, Shadows)
    const minC = -0.5;
    this.foodFloorRing.position.set(this.food.x, minC + 0.02, this.food.z);
    const pulse = 0.85 + Math.sin(this.gameTime * 7.0) * 0.25;
    this.foodFloorRing.scale.set(pulse, pulse, pulse);

    // Update Beacon
    const beamPositions = this.foodBeacon.geometry.attributes.position.array;
    beamPositions[0] = this.food.x;
    beamPositions[1] = minC;
    beamPositions[2] = this.food.z;
    beamPositions[3] = this.food.x;
    beamPositions[4] = this.food.y;
    beamPositions[5] = this.food.z;
    this.foodBeacon.geometry.attributes.position.needsUpdate = true;

    // Wall Projection Dots
    this.foodBackWallDot.position.set(this.food.x, this.food.y, minC + 0.05);
    this.foodLeftWallDot.position.set(minC + 0.05, this.food.y, this.food.z);

    // Snake Head Shadow
    if (this.snake.length > 0) {
      const headMesh = this.snakeGroup.children[this.snake.length - 1];
      if (headMesh) {
        this.headShadow.position.set(headMesh.position.x, minC + 0.02, headMesh.position.z);

        // Guide Line
        if (this.showGuide) {
          this.guideLine.visible = true;
          const gPositions = this.guideLine.geometry.attributes.position.array;
          gPositions[0] = headMesh.position.x;
          gPositions[1] = headMesh.position.y;
          gPositions[2] = headMesh.position.z;
          gPositions[3] = this.food.x;
          gPositions[4] = this.food.y;
          gPositions[5] = this.food.z;
          this.guideLine.geometry.attributes.position.needsUpdate = true;
        } else {
          this.guideLine.visible = false;
        }

        // Target Info HUD
        const dx = this.food.x - this.snake[this.snake.length - 1].x;
        const dy = this.food.y - this.snake[this.snake.length - 1].y;
        const dz = this.food.z - this.snake[this.snake.length - 1].z;
        const dist = Math.abs(dx) + Math.abs(dy) + Math.abs(dz);
        document.getElementById('hud-target-info').innerText =
          `Food Δ: [${dx >= 0 ? '+' : ''}${dx}, ${dy >= 0 ? '+' : ''}${dy}, ${dz >= 0 ? '+' : ''}${dz}] (Dist: ${dist})`;
      }
    }

    // 4. Camera Control Modes
    const center = (this.gridSize - 1) / 2.0;

    if (this.camMode === 'ORBIT' || this.state === 'MENU') {
      const radX = (this.camAngleX * Math.PI) / 180.0;
      const radY = (this.camAngleY * Math.PI) / 180.0;
      const cx = center + this.camDistance * Math.sin(radY) * Math.cos(radX);
      const cy = center + this.camDistance * Math.cos(radY);
      const cz = center + this.camDistance * Math.sin(radY) * Math.sin(radX);
      this.camera.position.set(cx, cy, cz);
      this.camera.lookAt(center, center, center);
    } else if (this.camMode === 'CHASE' && this.snake.length > 0) {
      const headMesh = this.snakeGroup.children[this.snake.length - 1];
      const targetCam = headMesh.position.clone()
        .sub(new THREE.Vector3(this.direction.x, this.direction.y, this.direction.z).multiplyScalar(8.5))
        .add(new THREE.Vector3(0, 3.2, 0));
      const targetLook = headMesh.position.clone()
        .add(new THREE.Vector3(this.direction.x, this.direction.y, this.direction.z).multiplyScalar(4.0));

      this.chaseCamPos.lerp(targetCam, 0.15);
      this.chaseLookPos.lerp(targetLook, 0.22);
      this.camera.position.copy(this.chaseCamPos);
      this.camera.lookAt(this.chaseLookPos);
    } else {
      // AUTO TRACK
      const head = this.snake[this.snake.length - 1] || { x: center, y: center, z: center };
      const mid = new THREE.Vector3((head.x + this.food.x) / 2, (head.y + this.food.y) / 2, (head.z + this.food.z) / 2);
      const dist = Math.max(30.0, new THREE.Vector3(head.x, head.y, head.z).distanceTo(new THREE.Vector3(this.food.x, this.food.y, this.food.z)) * 1.8);
      const radX = (this.camAngleX * Math.PI) / 180.0;
      this.camera.position.set(
        mid.x + dist * 0.7 * Math.cos(radX),
        mid.y + dist * 0.6,
        mid.z + dist * 0.7 * Math.sin(radX)
      );
      this.camera.lookAt(mid);
    }

    this.renderer.render(this.scene, this.camera);
  }
}

// Start application when page is ready
window.addEventListener('DOMContentLoaded', () => {
  window.app = new Snake3DApp();
});
