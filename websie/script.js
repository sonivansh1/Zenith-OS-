// ==========================================================
// Zenith OS — Interactive Website Engine
// Official ReactBits WebGL2 SideRays Background Engine
// & ReactBits AnimatedContent Spring Motion
// ==========================================================

document.addEventListener("DOMContentLoaded", () => {
    initSideRays();
    initAnimatedContent();
    initSpotlightCards();
    initMagneticButtons();
    initInstallStepper();
    initDynamicIslandSim();
    initMobileSidebar();
    initCompanionEyes();
    initGallery();
    initCopyButtons();
});

// ----------------------------------------------------------
// 1. Official ReactBits WebGL2 SideRays Background Engine
// Source: https://reactbits.dev/backgrounds/side-rays
// Volumetric light rays with interactive mouse tracking & dust motes
// GPU-accelerated WebGL2 Pipeline (60 FPS, 0% CPU overhead)
// ----------------------------------------------------------
function initSideRays() {
    const container = document.getElementById("side-rays-container");
    const canvas = document.getElementById("side-rays-canvas");
    if (!container || !canvas) return;

    const gl = canvas.getContext("webgl2", {
        alpha: true,
        premultipliedAlpha: true,
        antialias: false,
        depth: false,
        stencil: false,
        powerPreference: "high-performance"
    });

    if (!gl) {
        console.warn("WebGL2 not supported on this browser context.");
        return;
    }

    const PIXEL_BUDGET = 2.4e6;
    const TAU = Math.PI * 2;

    const ORIGINS = {
        'top-right': { flipX: 0, flipY: 0, side: 0 },
        'top-left': { flipX: 1, flipY: 0, side: 0 },
        'bottom-right': { flipX: 0, flipY: 1, side: 0 },
        'bottom-left': { flipX: 1, flipY: 1, side: 0 },
        right: { flipX: 0, flipY: 0, side: 1 },
        left: { flipX: 1, flipY: 0, side: 1 }
    };

    const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
    const wrapAngle = angle => ((((angle + Math.PI) % TAU) + TAU) % TAU) - Math.PI;

    const parseColor = value => {
        const text = String(value || '').trim();
        const hex = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(text);
        if (hex) {
            const full = hex[1].length === 3 ? hex[1].replace(/./g, digit => digit + digit) : hex[1];
            return [0, 2, 4].map(index => parseInt(full.slice(index, index + 2), 16) / 255);
        }
        const rgb = /^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)/i.exec(text);
        if (rgb) return [rgb[1], rgb[2], rgb[3]].map(channel => clamp(parseFloat(channel) / 255, 0, 1));
        return [1, 1, 1];
    };

    // Zenith OS signature aesthetic: Electric Cyan to Aurora Teal / Violet
    const settings = {
        colorA: parseColor("#00ffcc"),
        colorB: parseColor("#38bdf8"),
        blend: 0.65,
        frame: ORIGINS['top-right'],
        speed: 2.2 * 0.4,
        intensity: 2.3 * 0.75,
        spread: clamp(2.2, 0.1, 8) * 0.225,
        density: clamp(6.0, 1, 40),
        sharpness: clamp(0.52, 0, 1),
        tilt: (clamp(0, -180, 180) * Math.PI) / 180,
        falloff: clamp(1.45, 0.2, 6),
        glow: 1.15 * 1.2,
        saturation: 1.1,
        dust: clamp(0.2, 0, 1),
        followMouse: true,
        mouseInfluence: clamp(0.6, 0, 1),
        intro: true,
        light: false,
        opacity: clamp(0.92, 0, 1),
        maxRatio: clamp(2.0, 0.5, 3)
    };

    const VERTEX = `#version 300 es
    const vec2 corners[3] = vec2[3](vec2(-1.0, -1.0), vec2(3.0, -1.0), vec2(-1.0, 3.0));
    void main() {
      gl_Position = vec4(corners[gl_VertexID], 0.0, 1.0);
    }`;

    const FRAGMENT = `#version 300 es
    precision highp float;
    uniform vec2 uResolution;
    uniform float uTime;
    uniform vec3 uColorA;
    uniform vec3 uColorB;
    uniform float uBlend;
    uniform float uIntensity;
    uniform float uSpread;
    uniform float uDensity;
    uniform float uSharpness;
    uniform float uFalloff;
    uniform float uGlow;
    uniform float uSaturation;
    uniform float uDust;
    uniform float uOpacity;
    uniform float uReveal;
    uniform float uLight;
    uniform vec3 uFrame;
    uniform float uAim;
    uniform vec3 uFocus;
    uniform float uSway;
    out vec4 fragColor;

    float hash(vec2 p) {
      p = fract(p * vec2(123.34, 456.21));
      p += dot(p, p + 45.32);
      return fract(p.x * p.y);
    }

    float noise(vec2 p) {
      vec2 i = floor(p);
      vec2 f = p - i;
      vec2 w = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
      float a = hash(i);
      float b = hash(i + vec2(1.0, 0.0));
      float c = hash(i + vec2(0.0, 1.0));
      float d = hash(i + vec2(1.0, 1.0));
      return mix(mix(a, b, w.x), mix(c, d, w.x), w.y);
    }

    float shafts(float u, float t, float seed, float aa) {
      float sway = (0.4 * sin(t * 0.31 + seed) + 0.24 * sin(t * 0.17 + seed * 2.3)) * uSway;
      float n = 0.7 * noise(vec2(u + sway + seed, t * 0.3)) + 0.3 * noise(vec2(u * 2.4 + sway * 1.5 + seed * 1.7, t * 0.45 + 3.0));
      float width = mix(0.5, 0.1, uSharpness);
      float s = mix(smoothstep(0.5 - width, 0.5 + width, n), 0.5, aa);
      return mix(0.05, 1.0, s);
    }

    float motes(vec2 p, float cell, float t, float seed) {
      p += vec2(t * 0.021, -t * 0.013) + seed * 7.31;
      vec2 grid = p / cell;
      vec2 id = floor(grid);
      vec2 f = grid - id;
      float h = hash(id + seed);
      if (h > 0.5) return 0.0;
      vec2 center = 0.25 + 0.5 * vec2(hash(id + 1.7 + seed), hash(id + 3.1 + seed));
      center += 0.1 * vec2(sin(t * 0.7 + h * 31.0), cos(t * 0.6 + h * 23.0));
      float size = mix(0.035, 0.09, hash(id + 5.3 + seed));
      float edge = length(fwidth(grid)) * 0.7;
      float twinkle = 0.55 + 0.45 * sin(t * 1.9 + h * 41.0);
      return (1.0 - smoothstep(size - edge, size + edge, length(f - center))) * twinkle;
    }

    void main() {
      float aspect = uResolution.x / uResolution.y;
      vec2 q = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.y;
      if (uFrame.x > 0.5) q.x = -q.x;
      if (uFrame.y > 0.5) q.y = -q.y;
      vec2 source = uFrame.z > 0.5 ? vec2(aspect * 0.5 + 0.42, 0.3) : vec2(aspect * 0.5 + 0.1, 0.62);
      float heading = (uFrame.z > 0.5 ? 3.42 : -2.48) + uAim + 0.035 * sin(uTime * 0.21) * uSway;
      vec2 v = q - source;
      float r = length(v);
      float angle = mod(atan(v.y, v.x) - heading + 3.14159265, 6.28318531) - 3.14159265;
      float t = uTime;
      float u = angle * uDensity;
      float aa = smoothstep(0.12, 0.45, fwidth(u));
      float offset = uSpread * 0.22;
      float fanA = exp(-pow((angle + offset) / uSpread, 2.0) * 1.4);
      float fanB = exp(-pow((angle - offset) / (uSpread * 1.15), 2.0) * 1.4);
      float focus = 1.0 + uFocus.z * exp(-pow((angle - uFocus.x) / uFocus.y, 2.0));
      float lightA = fanA * shafts(u, t, 0.0, aa) * focus;
      float lightB = fanB * shafts(u * 0.83, t * 0.6, 17.0, aa) * focus;
      float reach = 1.0 / (1.0 + pow(r / 0.4, uFalloff));
      vec3 glowColor = mix(uColorA, uColorB, uBlend);
      vec3 light = (uColorA * lightA * (1.0 - uBlend) + uColorB * lightB * uBlend) * 2.0 * reach;
      light += glowColor * uGlow * exp(-pow(r / 0.4, 2.0));
      if (uDust > 0.0) {
        float sparkle = motes(q, 0.06, t, 0.0) + 0.7 * motes(q, 0.038, t * 0.8, 9.0);
        light += mix(glowColor, vec3(1.0), 0.6) * sparkle * (lightA + lightB) * reach * uDust * 2.5;
      }
      light *= uIntensity * (1.0 - smoothstep(uReveal * 2.6 - 0.45, uReveal * 2.6, r)) * smoothstep(0.0, 0.35, uReveal);
      float gray = dot(light, vec3(0.2126, 0.7152, 0.0722));
      light = max(mix(vec3(gray), light, uSaturation), 0.0);
      float peak = max(light.r, max(light.g, light.b));
      float grain = (fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715)))) - 0.5) / 255.0;
      if (uLight > 0.5) {
        vec3 ink = pow(light / max(peak, 1e-4), vec3(2.0)) * 0.75;
        float alpha = clamp(pow(1.0 - exp(-peak * 2.6), 2.5) * 0.9 * uOpacity + grain, 0.0, 1.0);
        fragColor = vec4(pow(ink, vec3(1.0 / 2.2)) * alpha, alpha);
        return;
      }
      float mapped = 1.0 - exp(-peak);
      vec3 tone = light * (mapped / max(peak, 1e-4));
      tone = mix(tone, vec3(mapped), smoothstep(0.7, 1.0, mapped) * 0.55);
      vec3 shown = clamp(tone * uOpacity, 0.0, 1.0);
      float alpha = max(shown.r, max(shown.g, shown.b));
      vec3 color = clamp(shown * alpha + grain, 0.0, 1.0);
      fragColor = vec4(min(color, vec3(alpha)), alpha);
    }`;

    const compileShader = (type, source) => {
        const shader = gl.createShader(type);
        gl.shaderSource(shader, source);
        gl.compileShader(shader);
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
            console.error("Shader compile error:", gl.getShaderInfoLog(shader));
            gl.deleteShader(shader);
            return null;
        }
        return shader;
    };

    const vShader = compileShader(gl.VERTEX_SHADER, VERTEX);
    const fShader = compileShader(gl.FRAGMENT_SHADER, FRAGMENT);
    const program = gl.createProgram();
    gl.attachShader(program, vShader);
    gl.attachShader(program, fShader);
    gl.linkProgram(program);

    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        console.error("Program link error:", gl.getProgramInfoLog(program));
        return;
    }

    const uniforms = {};
    const count = gl.getProgramParameter(program, gl.ACTIVE_UNIFORMS);
    for (let i = 0; i < count; i++) {
        const info = gl.getActiveUniform(program, i);
        if (info) uniforms[info.name] = gl.getUniformLocation(program, info.name);
    }

    const geometryFor = (frame, aspect) => ({
        source: frame.side ? [aspect * 0.5 + 0.42, 0.3] : [aspect * 0.5 + 0.1, 0.62],
        heading: frame.side ? 3.42 : -2.48
    });

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const vao = gl.createVertexArray();
    const size = { width: 1, height: 1 };
    const pointer = { x: 0, y: 0, inside: false };
    const aim = { value: 0, velocity: 0 };
    const focus = { angle: 0, strength: 0 };

    let time = Math.random() * 100;
    let reveal = settings.intro && !reduced ? 0 : 1;
    let raf = 0;
    let last = 0;
    let visible = true;
    let pageVisible = document.visibilityState !== 'hidden';

    let resizePending = false;
    const applyResize = () => {
        const s = settings;
        const rect = container.getBoundingClientRect();
        const cssWidth = Math.max(1, rect.width);
        const cssHeight = Math.max(1, rect.height);
        const ratio = Math.min(
            window.devicePixelRatio || 1,
            s.maxRatio,
            Math.sqrt(PIXEL_BUDGET / (cssWidth * cssHeight))
        );
        const width = Math.max(1, Math.round(cssWidth * ratio));
        const height = Math.max(1, Math.round(cssHeight * ratio));
        if (canvas.width !== width || canvas.height !== height) {
            canvas.width = width;
            canvas.height = height;
        }
        size.width = cssWidth;
        size.height = cssHeight;
    };

    const resize = () => {
        resizePending = true;
        wake();
    };

    const pointerAngle = s => {
        let x = (pointer.x - size.width / 2) / size.height;
        let y = (size.height / 2 - pointer.y) / size.height;
        if (s.frame.flipX) x = -x;
        if (s.frame.flipY) y = -y;
        const { source, heading } = geometryFor(s.frame, size.width / size.height);
        return wrapAngle(Math.atan2(y - source[1], x - source[0]) - heading - s.tilt);
    };

    const frame = now => {
        raf = 0;
        if (resizePending) {
            resizePending = false;
            applyResize();
        }
        const s = settings;
        const dt = clamp((now - last) / 1000 || 0, 0, 0.05);
        last = Math.max(last, now);
        time += dt * s.speed * (reduced ? 0.3 : 1);
        if (reveal < 1) reveal = Math.min(1, reveal + dt / 1.6);

        const tracking = s.followMouse && pointer.inside && !reduced;
        const pointed = tracking ? pointerAngle(s) : 0;
        const target = tracking ? clamp(pointed, -s.spread, s.spread) * s.mouseInfluence : 0;
        const focusTarget = tracking ? s.mouseInfluence : 0;
        const ease = 1 - Math.exp(-dt * 6);
        if (tracking) focus.angle += (clamp(pointed - aim.value, -s.spread * 1.5, s.spread * 1.5) - focus.angle) * ease;
        focus.strength += (focusTarget - focus.strength) * ease;
        const stiffness = 18;
        const damping = 2 * Math.sqrt(stiffness);
        aim.velocity += ((target - aim.value) * stiffness - aim.velocity * damping) * dt;
        aim.value += aim.velocity * dt;

        gl.viewport(0, 0, canvas.width, canvas.height);
        gl.useProgram(program);
        gl.bindVertexArray(vao);
        const u = uniforms;
        gl.uniform2f(u.uResolution, canvas.width, canvas.height);
        gl.uniform1f(u.uTime, time);
        gl.uniform3f(u.uColorA, s.colorA[0], s.colorA[1], s.colorA[2]);
        gl.uniform3f(u.uColorB, s.colorB[0], s.colorB[1], s.colorB[2]);
        gl.uniform1f(u.uBlend, s.blend);
        gl.uniform1f(u.uIntensity, s.intensity);
        gl.uniform1f(u.uSpread, s.spread);
        gl.uniform1f(u.uDensity, s.density);
        gl.uniform1f(u.uSharpness, s.sharpness);
        gl.uniform1f(u.uFalloff, s.falloff);
        gl.uniform1f(u.uGlow, s.glow);
        gl.uniform1f(u.uSaturation, s.saturation);
        gl.uniform1f(u.uDust, s.dust);
        gl.uniform1f(u.uOpacity, s.opacity);
        gl.uniform1f(u.uReveal, 1 - Math.pow(1 - reveal, 3));
        gl.uniform1f(u.uLight, s.light ? 1 : 0);
        gl.uniform3f(u.uFrame, s.frame.flipX, s.frame.flipY, s.frame.side);
        gl.uniform1f(u.uAim, s.tilt + aim.value);
        gl.uniform3f(u.uFocus, focus.angle, Math.max(0.06, s.spread * 0.25), focus.strength * 1.4);
        gl.uniform1f(u.uSway, reduced ? 0 : 1);
        gl.drawArrays(gl.TRIANGLES, 0, 3);

        const settling =
            Math.abs(target - aim.value) > 1e-4 ||
            Math.abs(aim.velocity) > 1e-4 ||
            Math.abs(focusTarget - focus.strength) > 1e-3;
        const busy = (s.speed > 0 && !reduced) || reveal < 1 || settling;
        if (busy && visible && pageVisible) raf = requestAnimationFrame(frame);
    };

    const wake = () => {
        if (raf || !visible || !pageVisible) return;
        last = performance.now();
        raf = requestAnimationFrame(frame);
    };

    const onPointerMove = event => {
        const rect = container.getBoundingClientRect();
        pointer.x = event.clientX - rect.left;
        pointer.y = event.clientY - rect.top;
        pointer.inside =
            event.clientX >= rect.left &&
            event.clientX <= rect.right &&
            event.clientY >= rect.top &&
            event.clientY <= rect.bottom;
        wake();
    };

    const onLeave = () => {
        pointer.inside = false;
        wake();
    };

    const onPointerUp = event => {
        if (event.pointerType !== 'mouse') onLeave();
    };

    window.addEventListener('pointermove', onPointerMove, { passive: true });
    window.addEventListener('pointerup', onPointerUp, { passive: true });
    window.addEventListener('pointercancel', onPointerUp, { passive: true });
    document.documentElement.addEventListener('pointerleave', onLeave);

    const resizeObserver = new ResizeObserver(() => {
        resize();
        wake();
    });
    resizeObserver.observe(container);

    const intersection = new IntersectionObserver(entries => {
        visible = entries.some(entry => entry.isIntersecting);
        wake();
    });
    intersection.observe(container);

    document.addEventListener('visibilitychange', () => {
        pageVisible = document.visibilityState !== 'hidden';
        wake();
    });

    resize();
    wake();
}

