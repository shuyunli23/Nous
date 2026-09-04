import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';

/**
 * Background effect: Gradient Orbs (original default)
 */
const GradientOrbs = ({ isPlaying }) => (
  <div className="absolute inset-0 overflow-hidden">
    <div className="absolute inset-0 bg-gradient-to-b from-emerald-900/30 via-black to-black" />
    {isPlaying && (
      <>
        <motion.div
          className="absolute w-[300px] sm:w-[400px] md:w-[500px] h-[300px] sm:h-[400px] md:h-[500px] rounded-full blur-[80px] md:blur-[100px]"
          style={{
            background: 'radial-gradient(circle, rgba(6, 182, 212, 0.35) 0%, rgba(6, 182, 212, 0.15) 40%, transparent 70%)',
            left: '5%',
            top: '10%'
          }}
          animate={{
            x: [0, 60, 0],
            y: [0, 40, 0],
            scale: [1, 1.2, 1],
            opacity: [0.6, 0.8, 0.6],
          }}
          transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.div
          className="absolute w-[250px] sm:w-[350px] md:w-[450px] h-[250px] sm:h-[350px] md:h-[450px] rounded-full blur-[60px] md:blur-[80px]"
          style={{
            background: 'radial-gradient(circle, rgba(16, 185, 129, 0.3) 0%, rgba(16, 185, 129, 0.1) 40%, transparent 70%)',
            right: '5%',
            bottom: '20%'
          }}
          animate={{
            x: [0, -40, 0],
            y: [0, -30, 0],
            scale: [1, 1.15, 1],
            opacity: [0.5, 0.7, 0.5],
          }}
          transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut', delay: 0.5 }}
        />
      </>
    )}
  </div>
);

/**
 * Background effect: Starfield
 */
const Starfield = ({ isPlaying }) => {
  const stars = useRef(
    Array.from({ length: 80 }, () => ({
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 2 + 1,
      duration: Math.random() * 3 + 2,
      delay: Math.random() * 2,
    }))
  ).current;

  return (
    <div className="absolute inset-0 overflow-hidden bg-gradient-to-b from-indigo-950/40 via-black to-black">
      {stars.map((star, i) => (
        <motion.div
          key={i}
          className="absolute rounded-full bg-white"
          style={{
            left: `${star.x}%`,
            top: `${star.y}%`,
            width: star.size,
            height: star.size,
          }}
          animate={isPlaying ? {
            opacity: [0.2, 0.9, 0.2],
            scale: [1, 1.5, 1],
          } : { opacity: 0.3, scale: 1 }}
          transition={{
            duration: star.duration,
            repeat: Infinity,
            delay: star.delay,
            ease: 'easeInOut',
          }}
        />
      ))}
      {/* Shooting stars when playing */}
      {isPlaying && (
        <>
          <motion.div
            className="absolute w-1 h-1 bg-white rounded-full"
            style={{ boxShadow: '0 0 6px 2px rgba(255,255,255,0.6)' }}
            animate={{
              x: ['-10vw', '110vw'],
              y: ['10vh', '60vh'],
              opacity: [0, 1, 1, 0],
            }}
            transition={{ duration: 2, repeat: Infinity, repeatDelay: 5, ease: 'linear' }}
          />
          <motion.div
            className="absolute w-1 h-1 bg-cyan-300 rounded-full"
            style={{ boxShadow: '0 0 6px 2px rgba(103,232,249,0.6)' }}
            animate={{
              x: ['110vw', '-10vw'],
              y: ['20vh', '70vh'],
              opacity: [0, 1, 1, 0],
            }}
            transition={{ duration: 1.8, repeat: Infinity, repeatDelay: 7, delay: 3, ease: 'linear' }}
          />
        </>
      )}
    </div>
  );
};

/**
 * Background effect: Fireworks (Canvas-based)
 * Rockets launch from the bottom in occasional volleys, then burst at apex.
 */
