/* ═══════════════════════════════════════════
   CARESTANCE AI — Futuristic Landing JS
   Three.js Neural Net + GSAP ScrollTrigger
   ═══════════════════════════════════════════ */

// ── Three.js Neural Particle System ──
function initHeroCanvas() {
  const canvas = document.getElementById('hero-canvas');
  if (!canvas || typeof THREE === 'undefined') return;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  // Particles
  const count = window.innerWidth < 768 ? 800 : 2000;
  const geo = new THREE.BufferGeometry();
  const pos = new Float32Array(count * 3);
  const cols = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    pos[i * 3] = (Math.random() - 0.5) * 20;
    pos[i * 3 + 1] = (Math.random() - 0.5) * 20;
    pos[i * 3 + 2] = (Math.random() - 0.5) * 20;
    // Cyan to purple gradient
    const t = Math.random();
    cols[i * 3] = t * 0.48;       // R
    cols[i * 3 + 1] = 0.5 + t * 0.33; // G
    cols[i * 3 + 2] = 1.0;         // B
  }
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(cols, 3));

  const mat = new THREE.PointsMaterial({
    size: 0.035,
    vertexColors: true,
    transparent: true,
    opacity: 0.7,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });
  const points = new THREE.Points(geo, mat);
  scene.add(points);

  // Neural connection lines
  const lineGeo = new THREE.BufferGeometry();
  const lineCount = window.innerWidth < 768 ? 100 : 300;
  const linePos = new Float32Array(lineCount * 6);
  for (let i = 0; i < lineCount; i++) {
    const idx1 = Math.floor(Math.random() * count);
    const idx2 = Math.floor(Math.random() * count);
    linePos[i * 6] = pos[idx1 * 3];
    linePos[i * 6 + 1] = pos[idx1 * 3 + 1];
    linePos[i * 6 + 2] = pos[idx1 * 3 + 2];
    linePos[i * 6 + 3] = pos[idx2 * 3];
    linePos[i * 6 + 4] = pos[idx2 * 3 + 1];
    linePos[i * 6 + 5] = pos[idx2 * 3 + 2];
  }
  lineGeo.setAttribute('position', new THREE.BufferAttribute(linePos, 3));
  const lineMat = new THREE.LineBasicMaterial({
    color: 0x00d4ff,
    transparent: true,
    opacity: 0.06,
    blending: THREE.AdditiveBlending
  });
  const lines = new THREE.LineSegments(lineGeo, lineMat);
  scene.add(lines);

  camera.position.z = 8;
  let mouseX = 0, mouseY = 0;

  document.addEventListener('mousemove', (e) => {
    mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
    mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
  });

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  function animate() {
    requestAnimationFrame(animate);
    points.rotation.x += 0.0003;
    points.rotation.y += 0.0005;
    lines.rotation.x += 0.0003;
    lines.rotation.y += 0.0005;
    // Cursor tracking
    camera.position.x += (mouseX * 0.5 - camera.position.x) * 0.02;
    camera.position.y += (-mouseY * 0.5 - camera.position.y) * 0.02;
    camera.lookAt(scene.position);
    renderer.render(scene, camera);
  }
  animate();
}

// ── GSAP Scroll Reveals ──
function initScrollAnimations() {
  if (typeof gsap === 'undefined' || typeof ScrollTrigger === 'undefined') {
    // Fallback: just show everything
    document.querySelectorAll('.reveal').forEach(el => el.classList.add('visible'));
    return;
  }
  gsap.registerPlugin(ScrollTrigger);

  document.querySelectorAll('.reveal').forEach(el => {
    gsap.fromTo(el, { y: 40, opacity: 0 }, {
      y: 0, opacity: 1, duration: 0.9,
      ease: 'power3.out',
      scrollTrigger: { trigger: el, start: 'top 88%', once: true }
    });
  });

  // Staggered card animations
  document.querySelectorAll('.stagger-parent').forEach(parent => {
    const children = parent.querySelectorAll('.stagger-child');
    gsap.fromTo(children, { y: 50, opacity: 0 }, {
      y: 0, opacity: 1, duration: 0.7, stagger: 0.12,
      ease: 'power3.out',
      scrollTrigger: { trigger: parent, start: 'top 85%', once: true }
    });
  });
}

// ── Chat Typing Animation ──
function initChatAnimation() {
  const msgs = document.querySelectorAll('.chat-msg');
  msgs.forEach((msg, i) => {
    msg.style.animationDelay = `${i * 0.8 + 0.5}s`;
  });
}

// ── Nav Scroll ──
function initNav() {
  const nav = document.getElementById('f-main-nav');
  if (!nav) return;
  window.addEventListener('scroll', () => {
    nav.classList.toggle('scrolled', window.scrollY > 40);
  });
  const toggleBtn = document.getElementById('f-menu-toggle');
  const mobileMenu = document.getElementById('f-mobile-menu');
  const icon = document.getElementById('f-menu-icon');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      const open = mobileMenu.classList.toggle('open');
      icon.className = open ? 'fa-solid fa-xmark' : 'fa-solid fa-bars';
    });
  }
  window.closeMobileF = () => {
    if (mobileMenu) mobileMenu.classList.remove('open');
    if (icon) icon.className = 'fa-solid fa-bars';
  };
}

// ── Typing Effect for Hero ──
function initTyping() {
  const el = document.getElementById('hero-typed');
  if (!el) return;
  const text = el.getAttribute('data-text') || el.textContent;
  el.textContent = '';
  let i = 0;
  function type() {
    if (i < text.length) {
      el.textContent += text[i];
      i++;
      setTimeout(type, 30);
    }
  }
  setTimeout(type, 800);
}

// ── FAQ Toggle ──
window.toggleFaq = (btn) => {
  const item = btn.closest('.faq-item');
  const body = item.querySelector('.faq-body');
  const isOpen = item.classList.contains('open');
  document.querySelectorAll('.faq-item').forEach(el => {
    el.classList.remove('open');
    const b = el.querySelector('.faq-body');
    if (b) b.style.maxHeight = '0';
  });
  if (!isOpen) {
    item.classList.add('open');
    if (body) body.style.maxHeight = body.scrollHeight + 'px';
  }
};

// ── Init All ──
document.addEventListener('DOMContentLoaded', () => {
  initNav();
  initTyping();
  initChatAnimation();
  // Defer heavy stuff
  setTimeout(() => {
    initHeroCanvas();
    initScrollAnimations();
  }, 100);
});