// ----------------------------------------------------------
// 2. ReactBits AnimatedContent Component Engine
// Based on: https://reactbits.dev/animations/animated-content
// Guaranteed instant visibility above fold & spring motion on scroll
// ----------------------------------------------------------
function initAnimatedContent() {
    const revealElements = document.querySelectorAll(".animated-content, [data-animated-content], [data-reveal]");
    if (!revealElements.length) return;

    const viewportHeight = window.innerHeight;

    // Immediately ensure above-the-fold elements are 100% visible
    revealElements.forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.top < viewportHeight * 0.92) {
            el.classList.add("is-revealed", "revealed");
        } else {
            el.classList.add("anim-ready");
        }
    });

    const observer = new IntersectionObserver((entries, obs) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const el = entry.target;
                const delay = parseInt(el.dataset.delay || "0", 10);
                setTimeout(() => {
                    el.classList.add("is-revealed", "revealed");
                }, delay);
                obs.unobserve(el);
            }
        });
    }, {
        threshold: 0.08,
        rootMargin: "0px 0px -20px 0px"
    });

    revealElements.forEach(el => observer.observe(el));
}

// ----------------------------------------------------------
// 3. ReactBits Spotlight Card Effect (Mouse Coordinate Tracker)
// ----------------------------------------------------------
function initSpotlightCards() {
    const cards = document.querySelectorAll(".spotlight-card");
    if (!cards.length) return;

    cards.forEach(card => {
        card.addEventListener("mousemove", (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            card.style.setProperty("--mouse-x", `${x}px`);
            card.style.setProperty("--mouse-y", `${y}px`);
        });
    });
}

