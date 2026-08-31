import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Custom hook for audio visualization
 * Creates dynamic bar heights based on audio analysis
 */
export function useAudioVisualizer(audioRef, isPlaying, barCount = 32) {
  const [leftBars, setLeftBars] = useState(() => Array(barCount).fill(10));
  const [rightBars, setRightBars] = useState(() => Array(barCount).fill(10));
  const analyzerRef = useRef(null);
  const audioContextRef = useRef(null);
  const sourceRef = useRef(null);
  const animationRef = useRef(null);
  const dataArrayRef = useRef(null);

  // Initialize Web Audio API
  const initAudioContext = useCallback(() => {
    if (!audioRef.current || audioContextRef.current) return;

    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      audioContextRef.current = new AudioContext();
      analyzerRef.current = audioContextRef.current.createAnalyser();
      analyzerRef.current.fftSize = 128;
      analyzerRef.current.smoothingTimeConstant = 0.7;
      
      sourceRef.current = audioContextRef.current.createMediaElementSource(audioRef.current);
      sourceRef.current.connect(analyzerRef.current);
      analyzerRef.current.connect(audioContextRef.current.destination);
      
      dataArrayRef.current = new Uint8Array(analyzerRef.current.frequencyBinCount);
    } catch (err) {
      console.log('Audio visualization not supported:', err);
    }
  }, [audioRef]);

  // Animation loop
  const animate = useCallback(() => {
    if (!analyzerRef.current || !dataArrayRef.current || !isPlaying) {
      // When not playing, gradually reduce bars
      setLeftBars(prev => prev.map(h => Math.max(10, h * 0.9)));
      setRightBars(prev => prev.map(h => Math.max(10, h * 0.9)));
      return;
    }

    analyzerRef.current.getByteFrequencyData(dataArrayRef.current);
    
    const bufferLength = dataArrayRef.current.length;
    const newLeftBars = [];
    const newRightBars = [];
    
    const step = Math.floor(bufferLength / barCount);
    
    for (let i = 0; i < barCount; i++) {
      const index = i * step;
      const value = dataArrayRef.current[index] || 0;
      
      // Normalize to percentage (10-100)
      const normalized = Math.max(10, (value / 255) * 100);
      
      // Add different variation between left and right for stereo effect
      const leftVariation = 1 + (Math.sin(Date.now() / 500 + i * 0.3) * 0.2);
      const rightVariation = 1 + (Math.cos(Date.now() / 500 + i * 0.3 + 0.5) * 0.2);
      
      newLeftBars.push(Math.min(100, normalized * leftVariation));
      newRightBars.push(Math.min(100, normalized * rightVariation));
    }
    
    setLeftBars(newLeftBars);
    setRightBars(newRightBars);
    
    animationRef.current = requestAnimationFrame(animate);
  }, [isPlaying, barCount]);

  // Start/stop animation based on playing state
  useEffect(() => {
    if (isPlaying) {
      initAudioContext();
      if (audioContextRef.current?.state === 'suspended') {
        audioContextRef.current.resume();
      }
      animationRef.current = requestAnimationFrame(animate);
    } else {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      // Fade out effect
      const fadeOut = () => {
        setLeftBars(prev => {
          const newBars = prev.map(h => Math.max(10, h * 0.92));
          if (newBars.every(h => h <= 12)) return prev;
          requestAnimationFrame(fadeOut);
          return newBars;
        });
        setRightBars(prev => prev.map(h => Math.max(10, h * 0.92)));
      };
      fadeOut();
    }

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isPlaying, animate, initAudioContext]);

  return { leftBars, rightBars };
}

/**
 * Enhanced simple visualizer with distinctly different left/right channels
 * Creates beautiful, organic wave patterns that respond to volume and playback
 * Each channel has its own unique character and rhythm
 */
