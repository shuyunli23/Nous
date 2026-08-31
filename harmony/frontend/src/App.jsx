import React, { useState, useEffect, useRef } from 'react';
import { AnimatePresence } from 'framer-motion';
import { Loader2 } from 'lucide-react';

import { AuthProvider, useAuth } from './contexts/AuthContext';
import { SidebarProvider, useSidebar } from './contexts/SidebarContext';
import { RatingProvider } from './contexts/RatingContext';
import { useSimpleVisualizer } from './hooks/useAudioVisualizer';
import api from './api/client';
import {
  loadPlayback,
  slimTrack,
  streamUrl,
  writePlayback,
} from './utils/playbackSession';

import { Sidebar, MiniPlayer, FullPlayer, QueuePanel, ProfileSettings } from './components';
import {
  LoginPage,
  HomePage,
  TopPage,
  SearchPage,
  LibraryPage,
  RequestsPage,
  ManageMusicPage,
  UsersPage,
  HistoryPage
} from './pages';

function MainApp() {
  const { user, updateUser } = useAuth();
  const { isMobile } = useSidebar();
  const isAdmin = user?.role === 'admin';
  
  const [currentPage, setCurrentPage] = useState('home');
  const [tracks, setTracks] = useState([]);
  const [playlists, setPlaylists] = useState([]);
  const [requests, setRequests] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Profile settings state
  const [showProfileSettings, setShowProfileSettings] = useState(false);
  
  // Player state
  const audioRef = useRef(new Audio());
  const [currentTrack, setCurrentTrack] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(80);
  const [isMuted, setIsMuted] = useState(false);
  const [playMode, setPlayMode] = useState(() => {
    return localStorage.getItem('playMode') || 'shuffle';
  });
  const [isPlayerExpanded, setIsPlayerExpanded] = useState(false);
  const [showQueue, setShowQueue] = useState(false);
  const [queue, setQueue] = useState([]);
  const [activePlaylistId, setActivePlaylistId] = useState(null);

  // Audio visualizer with currentTime for seek detection
  const { leftBars, rightBars } = useSimpleVisualizer(isPlaying, volume, 24, currentTime);

  const fetchData = async () => {
    try {
      const [tracksRes, playlistsRes, requestsRes] = await Promise.all([
        api.get('/music'),
        api.get('/playlists'),
        api.get('/requests')
      ]);
      setTracks(tracksRes.data);
      setPlaylists(playlistsRes.data);
      setRequests(requestsRes.data);
      
      if (isAdmin) {
        const usersRes = await api.get('/admin/users');
        setUsers(usersRes.data);
      }
    } catch (err) {
      console.error('Failed to fetch data:', err);
    } finally {
      setLoading(false);
    }
  };

  // Refresh data on initial load and when switching pages
  useEffect(() => { 
    fetchData(); 
  }, [isAdmin, currentPage]);

  // Audio event handlers
  useEffect(() => {
    const audio = audioRef.current;
    const handleTimeUpdate = () => setCurrentTime(audio.currentTime);
    const handleDurationChange = () => setDuration(audio.duration);
    const handleEnded = () => { 
      if (playMode === 'repeat-one') { 
        audio.currentTime = 0; 
        audio.play(); 
        if (currentTrack) {
          recordPlayHistory(currentTrack.id);
          setTracks(prevTracks => 
            prevTracks.map(t => 
              t.id === currentTrack.id 
                ? { ...t, play_count: t.play_count + 1 }
                : t
            )
          );
        }
      } else { 
        playNext(); 
      } 
    };
    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);

    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('durationchange', handleDurationChange);
    audio.addEventListener('ended', handleEnded);
    audio.addEventListener('play', handlePlay);
    audio.addEventListener('pause', handlePause);

    return () => {
      audio.removeEventListener('timeupdate', handleTimeUpdate);
      audio.removeEventListener('durationchange', handleDurationChange);
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('play', handlePlay);
      audio.removeEventListener('pause', handlePause);
    };
  }, [playMode, queue, currentTrack]);

  useEffect(() => { 
    audioRef.current.volume = isMuted ? 0 : volume / 100; 
  }, [volume, isMuted]);

  useEffect(() => {
    const session = loadPlayback();
    if (!session?.track) return;
    const audio = audioRef.current;
    setCurrentTrack(session.track);
    setQueue(session.queue?.length ? session.queue : [session.track]);
    setCurrentTime(session.currentTime || 0);
    if (session.playMode) {
      setPlayMode(session.playMode);
      localStorage.setItem('playMode', session.playMode);
    }
    const token = localStorage.getItem('token');
    audio.src = `/api/music/${session.track.id}/stream?token=${encodeURIComponent(token)}`;
    const onReady = () => {
      try {
        audio.currentTime = session.currentTime || 0;
      } catch {
        /* ignore */
      }
      if (session.isPlaying) {
        audio.play().catch(() => {});
      }
    };
    audio.addEventListener('loadedmetadata', onReady, { once: true });
    return () => audio.removeEventListener('loadedmetadata', onReady);
  }, []);

  useEffect(() => {
    if (!currentTrack) return;
    writePlayback({
      track: slimTrack(currentTrack),
      queue: (queue.length ? queue : [currentTrack]).map(slimTrack),
      currentTime: audioRef.current.currentTime || currentTime,
      isPlaying,
      playMode,
      volume,
      ...(isPlaying ? { dismissed: false } : {}),
    });
  }, [currentTrack, queue, isPlaying, playMode, volume]);

  useEffect(() => {
    const audio = audioRef.current;
    let last = 0;
    const onTime = () => {
      const now = Date.now();
      if (now - last < 800) return;
      last = now;
      if (!currentTrack) return;
      writePlayback({ currentTime: audio.currentTime, isPlaying: !audio.paused });
    };
    const flush = () => {
      if (!currentTrack) return;
      writePlayback({ currentTime: audio.currentTime, isPlaying: !audio.paused });
    };
    audio.addEventListener('timeupdate', onTime);
    window.addEventListener('pagehide', flush);
    return () => {
      audio.removeEventListener('timeupdate', onTime);
      window.removeEventListener('pagehide', flush);
    };
  }, [currentTrack]);

  // Record play history
  const recordPlayHistory = async (trackId) => {
    try {
      await api.post(`/history/${trackId}`);
    } catch (err) {
      console.error('Failed to record play history:', err);
    }
  };

  const playTrack = async (track, trackList = tracks, playlistId = null) => {
    const audio = audioRef.current;
    audio.src = streamUrl(track.id);
    
    try {
      await audio.play();
      setCurrentTrack(track);
      setQueue(trackList);
      setActivePlaylistId(playlistId);
      writePlayback({
        track: slimTrack(track),
        queue: (trackList.length ? trackList : [track]).map(slimTrack),
        currentTime: 0,
        isPlaying: true,
        playMode,
        volume,
        dismissed: false,
      });
      
      // Record to play history
      recordPlayHistory(track.id);
      
      // Update local play_count to reflect the increment from backend
      // This ensures Trending and Charts display accurate play counts
      setTracks(prevTracks => 
        prevTracks.map(t => 
          t.id === track.id 
            ? { ...t, play_count: t.play_count + 1 }
            : t
        )
      );
    } catch (err) {
      console.error('Play failed:', err);
    }
  };

  const togglePlay = () => { 
    if (isPlaying) audioRef.current.pause(); 
    else audioRef.current.play(); 
  };

  const playNext = () => {
    if (!currentTrack || queue.length === 0) return;
    const idx = queue.findIndex(t => t.id === currentTrack.id);
    
    let nextIdx;
    if (playMode === 'shuffle') {
      nextIdx = Math.floor(Math.random() * queue.length);
    } else if (playMode === 'repeat-all' || playMode === 'sequential') {
      nextIdx = (idx + 1) % queue.length;
    } else {
      nextIdx = idx + 1 < queue.length ? idx + 1 : idx;
    }
    
    if (nextIdx !== idx || playMode === 'repeat-all') {
      playTrack(queue[nextIdx], queue, activePlaylistId);
    }
  };

  const playPrev = () => {
    if (!currentTrack || queue.length === 0) return;
    const idx = queue.findIndex(t => t.id === currentTrack.id);
    const prevIdx = idx === 0 ? queue.length - 1 : idx - 1;
    playTrack(queue[prevIdx], queue, activePlaylistId);
  };

  const seekTo = (time) => {
    const audio = audioRef.current;
    const wasPlaying = !audio.paused;
    
    audio.currentTime = time;
    setCurrentTime(time);
    
    if (wasPlaying) {
      audio.play().catch(err => console.error('Play after seek failed:', err));
    }
  };

  const cyclePlayMode = () => {
    const modes = ['sequential', 'repeat-all', 'repeat-one', 'shuffle'];
    const currentIndex = modes.indexOf(playMode);
    const nextIndex = (currentIndex + 1) % modes.length;
    const newMode = modes[nextIndex];
    setPlayMode(newMode);
    localStorage.setItem('playMode', newMode);
  };

  const handleAddToPlaylist = async (playlistId, trackId) => {
    await api.post(`/playlists/${playlistId}/tracks/${trackId}`);
    fetchData();
  };

  const handleProfileUpdate = (updatedUser) => {
    if (updateUser) {
      updateUser(updatedUser);
    }
  };

  // Handle rating change - update local track popularity
  const handleRatingChange = (trackId, newRating, newPopularity) => {
    setTracks(prevTracks => 
      prevTracks.map(t => 
        t.id === trackId 
          ? { ...t, popularity_score: newPopularity }
          : t
      )
    );
    
    // Also update queue if the track is in it
    setQueue(prevQueue => 
      prevQueue.map(t => 
        t.id === trackId 
          ? { ...t, popularity_score: newPopularity }
          : t
      )
    );
    
    // Update current track if it's the one being rated
    if (currentTrack && currentTrack.id === trackId) {
      setCurrentTrack(prev => ({ ...prev, popularity_score: newPopularity }));
    }
  };

  const pendingCount = requests.filter(r => r.status === 'pending').length;

  if (loading) {
    return (
      <div className="h-screen w-full bg-zinc-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
      </div>
    );
  }

  return (
    <div className="h-screen w-full bg-gradient-to-br from-zinc-950 via-zinc-900 to-black text-white overflow-hidden flex">
      {/* Sidebar */}
      <Sidebar 
        currentPage={currentPage}
        setCurrentPage={setCurrentPage}
        pendingCount={pendingCount}
        onOpenProfileSettings={() => setShowProfileSettings(true)}
      />
      
      {/* Main Content */}
      <main className={`flex-1 flex flex-col overflow-hidden ${isMobile ? 'w-full' : ''}`}>
        <div className="flex-1 overflow-y-auto pt-14 md:pt-0">
          <AnimatePresence mode="wait">
            {currentPage === 'home' && (
              <HomePage 
                key="home" 
                tracks={tracks} 
                playlists={playlists}
                onPlay={(track) => playTrack(track, tracks, null)} 
                onAddToPlaylist={handleAddToPlaylist}
              />
            )}
            {currentPage === 'top' && (
              <TopPage 
                key="top" 
                tracks={tracks} 
                playlists={playlists}
                onPlay={(track, list) => playTrack(track, list, null)} 
                onAddToPlaylist={handleAddToPlaylist}
              />
            )}
            {currentPage === 'search' && (
              <SearchPage 
                key="search" 
                tracks={tracks} 
                playlists={playlists}
                onPlay={(track, list) => playTrack(track, list, null)} 
                onAddToPlaylist={handleAddToPlaylist}
              />
            )}
            {currentPage === 'library' && (
              <LibraryPage 
                key="library" 
                playlists={playlists} 
                setPlaylists={setPlaylists} 
                tracks={tracks} 
                onPlay={(track, list, playlistId) => playTrack(track, list, playlistId)}
                onRefresh={fetchData}
              />
            )}
            {currentPage === 'history' && (
              <HistoryPage 
                key="history"
                playlists={playlists}
                onPlay={(track, list) => playTrack(track, list, null)}
                onAddToPlaylist={handleAddToPlaylist}
              />
            )}
            {currentPage === 'requests' && (
              <RequestsPage 
                key="requests" 
                requests={requests} 
                setRequests={setRequests} 
                isAdmin={isAdmin} 
              />
            )}
            {currentPage === 'manage-music' && isAdmin && (
              <ManageMusicPage 
                key="manage" 
                tracks={tracks} 
                setTracks={setTracks} 
                onRefresh={fetchData} 
              />
            )}
            {currentPage === 'users' && isAdmin && (
              <UsersPage key="users" users={users} setUsers={setUsers} />
            )}
          </AnimatePresence>
        </div>
        
        {/* Mini Player */}
        {currentTrack && !isPlayerExpanded && (
          <MiniPlayer 
            track={currentTrack}
            isPlaying={isPlaying}
            currentTime={currentTime}
            duration={duration}
            volume={volume}
            isMuted={isMuted}
            playMode={playMode}
            leftBars={leftBars}
            rightBars={rightBars}
            playlists={playlists}
            onTogglePlay={togglePlay}
            onPrev={playPrev}
            onNext={playNext}
            onSeek={seekTo}
            onVolumeChange={setVolume}
            onMuteToggle={() => setIsMuted(!isMuted)}
            onPlayModeToggle={cyclePlayMode}
            onExpand={() => setIsPlayerExpanded(true)}
            onQueueToggle={() => setShowQueue(!showQueue)}
            onAddToPlaylist={handleAddToPlaylist}
            showQueue={showQueue}
            onRatingChange={handleRatingChange}
          />
        )}
      </main>
      
      {/* Full Player */}
      <AnimatePresence>
        {isPlayerExpanded && currentTrack && (
          <FullPlayer 
            track={currentTrack}
            isPlaying={isPlaying}
            currentTime={currentTime}
            duration={duration}
            playMode={playMode}
            leftBars={leftBars}
            rightBars={rightBars}
            playlists={playlists}
            onTogglePlay={togglePlay}
            onPrev={playPrev}
            onNext={playNext}
            onSeek={seekTo}
            onPlayModeToggle={cyclePlayMode}
            onCollapse={() => setIsPlayerExpanded(false)}
            onAddToPlaylist={handleAddToPlaylist}
          />
        )}
      </AnimatePresence>
      
      {/* Queue Panel */}
      <AnimatePresence>
        {showQueue && !isPlayerExpanded && (
          <QueuePanel 
            tracks={queue} 
            currentTrack={currentTrack} 
            onClose={() => setShowQueue(false)} 
            onPlay={(t) => playTrack(t, queue, activePlaylistId)} 
          />
        )}
      </AnimatePresence>

      {/* Profile Settings - Rendered at root level for proper centering */}
      <AnimatePresence>
        {showProfileSettings && user && (
          <ProfileSettings
            user={user}
            onClose={() => setShowProfileSettings(false)}
            onUpdate={handleProfileUpdate}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

function AppContent() {
  const { user, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="h-screen w-full bg-zinc-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
      </div>
    );
  }
  
  return user ? (
    <SidebarProvider>
      <RatingProvider>
        <MainApp />
      </RatingProvider>
    </SidebarProvider>
  ) : (
    <LoginPage />
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