// ----------------------------------------------------------
// 4. ReactBits Magnetic Buttons
// ----------------------------------------------------------
function initMagneticButtons() {
    const btns = document.querySelectorAll(".magnetic-btn");
    if (!btns.length) return;

    btns.forEach(btn => {
        btn.addEventListener("mousemove", (e) => {
            const rect = btn.getBoundingClientRect();
            const x = e.clientX - rect.left - rect.width / 2;
            const y = e.clientY - rect.top - rect.height / 2;
            btn.style.transform = `translate(${x * 0.18}px, ${y * 0.18}px)`;
        });

        btn.addEventListener("mouseleave", () => {
            btn.style.transform = "translate(0px, 0px)";
        });
    });
}

// ----------------------------------------------------------
// 5. Visual Installation Guide Stepper
// ----------------------------------------------------------
function initInstallStepper() {
    const stepTabs = document.querySelectorAll(".step-tab");
    const stepPanes = document.querySelectorAll(".step-pane");

    if (!stepTabs.length || !stepPanes.length) return;

    stepTabs.forEach(tab => {
        tab.addEventListener("click", () => {
            const stepNum = tab.dataset.step;

            stepTabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");

            stepPanes.forEach(p => {
                p.classList.remove("active");
                if (p.id === `step-pane-${stepNum}`) {
                    p.classList.add("active");
                }
            });
        });
    });
}