const Fireworks = ({ isPlaying }) => {
  const canvasRef = useRef(null);
  const frontCanvasRef = useRef(null);
  const animationRef = useRef(null);
  const rocketsRef = useRef([]);
  const sparksRef = useRef([]);
  const pendingRef = useRef([]);
  const [frontHost, setFrontHost] = useState(null);

  useEffect(() => {
    setFrontHost(document.getElementById('player-fx-front'));
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const frontCanvas = frontCanvasRef.current;
    const frontCtx = frontCanvas?.getContext('2d') || null;

    const fitCanvas = (target, targetCtx) => {
      if (!target || !targetCtx) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const width = Math.max(1, target.clientWidth);
      const height = Math.max(1, target.clientHeight);
      target.width = Math.floor(width * dpr);
      target.height = Math.floor(height * dpr);
      targetCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const resize = () => {
      fitCanvas(canvas, ctx);
      fitCanvas(frontCanvas, frontCtx);
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    if (frontCanvas) observer.observe(frontCanvas);
    window.addEventListener('resize', resize);

    const launchRocket = (width, height) => {
      const hScale = Math.max(0.85, Math.min(1.15, height / 720));
      const hue = Math.random() * 360;
      rocketsRef.current.push({
        x: width * (0.18 + Math.random() * 0.64),
        y: height + 8,
        vx: (Math.random() - 0.5) * 0.22,
        vy: -(5.75 + Math.random() * 1.85) * hScale,
        targetY: height * (0.11 + Math.random() * 0.24),
        hue,
        trail: [],
        front: Math.random() < 0.3,
        burstVy: -(0.35 + Math.random() * 0.7),
      });
    };

    const explode = (rocket, width, height) => {
      const scale = Math.max(0.8, Math.min(width, height) / 720);
      const speedBase = (2.55 + Math.random() * 0.95) * scale;
      const count = 96 + Math.floor(Math.random() * 40);
      const inheritVx = rocket.vx * 0.25;
      const inheritVy = rocket.vy * 0.16;

      for (let i = 0; i < count; i++) {
        const angle = Math.random() * Math.PI * 2;
        const radial = Math.pow(Math.random(), 0.5);
        const speed = speedBase * (0.2 + radial * 0.95);
        const heavy = Math.random() < 0.28;
        const front = Math.random() < 0.42;
        sparksRef.current.push({
          x: rocket.x,
          y: rocket.y,
          vx: Math.cos(angle) * speed + inheritVx,
          vy: Math.sin(angle) * speed + inheritVy + 0.12,
          life: 1,
          decay: heavy ? 0.0042 + Math.random() * 0.003 : 0.0054 + Math.random() * 0.004,
          hue: rocket.hue + (Math.random() - 0.5) * 24,
          size: (1.4 + Math.random() * 1.4) * scale * (front ? 1.12 : 0.92),
          drag: heavy ? 0.018 + Math.random() * 0.012 : 0.01 + Math.random() * 0.01,
          gravity: heavy ? 0.068 + Math.random() * 0.022 : 0.052 + Math.random() * 0.018,
          front,
        });
      }
    };

    const strokeTrail = (targetCtx, points) => {
      if (!targetCtx || points.length < 2) return;
      targetCtx.lineCap = 'round';
      targetCtx.lineJoin = 'round';
      targetCtx.beginPath();
      targetCtx.moveTo(points[0].x, points[0].y);
      for (let i = 1; i < points.length; i++) {
        targetCtx.lineTo(points[i].x, points[i].y);
      }
      targetCtx.strokeStyle = 'rgba(255, 214, 168, 0.28)';
      targetCtx.lineWidth = 1.05;
      targetCtx.stroke();
      const n = points.length;
      if (n < 3) return;
      targetCtx.beginPath();
      targetCtx.moveTo(points[n - 3].x, points[n - 3].y);
      targetCtx.lineTo(points[n - 1].x, points[n - 1].y);
      targetCtx.strokeStyle = 'rgba(255, 248, 232, 0.62)';
      targetCtx.lineWidth = 1.2;
      targetCtx.stroke();
    };

    const drawRocket = (targetCtx, rocket) => {
      if (!targetCtx) return;
      strokeTrail(targetCtx, rocket.trail);
      targetCtx.beginPath();
      targetCtx.arc(rocket.x, rocket.y, rocket.front ? 1.9 : 1.55, 0, Math.PI * 2);
      targetCtx.fillStyle = 'rgba(255, 248, 230, 0.98)';
      targetCtx.fill();
    };

    const drawSpark = (targetCtx, p) => {
      if (!targetCtx) return;
      targetCtx.beginPath();
      targetCtx.arc(p.x, p.y, Math.max(0.55, p.size * p.life), 0, Math.PI * 2);
      targetCtx.fillStyle = `hsla(${p.hue}, 100%, ${58 + p.life * 22}%, ${p.life})`;
      targetCtx.fill();
    };

    const fadeBack = (width, height) => {
      ctx.globalCompositeOperation = 'source-over';
      if (width <= 0 || height <= 0) return;
      const sky = ctx.createLinearGradient(0, 0, 0, height);
      sky.addColorStop(0, 'rgba(6, 10, 28, 0.72)');
      sky.addColorStop(0.42, 'rgba(10, 16, 38, 0.7)');
      sky.addColorStop(0.76, 'rgba(18, 16, 32, 0.68)');
      sky.addColorStop(1, 'rgba(28, 20, 16, 0.68)');
      ctx.fillStyle = sky;
      ctx.fillRect(0, 0, width, height);

      const haze = ctx.createRadialGradient(
        width * 0.5,
        height * 1.08,
        height * 0.06,
        width * 0.5,
        height * 1.02,
        height * 0.52,
      );
      haze.addColorStop(0, 'rgba(52, 38, 28, 0.16)');
      haze.addColorStop(1, 'rgba(52, 38, 28, 0)');
      ctx.fillStyle = haze;
      ctx.fillRect(0, 0, width, height);
    };

    const fadeFront = (width, height) => {
      if (!frontCtx || width <= 0 || height <= 0) return;
      frontCtx.globalCompositeOperation = 'destination-out';
      frontCtx.fillStyle = 'rgba(0, 0, 0, 0.62)';
      frontCtx.fillRect(0, 0, width, height);
      frontCtx.globalCompositeOperation = 'source-over';
    };

    const scheduleVolley = (time) => {
      const count = 1 + Math.floor(Math.random() * 4);
      for (let i = 0; i < count; i++) {
        pendingRef.current.push({
          at: time + i * (70 + Math.random() * 240),
        });
      }
    };

    let nextVolley = 0;
    let lastTime = 0;

    const animate = (time) => {
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      const dt = lastTime ? Math.min(2.2, (time - lastTime) / 16.667) : 1;
      lastTime = time;
      fadeBack(width, height);
      fadeFront(frontCanvas?.clientWidth || width, frontCanvas?.clientHeight || height);

      if (isPlaying) {
        if (nextVolley === 0) nextVolley = time + 280;
        if (time >= nextVolley) {
          scheduleVolley(time);
          nextVolley = time + 2000 + Math.random() * 2800;
        }
        pendingRef.current = pendingRef.current.filter((shot) => {
          if (time < shot.at) return true;
          launchRocket(width, height);
          return false;
        });
      } else {
        pendingRef.current = [];
        nextVolley = 0;
      }

      rocketsRef.current = rocketsRef.current.filter((rocket) => {
        rocket.x += rocket.vx * dt;
        rocket.y += rocket.vy * dt;
        rocket.vy += 0.04 * dt;
        const last = rocket.trail[rocket.trail.length - 1];
        if (!last || Math.hypot(rocket.x - last.x, rocket.y - last.y) > 3.2) {
          rocket.trail.push({ x: rocket.x, y: rocket.y });
          if (rocket.trail.length > 5) rocket.trail.shift();
        }

        if (rocket.y <= rocket.targetY || rocket.vy >= rocket.burstVy) {
          explode(rocket, width, height);
          return false;
        }

        drawRocket(rocket.front ? frontCtx : ctx, rocket);
        return true;
      });

      if (sparksRef.current.length > 1400) {
        sparksRef.current = sparksRef.current.slice(-1100);
      }

      sparksRef.current = sparksRef.current.filter((p) => {
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.vx *= 1 - p.drag * dt;
        p.vy *= 1 - p.drag * dt;
        p.vy += p.gravity * dt;
        p.life -= p.decay * dt;
        if (p.life <= 0) return false;
        drawSpark(p.front ? frontCtx : ctx, p);
        return true;
      });

      animationRef.current = requestAnimationFrame(animate);
    };

    animationRef.current = requestAnimationFrame(animate);

    return () => {
      observer.disconnect();
      window.removeEventListener('resize', resize);
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [isPlaying, frontHost]);

  const frontCanvas = (
    <canvas
      ref={frontCanvasRef}
      className="absolute inset-0 w-full h-full"
    />
  );

  return (
    <div
      className="absolute inset-0"
      style={{
        background:
          'linear-gradient(180deg, #060a1c 0%, #0b1028 46%, #141022 76%, #1a140f 100%)',
      }}
    >
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full"
      />
      {frontHost ? createPortal(frontCanvas, frontHost) : null}
    </div>
  );
};

/**
 * Background effect: Aurora
 */
const Aurora = ({ isPlaying }) => (
  <div className="absolute inset-0 overflow-hidden bg-gradient-to-b from-black via-slate-950 to-black">
    {isPlaying && (
      <>
        <motion.div
          className="absolute w-[150%] h-[40%] top-[5%] -left-[25%]"
          style={{
            background: 'linear-gradient(180deg, transparent 0%, rgba(34, 197, 94, 0.15) 30%, rgba(6, 182, 212, 0.2) 50%, rgba(139, 92, 246, 0.15) 70%, transparent 100%)',
            filter: 'blur(40px)',
            borderRadius: '50%',
          }}
          animate={{
            x: ['-5%', '10%', '-5%'],
            scaleX: [1, 1.2, 1],
            skewX: [0, 5, -5, 0],
            opacity: [0.6, 0.9, 0.6],
          }}
          transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.div
          className="absolute w-[120%] h-[35%] top-[15%] -left-[10%]"
          style={{
            background: 'linear-gradient(180deg, transparent 0%, rgba(139, 92, 246, 0.12) 30%, rgba(236, 72, 153, 0.15) 50%, rgba(34, 197, 94, 0.1) 70%, transparent 100%)',
            filter: 'blur(50px)',
            borderRadius: '50%',
          }}
          animate={{
            x: ['5%', '-8%', '5%'],
            scaleX: [1, 1.15, 1],
            skewX: [0, -3, 3, 0],
            opacity: [0.4, 0.7, 0.4],
          }}
          transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
        />
        <motion.div
          className="absolute w-[100%] h-[25%] top-[25%] left-[5%]"
          style={{
            background: 'linear-gradient(180deg, transparent 0%, rgba(6, 182, 212, 0.1) 40%, rgba(16, 185, 129, 0.12) 60%, transparent 100%)',
            filter: 'blur(35px)',
            borderRadius: '50%',
          }}
          animate={{
            x: ['-3%', '6%', '-3%'],
            opacity: [0.3, 0.6, 0.3],
          }}
          transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut', delay: 2 }}
        />
      </>
    )}
    {!isPlaying && (
      <div
        className="absolute w-[120%] h-[30%] top-[10%] -left-[10%] opacity-30"
        style={{
          background: 'linear-gradient(180deg, transparent 0%, rgba(34, 197, 94, 0.1) 40%, rgba(6, 182, 212, 0.1) 60%, transparent 100%)',
          filter: 'blur(40px)',
          borderRadius: '50%',
        }}
      />
    )}
  </div>
);

/**
 * Background effect: Particles (floating bubbles)
 */
const Particles = ({ isPlaying }) => {
  const particles = useRef(
    Array.from({ length: 40 }, () => ({
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 20 + 5,
      duration: Math.random() * 10 + 8,
      delay: Math.random() * 5,
      hue: Math.random() * 60 + 140, // cyan to purple range
    }))
  ).current;

  return (
    <div className="absolute inset-0 overflow-hidden bg-gradient-to-b from-purple-950/30 via-black to-black">
      {particles.map((p, i) => (
        <motion.div
          key={i}
          className="absolute rounded-full"
          style={{
            left: `${p.x}%`,
            width: p.size,
            height: p.size,
            background: `hsla(${p.hue}, 70%, 50%, 0.3)`,
            boxShadow: `0 0 ${p.size}px hsla(${p.hue}, 70%, 50%, 0.2)`,
          }}
          animate={isPlaying ? {
            y: [`${p.y}vh`, `${p.y - 30}vh`, `${p.y}vh`],
            x: [`${p.x}%`, `${p.x + (Math.random() - 0.5) * 10}%`, `${p.x}%`],
            opacity: [0.2, 0.6, 0.2],
            scale: [1, 1.3, 1],
          } : {
            y: `${p.y}vh`,
            opacity: 0.15,
            scale: 1,
          }}
          transition={{
            duration: p.duration,
            repeat: Infinity,
            delay: p.delay,
            ease: 'easeInOut',
          }}
        />
      ))}
    </div>
  );
};

/**
 * Background effect: Waves
 */
const Waves = ({ isPlaying }) => {
  const canvasRef = useRef(null);
  const animationRef = useRef(null);
  const playingRef = useRef(isPlaying);
  playingRef.current = isPlaying;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const width = Math.max(1, canvas.clientWidth);
      const height = Math.max(1, canvas.clientHeight);
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    window.addEventListener('resize', resize);

    const layers = [
      { base: 0.52, amp: 7, len: 270, speed: 0.36, steep: 0.18, chop: 0.08, skew: 0.15, foam: 0.12, top: [9, 32, 48], bot: [6, 18, 32], alpha: 0.58 },
      { base: 0.64, amp: 15, len: 165, speed: 0.68, steep: 0.28, chop: 0.18, skew: -0.1, foam: 0.34, top: [14, 56, 70], bot: [8, 30, 46], alpha: 0.46 },
      { base: 0.78, amp: 22, len: 108, speed: 1.02, steep: 0.38, chop: 0.26, skew: 0.06, foam: 0.52, top: [26, 90, 96], bot: [10, 40, 56], alpha: 0.32 },
    ];

    const stars = Array.from({ length: 56 }, () => ({
      x: Math.random(),
      y: Math.random() * 0.46,
      size: Math.random() < 0.12 ? 1.25 : 0.45 + Math.random() * 0.55,
      twinkle: Math.random() * Math.PI * 2,
      base: 0.22 + Math.random() * 0.5,
    }));

    const sampleWave = (x, t, layer, height, energy) => {
      const amp = layer.amp * energy * Math.max(0.75, height / 720);
      const th = (x + layer.skew * 48) / layer.len + t * layer.speed;
      const primary = Math.sin(th) + layer.steep * Math.sin(2 * th + 0.25);
      const chop = layer.chop * Math.sin(x / (layer.len * 0.27) + t * layer.speed * 1.85 + 1.1);
      const group = 0.16 * Math.sin(x / (layer.len * 2.35) + t * 0.26);
      const n = primary + chop + group;
      return {
        y: height * layer.base - amp * n,
        crest: Math.max(0, Math.min(1, (n - 0.52) / 0.62)),
      };
    };

    const waveY = (x, t, layer, height, energy) => sampleWave(x, t, layer, height, energy).y;

    let t = 0;
    let last = 0;

    const animate = (now) => {
      const dt = last ? Math.min(0.05, (now - last) / 1000) : 0.016;
      last = now;
      const playing = playingRef.current;
      t += dt * (playing ? 1 : 0.28);
      const energy = playing ? 1 : 0.38;
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      if (width < 1 || height < 1) {
        animationRef.current = requestAnimationFrame(animate);
        return;
      }

      const sky = ctx.createLinearGradient(0, 0, 0, height);
      sky.addColorStop(0, '#020617');
      sky.addColorStop(0.36, '#071422');
      sky.addColorStop(0.5, '#123044');
      ctx.fillStyle = sky;
      ctx.fillRect(0, 0, width, height);

      const moonX = width * 0.74;
      const moonY = height * 0.17;
      const moonR = Math.max(10, Math.min(width, height) * 0.026);

      stars.forEach((star) => {
        const sx = star.x * width;
        const sy = star.y * height;
        const nearMoon = Math.hypot(sx - moonX, sy - moonY);
        if (nearMoon < moonR * 5.5) return;
        const twinkle = 0.72 + 0.28 * Math.sin(t * 0.7 + star.twinkle);
        ctx.beginPath();
        ctx.arc(sx, sy, star.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(220, 230, 245, ${star.base * twinkle})`;
        ctx.fill();
      });
      const moonGlow = ctx.createRadialGradient(moonX, moonY, moonR * 0.4, moonX, moonY, moonR * 8);
      moonGlow.addColorStop(0, 'rgba(220, 230, 245, 0.16)');
      moonGlow.addColorStop(0.55, 'rgba(140, 180, 200, 0.05)');
      moonGlow.addColorStop(1, 'transparent');
      ctx.fillStyle = moonGlow;
      ctx.fillRect(moonX - moonR * 8, moonY - moonR * 8, moonR * 16, moonR * 16);
      ctx.save();
      ctx.beginPath();
      ctx.arc(moonX, moonY, moonR, 0, Math.PI * 2);
      ctx.clip();
      const moonShade = ctx.createLinearGradient(
        moonX - moonR * 0.85,
        moonY - moonR * 0.85,
        moonX + moonR * 0.7,
        moonY + moonR * 0.75,
      );
      moonShade.addColorStop(0, '#f7f9fc');
      moonShade.addColorStop(0.38, '#e4eaf1');
      moonShade.addColorStop(0.72, '#c5ced8');
      moonShade.addColorStop(1, '#9aa6b4');
      ctx.fillStyle = moonShade;
      ctx.fillRect(moonX - moonR - 1, moonY - moonR - 1, moonR * 2 + 2, moonR * 2 + 2);
      ctx.restore();

      layers.forEach((layer) => {
        const y0 = waveY(0, t, layer, height, energy);
        ctx.beginPath();
        ctx.moveTo(0, height);
        ctx.lineTo(0, y0);
        let yMin = y0;
        for (let x = 2; x <= width; x += 2) {
          const y = waveY(x, t, layer, height, energy);
          if (y < yMin) yMin = y;
          ctx.lineTo(x, y);
        }
        ctx.lineTo(width, height);
        ctx.closePath();
        const fill = ctx.createLinearGradient(0, yMin, 0, height);
        fill.addColorStop(0, `rgba(${layer.top.join(',')}, ${layer.alpha})`);
        fill.addColorStop(0.22, `rgba(${layer.top.join(',')}, ${layer.alpha * 0.82})`);
        fill.addColorStop(1, `rgba(${layer.bot.join(',')}, ${layer.alpha * 0.72})`);
        ctx.fillStyle = fill;
        ctx.fill();

        if (layer.foam > 0.05) {
          ctx.lineCap = 'round';
          ctx.lineJoin = 'round';
          let prev = null;
          for (let x = 0; x <= width; x += 2) {
            const sample = sampleWave(x, t, layer, height, energy);
            if (prev && sample.crest > 0.18 && prev.crest > 0.18) {
              ctx.beginPath();
              ctx.moveTo(prev.x, prev.y);
              ctx.lineTo(x, sample.y);
              const a = sample.crest * layer.foam * (playing ? 0.5 : 0.26);
              ctx.strokeStyle = `rgba(214, 232, 236, ${a})`;
              ctx.lineWidth = 0.8 + sample.crest * 1.6;
              ctx.stroke();
            }
            prev = { x, y: sample.y, crest: sample.crest };
          }
        }
      });

      const horizon = height * layers[0].base;
      for (let y = horizon; y < height; y += 3) {
        const dist = (y - horizon) / Math.max(1, height - horizon);
        const layer = dist < 0.38 ? layers[0] : dist < 0.72 ? layers[1] : layers[2];
        const wobble = Math.sin(y * 0.07 + t * 1.35) * (3 + dist * 16);
        const x = moonX + wobble;
        const surface = waveY(x, t, layer, height, energy);
        if (Math.abs(y - surface) > 5 + dist * 7) continue;
        const w = 0.8 + dist * 7;
        ctx.fillStyle = `rgba(214, 228, 240, ${(playing ? 0.16 : 0.09) * (1 - dist * 0.45)})`;
        ctx.beginPath();
        ctx.ellipse(x, y, w, 0.9, 0, 0, Math.PI * 2);
        ctx.fill();
      }

      animationRef.current = requestAnimationFrame(animate);
    };

    animationRef.current = requestAnimationFrame(animate);

    return () => {
      observer.disconnect();
      window.removeEventListener('resize', resize);
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, []);

  return (
    <div className="absolute inset-0 bg-[#020617]">
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full" />
    </div>
  );
};

/**
 * Background effect: Neon Glow - bright colorful pulsing neon lights
 */
const NeonGlow = ({ isPlaying }) => (
  <div className="absolute inset-0 overflow-hidden bg-gradient-to-br from-slate-900 via-purple-950/50 to-slate-900">
    {isPlaying && (
      <>
        <motion.div
          className="absolute w-[60%] h-[2px] top-[20%] left-[20%]"
          style={{ background: 'linear-gradient(90deg, transparent, #f472b6, #c084fc, transparent)', boxShadow: '0 0 20px #f472b6, 0 0 40px #c084fc' }}
          animate={{ opacity: [0.3, 1, 0.3], scaleX: [0.8, 1.2, 0.8] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.div
          className="absolute w-[2px] h-[50%] top-[25%] left-[15%]"
          style={{ background: 'linear-gradient(180deg, transparent, #22d3ee, #a78bfa, transparent)', boxShadow: '0 0 15px #22d3ee, 0 0 30px #a78bfa' }}
          animate={{ opacity: [0.4, 1, 0.4], scaleY: [0.9, 1.1, 0.9] }}
          transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut', delay: 0.5 }}
        />
        <motion.div
          className="absolute w-[40%] h-[2px] bottom-[30%] right-[15%]"
          style={{ background: 'linear-gradient(90deg, transparent, #34d399, #fbbf24, transparent)', boxShadow: '0 0 20px #34d399, 0 0 40px #fbbf24' }}
          animate={{ opacity: [0.3, 1, 0.3], scaleX: [1, 0.8, 1] }}
          transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
        />
        <motion.div
          className="absolute w-[2px] h-[40%] top-[30%] right-[20%]"
          style={{ background: 'linear-gradient(180deg, transparent, #fb923c, #f43f5e, transparent)', boxShadow: '0 0 15px #fb923c, 0 0 30px #f43f5e' }}
          animate={{ opacity: [0.5, 1, 0.5], scaleY: [1.1, 0.9, 1.1] }}
          transition={{ duration: 2.8, repeat: Infinity, ease: 'easeInOut', delay: 0.3 }}
        />
        <motion.div
          className="absolute w-[300px] h-[300px] top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(192, 132, 252, 0.2) 0%, transparent 70%)' }}
          animate={{ scale: [1, 1.3, 1], opacity: [0.3, 0.6, 0.3] }}
          transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
        />
      </>
    )}
    {!isPlaying && (
      <div className="absolute w-[60%] h-[2px] top-[20%] left-[20%] opacity-20"
        style={{ background: 'linear-gradient(90deg, transparent, #f472b6, #c084fc, transparent)' }}
      />
    )}
  </div>
);

/**
 * Background effect: Sunset - warm gradient with floating light
 */
const Sunset = ({ isPlaying }) => (
  <div
    className="absolute inset-0 overflow-hidden"
    style={{
      background: 'linear-gradient(180deg, #0a0d18 0%, #14182c 22%, #2a2040 48%, #6b3348 68%, #b85a3c 84%, #d4894a 100%)',
    }}
  >
    <div className="absolute inset-0 bg-black/30" />
    <div
      className="absolute left-[-25%] right-[-25%] bottom-0 h-[55%] blur-3xl"
      style={{
        background: 'linear-gradient(180deg, transparent 0%, rgba(200, 90, 60, 0.22) 45%, rgba(232, 160, 90, 0.28) 100%)',
      }}
    />
    <motion.div
      className="absolute left-1/2 -translate-x-1/2 rounded-full blur-[56px]"
      style={{
        width: '78vmin',
        height: '46vmin',
        bottom: '-12%',
        background: 'radial-gradient(circle, rgba(255, 196, 130, 0.55) 0%, rgba(255, 130, 70, 0.28) 36%, rgba(180, 60, 50, 0.1) 58%, transparent 74%)',
      }}
      animate={isPlaying ? { scale: [1, 1.05, 1], opacity: [0.7, 0.92, 0.7] } : { opacity: 0.72, scale: 1 }}
      transition={{ duration: 9, repeat: Infinity, ease: 'easeInOut' }}
    />
    <motion.div
      className="absolute left-1/2 -translate-x-1/2 rounded-full blur-[22px]"
      style={{
        width: '22vmin',
        height: '18vmin',
        bottom: '6%',
        background: 'radial-gradient(circle, rgba(255, 232, 190, 0.42) 0%, rgba(255, 170, 90, 0.16) 48%, transparent 72%)',
      }}
      animate={isPlaying ? { opacity: [0.4, 0.62, 0.4] } : { opacity: 0.38 }}
      transition={{ duration: 7, repeat: Infinity, ease: 'easeInOut' }}
    />
    {isPlaying && (
      <>
        <motion.div
          className="absolute w-[60%] h-[42%] rounded-full blur-[90px]"
          style={{
            background: 'radial-gradient(circle, rgba(255, 110, 70, 0.2) 0%, transparent 72%)',
            bottom: '-4%',
            left: '-8%',
          }}
          animate={{ x: [0, 28, 0], opacity: [0.3, 0.5, 0.3] }}
          transition={{ duration: 16, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.div
          className="absolute w-[50%] h-[38%] rounded-full blur-[90px]"
          style={{
            background: 'radial-gradient(circle, rgba(255, 180, 90, 0.16) 0%, transparent 72%)',
            bottom: '0%',
            right: '-10%',
          }}
          animate={{ x: [0, -22, 0], opacity: [0.22, 0.42, 0.22] }}
          transition={{ duration: 13, repeat: Infinity, ease: 'easeInOut', delay: 1.2 }}
        />
      </>
    )}
  </div>
);

/**
 * Background effect: Rainbow Flow - flowing rainbow colors
 */
const RainbowFlow = ({ isPlaying }) => (
  <div className="absolute inset-0 overflow-hidden bg-black">
    {isPlaying && (
      <>
        <motion.div
          className="absolute rounded-full"
          style={{
            width: '160vmax',
            height: '160vmax',
            left: '50%',
            top: '50%',
            marginLeft: '-80vmax',
            marginTop: '-80vmax',
            background: 'conic-gradient(from 0deg, rgba(239,68,68,0.2), rgba(249,115,22,0.2), rgba(234,179,8,0.2), rgba(34,197,94,0.2), rgba(59,130,246,0.2), rgba(168,85,247,0.2), rgba(236,72,153,0.2), rgba(239,68,68,0.2))',
          }}
          animate={{ rotate: 360 }}
          transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
        />
        {['#ef4444', '#f59e0b', '#22c55e', '#3b82f6', '#a855f7', '#ec4899'].map((color, i) => (
          <motion.div
            key={i}
            className="absolute w-[250px] h-[250px] rounded-full blur-[80px]"
            style={{
              background: `radial-gradient(circle, ${color}40 0%, transparent 70%)`,
              left: `${10 + i * 15}%`,
              top: `${20 + (i % 3) * 20}%`,
            }}
            animate={{
              x: [0, (i % 2 === 0 ? 50 : -50), 0],
              y: [0, (i % 2 === 0 ? -30 : 30), 0],
              scale: [1, 1.3, 1],
              opacity: [0.3, 0.6, 0.3],
            }}
            transition={{ duration: 4 + i * 0.8, repeat: Infinity, ease: 'easeInOut', delay: i * 0.5 }}
          />
        ))}
      </>
    )}
    {!isPlaying && (
      <div
        className="absolute inset-0 opacity-20"
        style={{ background: 'linear-gradient(135deg, rgba(239,68,68,0.15), rgba(59,130,246,0.15), rgba(168,85,247,0.15))' }}
      />
    )}
  </div>
);

/**
 * Background effect: Sakura (Cherry Blossoms) - falling petals
 */
const Sakura = ({ isPlaying }) => {
  const petals = useRef(
    Array.from({ length: 35 }, () => ({
      x: Math.random() * 100,
      size: Math.random() * 12 + 6,
      duration: Math.random() * 8 + 6,
      delay: Math.random() * 6,
      sway: Math.random() * 40 - 20,
      rotation: Math.random() * 360,
    }))
  ).current;

  return (
    <div className="absolute inset-0 overflow-hidden"
      style={{ background: 'linear-gradient(180deg, #1a1a2e 0%, #2d1b4e 30%, #4a2040 60%, #1a1a2e 100%)' }}
    >
      <div className="absolute w-[400px] h-[400px] top-[10%] left-[20%] rounded-full blur-[100px]"
        style={{ background: 'radial-gradient(circle, rgba(244, 114, 182, 0.15) 0%, transparent 70%)' }}
      />
      {isPlaying && petals.map((p, i) => (
        <motion.div
          key={i}
          className="absolute"
          style={{
            left: `${p.x}%`,
            width: p.size,
            height: p.size * 0.7,
            background: 'radial-gradient(ellipse, rgba(251, 207, 232, 0.9) 0%, rgba(244, 114, 182, 0.6) 100%)',
            borderRadius: '50% 0 50% 0',
          }}
          animate={{
            y: ['-10vh', '110vh'],
            x: [`${p.x}%`, `${p.x + p.sway}%`],
            rotate: [p.rotation, p.rotation + 360],
            opacity: [0, 0.8, 0.8, 0],
          }}
          transition={{
            duration: p.duration,
            repeat: Infinity,
            delay: p.delay,
            ease: 'linear',
          }}
        />
      ))}
    </div>
  );
};

/**
 * Background effect: Lightning Storm - dramatic flashes
 */
const Lightning = ({ isPlaying }) => {
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    if (!isPlaying) return;
    let timeout;
    const doFlash = () => {
      setFlash(true);
      setTimeout(() => setFlash(false), 150);
      timeout = setTimeout(doFlash, 2000 + Math.random() * 3000);
    };
    timeout = setTimeout(doFlash, 1000);
    return () => clearTimeout(timeout);
  }, [isPlaying]);

  return (
    <div className="absolute inset-0 overflow-hidden bg-gradient-to-b from-slate-900 via-indigo-950/60 to-black">
      <motion.div
        className="absolute w-[80%] h-[30%] top-0 left-[10%] rounded-full blur-[60px]"
        style={{ background: 'radial-gradient(ellipse, rgba(100, 116, 139, 0.4) 0%, transparent 70%)' }}
        animate={isPlaying ? { x: ['-5%', '5%', '-5%'] } : {}}
        transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        className="absolute w-[60%] h-[25%] top-[5%] left-[30%] rounded-full blur-[50px]"
        style={{ background: 'radial-gradient(ellipse, rgba(71, 85, 105, 0.5) 0%, transparent 70%)' }}
        animate={isPlaying ? { x: ['3%', '-3%', '3%'] } : {}}
        transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
      />
      {flash && <div className="absolute inset-0 bg-white/20" />}
      {isPlaying && Array.from({ length: 20 }).map((_, i) => (
        <motion.div
          key={i}
          className="absolute w-[1px] bg-gradient-to-b from-blue-200/60 to-transparent"
          style={{ left: `${5 + i * 4.5}%`, height: `${20 + (i % 5) * 8}px` }}
          animate={{ y: ['-10vh', '110vh'] }}
          transition={{ duration: 0.6 + (i % 4) * 0.1, repeat: Infinity, delay: i * 0.15, ease: 'linear' }}
        />
      ))}
    </div>
  );
};

/**
 * Background effect: Lava Lamp - slow moving blobs
 */
const LavaLamp = ({ isPlaying }) => (
  <div className="absolute inset-0 overflow-hidden bg-gradient-to-b from-orange-950/40 via-red-950/30 to-black">
    {[
      { color: 'rgba(239, 68, 68, 0.4)', size: 200, x: '20%', y: '60%', dx: 30, dy: -80, dur: 8 },
      { color: 'rgba(249, 115, 22, 0.35)', size: 160, x: '60%', y: '70%', dx: -40, dy: -60, dur: 10 },
      { color: 'rgba(234, 179, 8, 0.3)', size: 140, x: '40%', y: '30%', dx: 20, dy: 50, dur: 9 },
      { color: 'rgba(236, 72, 153, 0.35)', size: 180, x: '70%', y: '40%', dx: -30, dy: -40, dur: 11 },
      { color: 'rgba(251, 146, 60, 0.3)', size: 120, x: '30%', y: '50%', dx: 40, dy: 30, dur: 7 },
    ].map((blob, i) => (
      <motion.div
        key={i}
        className="absolute rounded-full blur-[40px]"
        style={{
          width: blob.size,
          height: blob.size,
          background: `radial-gradient(circle, ${blob.color} 0%, transparent 70%)`,
          left: blob.x,
          top: blob.y,
        }}
        animate={isPlaying ? {
          x: [0, blob.dx, 0],
          y: [0, blob.dy, 0],
          scale: [1, 1.4, 1],
          borderRadius: ['50%', '40% 60% 50% 50%', '50%'],
        } : { scale: 1 }}
        transition={{ duration: blob.dur, repeat: Infinity, ease: 'easeInOut', delay: i * 0.5 }}
      />
    ))}
  </div>
);

// Available backgrounds registry
export const BACKGROUNDS = [
  { id: 'orbs', name: 'Gradient Orbs', component: GradientOrbs },
  { id: 'aurora', name: 'Aurora', component: Aurora },
  { id: 'fireworks', name: 'Fireworks', component: Fireworks },
  { id: 'starfield', name: 'Starfield', component: Starfield },
  { id: 'particles', name: 'Particles', component: Particles },
  { id: 'waves', name: 'Waves', component: Waves },
  { id: 'neon', name: 'Neon Glow', component: NeonGlow },
  { id: 'sunset', name: 'Sunset', component: Sunset },
  { id: 'rainbow', name: 'Rainbow Flow', component: RainbowFlow },
  { id: 'sakura', name: 'Sakura', component: Sakura },
  { id: 'lightning', name: 'Lightning', component: Lightning },
  { id: 'lava', name: 'Lava Lamp', component: LavaLamp },
];

/**
 * Background selector button for FullPlayer header
 */
export function BackgroundSelector({ current, onChange }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="relative z-[60]">
      <button
        onClick={(e) => { e.stopPropagation(); setIsOpen(!isOpen); }}
        className="p-2 rounded-full hover:bg-white/10 transition-colors"
        title="Switch background effect"
      >
        <svg className="w-5 h-5 sm:w-6 sm:h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 3v1m0 16v1m8.66-13.66l-.71.71M4.05 19.95l-.71.71M21 12h-1M4 12H3m16.95 7.95l-.71-.71M4.76 4.76l-.71-.71" strokeLinecap="round" />
          <circle cx="12" cy="12" r="4" />
        </svg>
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-[60]" onClick={(e) => { e.stopPropagation(); setIsOpen(false); }} />
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            className="absolute top-full mt-2 right-0 z-[70] bg-zinc-900/95 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl py-2 min-w-[160px] max-h-[70vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {BACKGROUNDS.map(bg => (
              <button
                key={bg.id}
                onClick={(e) => { e.stopPropagation(); onChange(bg.id); setIsOpen(false); }}
                className={`w-full px-4 py-2.5 text-left text-sm transition-colors flex items-center gap-2 ${
                  current === bg.id
                    ? 'text-emerald-400 bg-emerald-500/10'
                    : 'text-zinc-300 hover:bg-white/5 hover:text-white'
                }`}
              >
                {current === bg.id && (
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                )}
                <span className={current === bg.id ? '' : 'ml-3.5'}>{bg.name}</span>
              </button>
            ))}
          </motion.div>
        </>
      )}
    </div>
  );
}

/**
 * Render the selected background
 */
export function PlayerBackground({ backgroundId, isPlaying }) {
  const bg = BACKGROUNDS.find(b => b.id === backgroundId) || BACKGROUNDS[0];
  const Component = bg.component;
  const [frontHost, setFrontHost] = useState(null);

  useEffect(() => {
    setFrontHost(document.getElementById('player-fx-front'));
  }, []);

  return (
    <>
      <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none [transform:translateZ(0)]">
        <Component isPlaying={isPlaying} />
      </div>
      {backgroundId !== 'fireworks' && backgroundId !== 'waves' && frontHost
        ? createPortal(
            <div className="absolute inset-0 opacity-[0.26] mix-blend-screen pointer-events-none">
              <Component isPlaying={isPlaying} />
            </div>,
            frontHost,
          )
        : null}
    </>
  );
}