export function useSimpleVisualizer(isPlaying, volume, barCount = 32, currentTime = 0) {
  const [leftBars, setLeftBars] = useState(() => Array(barCount).fill(10));
  const [rightBars, setRightBars] = useState(() => Array(barCount).fill(10));
  const animationRef = useRef(null);
  const timeRef = useRef(0);
  const prevVolumeRef = useRef(volume);
  const prevTimeRef = useRef(currentTime);
  const volumeTransitionRef = useRef(0);
  const seekTransitionRef = useRef(0);
  
  // Separate phase offsets for left and right to create distinct patterns
  const leftPhaseRef = useRef(0);
  const rightPhaseRef = useRef(Math.PI * 0.7);
  
  // Energy accumulators for each channel
  const leftEnergyRef = useRef(Array(barCount).fill(50));
  const rightEnergyRef = useRef(Array(barCount).fill(50));
  
  // Detect volume changes and seek events
  useEffect(() => {
    // Volume change detection - triggers visual pulse
    if (Math.abs(prevVolumeRef.current - volume) > 2) {
      volumeTransitionRef.current = 1.0;
      prevVolumeRef.current = volume;
    }
    
    // Seek event detection - triggers wave effect
    const timeDiff = Math.abs(currentTime - prevTimeRef.current);
    if (timeDiff > 1.0) {
      seekTransitionRef.current = 1.0;
      // Shift phases differently on seek for visual variety
      leftPhaseRef.current += currentTime * 0.3;
      rightPhaseRef.current += currentTime * 0.5;
    }
    prevTimeRef.current = currentTime;
  }, [volume, currentTime]);

  useEffect(() => {
    const animate = () => {
      timeRef.current += 0.04;
      volumeTransitionRef.current = Math.max(0, volumeTransitionRef.current - 0.015);
      seekTransitionRef.current = Math.max(0, seekTransitionRef.current - 0.025);
      
      // Slowly drift the phases for organic movement
      leftPhaseRef.current += 0.02;
      rightPhaseRef.current += 0.025;
      
      if (isPlaying) {
        const baseIntensity = (volume / 100) * 0.8 + 0.2;
        const volumePulse = volumeTransitionRef.current * 0.4;
        const seekWave = seekTransitionRef.current * 0.5;
        
        // LEFT CHANNEL - Bass-heavy, slower, more grounded rhythm
        // Emphasizes lower frequencies with deep, punchy movements
        const newLeftBars = Array(barCount).fill(0).map((_, i) => {
          const position = i / barCount;
          const centerDistance = Math.abs(position - 0.5) * 2;
          
          // Primary wave - slow, bass-like pulse
          const bassWave = Math.sin(timeRef.current * 1.4 + leftPhaseRef.current + i * 0.25) * 0.4;
          
          // Secondary wave - mid-range groove
          const midWave = Math.sin(timeRef.current * 2.8 + i * 0.45 + Math.PI / 3) * 0.25;
          
          // Tertiary wave - subtle high-frequency shimmer
          const highWave = Math.sin(timeRef.current * 5.2 + i * 0.12) * 0.1;
          
          // Bass emphasis - bars toward the center are stronger
          const bassEmphasis = Math.pow(1 - centerDistance, 1.8) * 0.25;
          
          // Pulse wave - creates a breathing effect
          const pulseWave = Math.sin(timeRef.current * 0.8) * 0.15 * (1 - position);
          
          // Seek effect - ripple spreading from left
          const seekEffect = seekWave * Math.sin((position * Math.PI * 3) - (seekTransitionRef.current * Math.PI * 5)) * 0.3;
          
          // Volume pulse - synchronized bass hit
          const volumeEffect = volumePulse * (0.6 + Math.pow(Math.sin(timeRef.current * 8), 2) * 0.4) * (1 - position * 0.5);
          
          // Natural randomness - subtle noise
          const noise = (Math.random() - 0.5) * 0.08;
          
          // Energy smoothing for organic movement
          const targetEnergy = 0.42 + bassWave + midWave + highWave + bassEmphasis + pulseWave + seekEffect + volumeEffect + noise;
          leftEnergyRef.current[i] = leftEnergyRef.current[i] * 0.85 + targetEnergy * 100 * 0.15;
          
          const combined = leftEnergyRef.current[i] * baseIntensity;
          return Math.max(8, Math.min(100, combined));
        });
        
        // RIGHT CHANNEL - Treble-focused, faster, more energetic and sparkly
        // Emphasizes higher frequencies with quick, dancing movements
        const newRightBars = Array(barCount).fill(0).map((_, i) => {
          const position = i / barCount;
          const centerDistance = Math.abs(position - 0.5) * 2;
          
          // Primary wave - fast, treble-like shimmer
          const trebleWave = Math.cos(timeRef.current * 3.2 + rightPhaseRef.current + i * 0.38) * 0.35;
          
          // Secondary wave - syncopated rhythm
          const rhythmWave = Math.cos(timeRef.current * 4.5 + i * 0.52 - Math.PI / 5) * 0.28;
          
          // Tertiary wave - sparkling high frequencies
          const sparkleWave = Math.sin(timeRef.current * 7.5 + i * 0.2 + Math.PI / 4) * 0.15;
          
          // Quaternary wave - adds complexity
          const complexWave = Math.cos(timeRef.current * 2.1 + i * 0.65) * 0.12;
          
          // Treble emphasis - outer bars are stronger
          const trebleEmphasis = Math.pow(position, 1.5) * 0.2;
          
          // Dancing effect - creates playful bouncing
          const danceWave = Math.abs(Math.sin(timeRef.current * 3.5 + i * 0.3)) * 0.18 * position;
          
          // Seek effect - ripple spreading from right (opposite direction)
          const seekEffect = seekWave * Math.cos((position * Math.PI * 3) + (seekTransitionRef.current * Math.PI * 5)) * 0.3;
          
          // Volume pulse - bright accent hit
          const volumeEffect = volumePulse * (0.5 + Math.pow(Math.cos(timeRef.current * 10 + Math.PI / 4), 2) * 0.5) * (0.5 + position * 0.5);
          
          // Natural randomness - more active noise for treble character
          const noise = (Math.random() - 0.5) * 0.1;
          
          // Energy smoothing - faster response for treble
          const targetEnergy = 0.45 + trebleWave + rhythmWave + sparkleWave + complexWave + trebleEmphasis + danceWave + seekEffect + volumeEffect + noise;
          rightEnergyRef.current[i] = rightEnergyRef.current[i] * 0.8 + targetEnergy * 100 * 0.2;
          
          const combined = rightEnergyRef.current[i] * baseIntensity;
          return Math.max(8, Math.min(100, combined));
        });
        
        setLeftBars(newLeftBars);
        setRightBars(newRightBars);
      } else {
        // Elegant fade out when paused
        setLeftBars(prev => prev.map((h, i) => {
          leftEnergyRef.current[i] *= 0.92;
          return Math.max(8, h * 0.92);
        }));
        setRightBars(prev => prev.map((h, i) => {
          rightEnergyRef.current[i] *= 0.92;
          return Math.max(8, h * 0.92);
        }));
      }
      
      animationRef.current = requestAnimationFrame(animate);
    };
    
    animationRef.current = requestAnimationFrame(animate);
    
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isPlaying, volume, barCount, currentTime]);

  return { leftBars, rightBars };
}