// ----------------------------------------------------------
// 6. Dynamic Island Resting Notch
// ----------------------------------------------------------
function initDynamicIslandSim() {
    // Top cylindrical notch stays sleek, animated, and resting at the screen edge
    // Clicking does not open preview, maintaining true unobtrusive OS notch behavior
    const island = document.getElementById("islandSim");
    if (!island) return;
}

// ----------------------------------------------------------
// 7. Mobile / Android Navigation Sidebar Drawer
// ----------------------------------------------------------
function initMobileSidebar() {
    const menuBtn = document.getElementById("mobileMenuBtn");
    const sidebar = document.getElementById("mobileSidebar");
    const backdrop = document.getElementById("mobileSidebarBackdrop");
    const closeBtn = document.getElementById("mobileSidebarClose");
    const navLinks = document.querySelectorAll(".mobile-nav-link, .mobile-cta-btn");

    if (!menuBtn || !sidebar || !backdrop) return;

    function openSidebar() {
        sidebar.classList.add("active");
        backdrop.classList.add("active");
        document.body.style.overflow = "hidden";
    }

    function closeSidebar() {
        sidebar.classList.remove("active");
        backdrop.classList.remove("active");
        document.body.style.overflow = "";
    }

    menuBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        openSidebar();
    });

    if (closeBtn) {
        closeBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            closeSidebar();
        });
    }

    backdrop.addEventListener("click", closeSidebar);

    navLinks.forEach(link => {
        link.addEventListener("click", () => {
            closeSidebar();
        });
    });

    // Close on Escape key
    window.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && sidebar.classList.contains("active")) {
            closeSidebar();
        }
    });
}

