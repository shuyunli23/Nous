import React, { memo } from 'react';
import { motion } from 'framer-motion';

/**
 * Audio visualizer bars component
 * Displays animated bars that respond to music with distinct left/right channel aesthetics
 * Left channel: Warm cyan tones, bass-focused character
 * Right channel: Cool teal/emerald tones, treble-focused character
 */
const AudioVisualizer = memo(function AudioVisualizer({ 
  leftBars, 
  rightBars, 
  isPlaying,
  variant = 'default' // 'default' | 'mini' | 'full'
}) {
  const config = {
    default: { height: 80, barWidth: 3, gap: 2, borderRadius: 2 },
    mini: { height: 40, barWidth: 2, gap: 1, borderRadius: 1 },
    full: { height: 160, barWidth: 4, gap: 3, borderRadius: 3 }
  }[variant];

  // Left channel color - warm cyan with bass character
  const getLeftBarColor = (index, value) => {
    const intensity = value / 100;
    const position = index / leftBars.length;
    
    // Gradient from deep cyan to bright teal
    const hue = 175 - (position * 15); // 175 to 160
    const saturation = 70 + (intensity * 20);
    const lightness = 40 + (intensity * 25);
    const alpha = 0.5 + (intensity * 0.5);
    
    return `hsla(${hue}, ${saturation}%, ${lightness}%, ${alpha})`;
  };

  // Right channel color - cool emerald with treble character
  const getRightBarColor = (index, value) => {
    const intensity = value / 100;
    const position = index / rightBars.length;
    
    // Gradient from emerald to bright green
    const hue = 145 + (position * 20); // 145 to 165
    const saturation = 65 + (intensity * 25);
    const lightness = 45 + (intensity * 20);
    const alpha = 0.5 + (intensity * 0.5);
    
    return `hsla(${hue}, ${saturation}%, ${lightness}%, ${alpha})`;
  };

  // Glow effect for high-intensity bars
  const getLeftGlow = (value) => {
    if (!isPlaying || value < 45) return 'none';
    const intensity = (value - 45) / 55;
    return `0 0 ${8 + intensity * 12}px hsla(170, 80%, 50%, ${0.3 + intensity * 0.4})`;
  };

  const getRightGlow = (value) => {
    if (!isPlaying || value < 45) return 'none';
    const intensity = (value - 45) / 55;
    return `0 0 ${8 + intensity * 12}px hsla(155, 75%, 50%, ${0.3 + intensity * 0.4})`;
  };

  return (
    <div 
      className="flex items-center justify-center select-none"
      style={{ height: config.height, gap: variant === 'full' ? 8 : 4 }}
    >
      {/* Left channel visualizer - reversed for symmetry, bass character */}
      <div className="flex items-center" style={{ gap: config.gap }}>
        {[...leftBars].reverse().map((height, i) => {
          const originalIndex = leftBars.length - 1 - i;
          return (
            <motion.div
              key={`left-${i}`}
              className="origin-center"
              style={{
                width: config.barWidth,
                borderRadius: config.borderRadius,
                background: isPlaying 
                  ? getLeftBarColor(originalIndex, height)
                  : 'rgba(120, 180, 180, 0.15)',
                boxShadow: getLeftGlow(height),
              }}
              animate={{
                height: `${Math.max(12, height)}%`,
                scaleY: isPlaying ? 1 : 0.6,
              }}
              transition={{
                type: 'spring',
                stiffness: 280,
                damping: 18,
                mass: 0.6
              }}
            />
          );
        })}
      </div>

      {/* Center divider - subtle glowing separator */}
      {variant === 'full' && (
        <div 
          className="w-px h-1/2 rounded-full"
          style={{
            background: isPlaying 
              ? 'linear-gradient(to bottom, transparent, rgba(16, 185, 129, 0.4), transparent)'
              : 'rgba(255, 255, 255, 0.1)',
            boxShadow: isPlaying ? '0 0 8px rgba(16, 185, 129, 0.3)' : 'none'
          }}
        />
      )}
      
      {/* Right channel visualizer - treble character */}
      <div className="flex items-center" style={{ gap: config.gap }}>
        {rightBars.map((height, i) => (
          <motion.div
            key={`right-${i}`}
            className="origin-center"
            style={{
              width: config.barWidth,
              borderRadius: config.borderRadius,
              background: isPlaying 
                ? getRightBarColor(i, height)
                : 'rgba(100, 200, 150, 0.15)',
              boxShadow: getRightGlow(height),
            }}
            animate={{
              height: `${Math.max(12, height)}%`,
              scaleY: isPlaying ? 1 : 0.6,
            }}
            transition={{
              type: 'spring',
              stiffness: 320,
              damping: 16,
              mass: 0.5
            }}
          />
        ))}
      </div>
    </div>
  );
});

/**
 * Waveform visualizer - horizontal wave display
 * Alternative visualizer style for variety
 */
export const WaveformVisualizer = memo(function WaveformVisualizer({
  leftBars,
  rightBars,
  isPlaying,
  height = 60
}) {
  // Combine and smooth the bars for a waveform look
  const combinedBars = leftBars.map((l, i) => (l + rightBars[i]) / 2);
  
  const points = combinedBars.map((value, i) => {
    const x = (i / (combinedBars.length - 1)) * 100;
    const y = 50 - ((value - 50) * 0.8);
    return `${x},${y}`;
  }).join(' ');

  const mirrorPoints = combinedBars.map((value, i) => {
    const x = (i / (combinedBars.length - 1)) * 100;
    const y = 50 + ((value - 50) * 0.8);
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg 
      viewBox="0 0 100 100" 
      className="w-full"
      style={{ height }}
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id="waveGradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor={isPlaying ? "rgba(6, 182, 212, 0.6)" : "rgba(255,255,255,0.1)"} />
          <stop offset="50%" stopColor={isPlaying ? "rgba(16, 185, 129, 0.8)" : "rgba(255,255,255,0.15)"} />
          <stop offset="100%" stopColor={isPlaying ? "rgba(52, 211, 153, 0.6)" : "rgba(255,255,255,0.1)"} />
        </linearGradient>
        <filter id="glow">
          <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
          <feMerge>
            <feMergeNode in="coloredBlur"/>
            <feMergeNode in="SourceGraphic"/>
          </feMerge>
        </filter>
      </defs>
      
      {/* Upper wave */}
      <motion.polyline
        points={points}
        fill="none"
        stroke="url(#waveGradient)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        filter={isPlaying ? "url(#glow)" : "none"}
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.5 }}
      />
      
      {/* Lower wave (mirror) */}
      <motion.polyline
        points={mirrorPoints}
        fill="none"
        stroke="url(#waveGradient)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{ opacity: 0.5 }}
        filter={isPlaying ? "url(#glow)" : "none"}
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.5, delay: 0.1 }}
      />
      
      {/* Center line */}
      <line 
        x1="0" y1="50" x2="100" y2="50" 
        stroke={isPlaying ? "rgba(16, 185, 129, 0.3)" : "rgba(255,255,255,0.05)"} 
        strokeWidth="0.5"
      />
    </svg>
  );
});

export default AudioVisualizer;