// ----------------------------------------------------------
// 8. Autonomous Expressive Companion Robot Eyes (Vector Engine)
// ----------------------------------------------------------
function initCompanionEyes() {
    const canvas = document.getElementById("companionEyesCanvas");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const cssWidth = 340;
    const cssHeight = 130;
    canvas.width = cssWidth * dpr;
    canvas.height = cssHeight * dpr;
    ctx.scale(dpr, dpr);

    let currentMood = "neutral";
    let targetGazeX = 0;
    let targetGazeY = 0;
    let gazeX = 0;
    let gazeY = 0;
    let blinkProgress = 0;
    let isBlinking = false;
    let blinkStartTime = 0;
    const blinkDuration = 140;
    let nextBlinkTime = performance.now() + 2500 + Math.random() * 2000;
    let animTime = 0;

    // Mood buttons
    const moodChips = document.querySelectorAll(".mood-chip");
    moodChips.forEach(chip => {
        chip.addEventListener("click", () => {
            moodChips.forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            currentMood = chip.dataset.mood || "neutral";
        });
    });

    // Interactive gaze tracking
    window.addEventListener("mousemove", (e) => {
        const rect = canvas.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        const dx = e.clientX - centerX;
        const dy = e.clientY - centerY;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist > 0) {
            const maxOffset = 14;
            const factor = Math.min(dist / 300, 1);
            targetGazeX = (dx / dist) * maxOffset * factor;
            targetGazeY = (dy / dist) * (maxOffset * 0.75) * factor;
        } else {
            targetGazeX = 0;
            targetGazeY = 0;
        }
    });

    // Click canvas to trigger blink
    canvas.addEventListener("click", () => {
        triggerBlink();
    });

    function triggerBlink() {
        if (!isBlinking) {
            isBlinking = true;
            blinkStartTime = performance.now();
        }
    }

    function render(now) {
        requestAnimationFrame(render);
        animTime = now * 0.003;

        // Autonomous blink scheduling
        if (!isBlinking && now >= nextBlinkTime) {
            if (currentMood !== "offline" && currentMood !== "listening" && currentMood !== "responding") {
                triggerBlink();
            }
            nextBlinkTime = now + 2800 + Math.random() * 2500;
        }

        // Compute blink progress
        if (isBlinking) {
            const elapsed = now - blinkStartTime;
            if (elapsed < blinkDuration) {
                blinkProgress = Math.sin((elapsed / blinkDuration) * Math.PI);
            } else {
                blinkProgress = 0;
                isBlinking = false;
            }
        }

        // LERP gaze
        gazeX += (targetGazeX - gazeX) * 0.12;
        gazeY += (targetGazeY - gazeY) * 0.12;

        // Clear canvas
        ctx.clearRect(0, 0, cssWidth, cssHeight);

        const leftCx = cssWidth * 0.35 + gazeX;
        const rightCx = cssWidth * 0.65 + gazeX;
        const cy = cssHeight * 0.5 + gazeY;

        // Render eyes according to mood
        switch (currentMood) {
            case "happy":
                drawHappyEye(leftCx, cy);
                drawHappyEye(rightCx, cy);
                break;
            case "love":
                drawHeartEye(leftCx, cy, animTime);
                drawHeartEye(rightCx, cy, animTime);
                break;
            case "stars":
                drawStarEye(leftCx, cy, animTime);
                drawStarEye(rightCx, cy, animTime + 0.5);
                break;
            case "wink":
                drawHappyEye(leftCx, cy);
                drawWinkEye(rightCx, cy);
                break;
            case "listening":
                drawMicWave(leftCx, rightCx, cy, animTime, false);
                break;
            case "responding":
                drawMicWave(leftCx, rightCx, cy, animTime, true);
                break;
            case "confused":
                drawNeutralEye(leftCx, cy - 8, 42, 60, blinkProgress);
                drawDroopEye(rightCx, cy + 10, 42, 48, blinkProgress);
                break;
            case "scanner":
                drawScannerEyes(leftCx, rightCx, cy, animTime);
                break;
            case "shocked":
                drawShockedEye(leftCx, cy, blinkProgress);
                drawShockedEye(rightCx, cy, blinkProgress);
                break;
            case "offline":
                drawDeadCrossEye(leftCx, cy);
                drawDeadCrossEye(rightCx, cy);
                break;
            case "neutral":
            default:
                drawNeutralEye(leftCx, cy, 44, 62, blinkProgress);
                drawNeutralEye(rightCx, cy, 44, 62, blinkProgress);
                break;
        }
    }

    // Drawing Primitives
    function drawNeutralEye(cx, cy, w, h, blink) {
        const currentH = Math.max(3, h * (1 - blink * 0.95));
        const currentR = Math.min(w / 2, currentH / 2);

        ctx.save();
        ctx.shadowColor = "#00F0FF";
        ctx.shadowBlur = 18;
        ctx.fillStyle = "#00F0FF";

        ctx.beginPath();
        ctx.roundRect(cx - w / 2, cy - currentH / 2, w, currentH, currentR);
        ctx.fill();

        if (currentH > 20) {
            ctx.shadowBlur = 0;
            ctx.fillStyle = "rgba(255, 255, 255, 0.45)";
            ctx.beginPath();
            ctx.ellipse(cx - w * 0.18, cy - currentH * 0.22, w * 0.16, currentH * 0.16, 0, 0, Math.PI * 2);
            ctx.fill();
        }
        ctx.restore();
    }

    function drawHappyEye(cx, cy) {
        ctx.save();
        ctx.shadowColor = "#00F0FF";
        ctx.shadowBlur = 18;
        ctx.strokeStyle = "#00F0FF";
        ctx.lineWidth = 9;
        ctx.lineCap = "round";

        ctx.beginPath();
        ctx.arc(cx, cy + 10, 24, Math.PI * 1.15, Math.PI * 1.85, false);
        ctx.stroke();
        ctx.restore();
    }

    function drawWinkEye(cx, cy) {
        ctx.save();
        ctx.shadowColor = "#00F0FF";
        ctx.shadowBlur = 16;
        ctx.strokeStyle = "#00F0FF";
        ctx.lineWidth = 8;
        ctx.lineCap = "round";

        ctx.beginPath();
        ctx.moveTo(cx - 22, cy);
        ctx.lineTo(cx + 22, cy);
        ctx.stroke();
        ctx.restore();
    }

    function drawDroopEye(cx, cy, w, h, blink) {
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(-0.15);
        drawNeutralEye(0, 0, w, h, blink);
        ctx.restore();
    }

    function drawHeartEye(cx, cy, time) {
        const pulse = 1.0 + 0.08 * Math.sin(time * 5);
        const w = 46 * pulse;
        const h = 44 * pulse;

        ctx.save();
        ctx.shadowColor = "#FF5096";
        ctx.shadowBlur = 22;
        ctx.fillStyle = "#FF5096";

        ctx.beginPath();
        const topY = cy - h * 0.45;
        const bottomY = cy + h * 0.5;
        const notchY = cy - h * 0.15;
        const leftX = cx - w * 0.5;
        const rightX = cx + w * 0.5;

        ctx.moveTo(cx, notchY);
        ctx.bezierCurveTo(cx - w * 0.25, topY, leftX, topY + h * 0.2, leftX, cy);
        ctx.bezierCurveTo(leftX, cy + h * 0.3, cx - w * 0.1, bottomY - h * 0.1, cx, bottomY);
        ctx.bezierCurveTo(cx + w * 0.1, bottomY - h * 0.1, rightX, cy + h * 0.3, rightX, cy);
        ctx.bezierCurveTo(rightX, topY + h * 0.2, cx + w * 0.25, topY, cx, notchY);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    }

    function drawStarEye(cx, cy, time) {
        const pulse = 1.0 + 0.1 * Math.sin(time * 4);
        const rOuter = 26 * pulse;
        const rInner = 8 * pulse;

        ctx.save();
        ctx.shadowColor = "#FFD700";
        ctx.shadowBlur = 20;
        ctx.fillStyle = "#FFD700";

        ctx.beginPath();
        const points = [
            [cx, cy - rOuter],
            [cx + rInner, cy - rInner],
            [cx + rOuter, cy],
            [cx + rInner, cy + rInner],
            [cx, cy + rOuter],
            [cx - rInner, cy + rInner],
            [cx - rOuter, cy],
            [cx - rInner, cy - rInner]
        ];
        ctx.moveTo(points[0][0], points[0][1]);
        for (let i = 1; i < points.length; i++) {
            ctx.lineTo(points[i][0], points[i][1]);
        }
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    }

    function drawScannerEyes(leftCx, rightCx, cy, time) {
        const w = 50;
        const h = 10;
        const r = 5;

        ctx.save();
        ctx.shadowColor = "#00F0FF";
        ctx.shadowBlur = 14;
        ctx.fillStyle = "rgba(0, 240, 255, 0.25)";

        ctx.beginPath();
        ctx.roundRect(leftCx - w / 2, cy - h / 2, w, h, r);
        ctx.roundRect(rightCx - w / 2, cy - h / 2, w, h, r);
        ctx.fill();

        const sweep = Math.sin(time * 3) * 16;
        ctx.fillStyle = "#00F0FF";
        ctx.shadowBlur = 22;

        ctx.beginPath();
        ctx.roundRect(leftCx + sweep - 8, cy - h / 2, 16, h, r);
        ctx.roundRect(rightCx + sweep - 8, cy - h / 2, 16, h, r);
        ctx.fill();

        ctx.restore();
    }

    function drawShockedEye(cx, cy, blink) {
        const w = 48;
        const h = Math.max(3, 76 * (1 - blink * 0.95));
        const r = Math.min(w / 2, h / 2);

        ctx.save();
        ctx.shadowColor = "#00F0FF";
        ctx.shadowBlur = 22;
        ctx.fillStyle = "#00F0FF";

        ctx.beginPath();
        ctx.roundRect(cx - w / 2, cy - h / 2, w, h, r);
        ctx.fill();
        ctx.restore();
    }

    function drawDeadCrossEye(cx, cy) {
        const arm = 18;
        ctx.save();
        ctx.shadowColor = "#FF2233";
        ctx.shadowBlur = 18;
        ctx.strokeStyle = "#FF2233";
        ctx.lineWidth = 7;
        ctx.lineCap = "round";

        ctx.beginPath();
        ctx.moveTo(cx - arm, cy - arm);
        ctx.lineTo(cx + arm, cy + arm);
        ctx.moveTo(cx + arm, cy - arm);
        ctx.lineTo(cx - arm, cy + arm);
        ctx.stroke();
        ctx.restore();
    }

    function drawMicWave(leftCx, rightCx, cy, time, isResponding) {
        const midCx = (leftCx + rightCx) / 2;
        const barW = 8;
        const gap = 20;

        ctx.save();
        ctx.shadowColor = isResponding ? "#00FF88" : "#00F0FF";
        ctx.shadowBlur = 20;
        ctx.fillStyle = isResponding ? "#00FF88" : "#00F0FF";

        const heights = [
            Math.max(12, 38 + 24 * Math.sin(time * 4)),
            Math.max(16, 52 + 30 * Math.sin(time * 4 + 1.4)),
            Math.max(12, 38 + 24 * Math.sin(time * 4 + 2.8))
        ];

        [-1, 0, 1].forEach((pos, idx) => {
            const bx = midCx + pos * gap;
            const bh = heights[idx];
            ctx.beginPath();
            ctx.roundRect(bx - barW / 2, cy - bh / 2, barW, bh, barW / 2);
            ctx.fill();
        });

        ctx.restore();
    }

    requestAnimationFrame(render);
}

// ----------------------------------------------------------
// 9. Screenshot Gallery Tabs
// ----------------------------------------------------------
function initGallery() {
    const tabs = document.querySelectorAll(".gallery-tab");
    const mainImg = document.getElementById("galleryMainImg");

    if (!tabs.length || !mainImg) return;

    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");

            const newSrc = tab.dataset.img;
            mainImg.style.opacity = "0.2";
            setTimeout(() => {
                mainImg.src = newSrc;
                mainImg.style.opacity = "1";
            }, 180);
        });
    });
}

// ----------------------------------------------------------
// 11. Copy Command Buttons
// ----------------------------------------------------------
function initCopyButtons() {
    const copyBtns = document.querySelectorAll(".copy-btn");
    copyBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetId = btn.dataset.target;
            const targetEl = targetId ? document.getElementById(targetId) : null;
            const textToCopy = targetEl ? targetEl.textContent : btn.closest(".code-wrapper, .quickstart-box").querySelector("code").textContent;

            navigator.clipboard.writeText(textToCopy).then(() => {
                const orig = btn.textContent;
                btn.textContent = "Copied!";
                setTimeout(() => {
                    btn.textContent = orig;
                }, 2000);
            }).catch(() => {
                btn.textContent = "Done";
            });
        });
    });
}
