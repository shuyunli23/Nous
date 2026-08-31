import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Shield, Upload, RefreshCw, Trash2, Music, Edit2, X, 
  Folder, FolderPlus, ChevronRight, Home, Check, AlertCircle,
  MoreVertical, Pencil, FileAudio, Search, Move, ArrowRight
} from 'lucide-react';
import api from '../api/client';
import { formatPlayCount } from '../utils/helpers';
import { looksLikeLrc, shiftLrc } from '../utils/lrc';

/**
 * Helper function to parse error messages from API responses
 */
function parseErrorMessage(err, defaultMsg = 'An error occurred') {
  const detail = err.response?.data?.detail;
  
  if (typeof detail === 'string') {
    return detail;
  }
  
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map(e => e.msg).join(', ');
  }
  
  if (detail && typeof detail === 'object') {
    return detail.msg || detail.message || defaultMsg;
  }
  
  return err.message || defaultMsg;
}

// Edit Track Dialog Component
function EditTrackDialog({ track, onClose, onSave }) {
  const [formData, setFormData] = useState({
    title: track.title,
    artist: track.artist,
    album: track.album || ''
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [coverFile, setCoverFile] = useState(null);
  const [coverPreview, setCoverPreview] = useState(null);
  const [uploadingCover, setUploadingCover] = useState(false);
  const [coverSuccess, setCoverSuccess] = useState(false);
  const [lyricsFile, setLyricsFile] = useState(null);
  const [uploadingLyrics, setUploadingLyrics] = useState(false);
  const [lyricsSuccess, setLyricsSuccess] = useState(false);
  const [lyricsOffset, setLyricsOffset] = useState(0);

  const handleSave = async () => {
    if (!formData.title.trim() || !formData.artist.trim()) {
      setError('Title and artist cannot be empty');
      return;
    }

    setSaving(true);
    setError('');
    try {
      const data = new FormData();
      data.append('title', formData.title);
      data.append('artist', formData.artist);
      data.append('album', formData.album || '');
      
      await api.put(`/music/${track.id}`, data, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      onSave();
    } catch (err) {
      setError(parseErrorMessage(err, 'Failed to save'));
    } finally {
      setSaving(false);
    }
  };

  const handleCoverSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setCoverFile(file);
      const reader = new FileReader();
      reader.onloadend = () => setCoverPreview(reader.result);
      reader.readAsDataURL(file);
    }
  };

  const handleCoverUpload = async () => {
    if (!coverFile) return;
    setUploadingCover(true);
    setError('');
    try {
      const data = new FormData();
      data.append('cover', coverFile);
      await api.post(`/music/${track.id}/cover`, data, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setCoverSuccess(true);
      setCoverFile(null);
      setTimeout(() => setCoverSuccess(false), 2000);
    } catch (err) {
      setError(parseErrorMessage(err, 'Failed to upload cover'));
    } finally {
      setUploadingCover(false);
    }
  };

  const handleLyricsSelect = (e) => {
    const file = e.target.files[0];
    if (file) setLyricsFile(file);
  };

  const handleLyricsUpload = async () => {
    if (!lyricsFile) return;
    setUploadingLyrics(true);
    setError('');
    try {
      let body = await lyricsFile.text();
      if (lyricsOffset && looksLikeLrc(body)) {
        body = shiftLrc(body, lyricsOffset);
      }
      const data = new FormData();
      data.append('text', body);
      await api.post(`/music/${track.id}/lyrics`, data, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setLyricsSuccess(true);
      setLyricsFile(null);
      setLyricsOffset(0);
      setTimeout(() => setLyricsSuccess(false), 2000);
    } catch (err) {
      setError(parseErrorMessage(err, 'Failed to upload lyrics'));
    } finally {
      setUploadingLyrics(false);
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0 }} 
      animate={{ opacity: 1 }} 
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" 
      onClick={onClose}
    >
      <motion.div 
        initial={{ scale: 0.95, opacity: 0 }} 
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 w-full max-w-md max-h-[90vh] overflow-y-auto" 
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold">Edit Track Info</h2>
          <button 
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-500/20 border border-red-500/30 rounded-lg flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <p className="text-sm text-red-400">{error}</p>
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-zinc-400 mb-1">Title *</label>
            <input 
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className="w-full px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg focus:outline-none focus:border-amber-500"
              placeholder="Enter track title"
            />
          </div>

          <div>
            <label className="block text-sm text-zinc-400 mb-1">Artist *</label>
            <input 
              type="text"
              value={formData.artist}
              onChange={(e) => setFormData({ ...formData, artist: e.target.value })}
              className="w-full px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg focus:outline-none focus:border-amber-500"
              placeholder="Enter artist name"
            />
          </div>

          <div>
            <label className="block text-sm text-zinc-400 mb-1">Album</label>
            <input 
              type="text"
              value={formData.album}
              onChange={(e) => setFormData({ ...formData, album: e.target.value })}
              className="w-full px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg focus:outline-none focus:border-amber-500"
              placeholder="Enter album name (optional)"
            />
          </div>

          <div>
            <label className="block text-sm text-zinc-400 mb-1">File Path</label>
            <div className="flex items-center gap-2 px-4 py-2 bg-zinc-800/50 border border-zinc-700/50 rounded-lg text-zinc-500 text-sm">
              <FileAudio className="w-4 h-4 shrink-0" />
              <span className="truncate">{track.file_path}</span>
            </div>
          </div>

          {/* Cover Art Upload */}
          <div>
            <label className="block text-sm text-zinc-400 mb-1">Cover Art</label>
            <div className="flex items-center gap-3">
              {/* Current or preview cover */}
              <div className="w-16 h-16 rounded-lg overflow-hidden bg-zinc-800 border border-zinc-700 flex items-center justify-center shrink-0">
                {coverPreview ? (
                  <img src={coverPreview} alt="Preview" className="w-full h-full object-cover" />
                ) : track.cover_path ? (
                  <img 
                    src={`/api/music/${track.id}/cover?token=${encodeURIComponent(localStorage.getItem('token'))}`} 
                    alt="Cover" 
                    className="w-full h-full object-cover"
                    onError={(e) => { e.target.style.display = 'none'; }}
                  />
                ) : (
                  <Music className="w-6 h-6 text-zinc-600" />
                )}
              </div>
              
              <div className="flex-1 space-y-2">
                <label className="flex items-center gap-2 px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg cursor-pointer hover:border-amber-500 transition-colors text-sm">
                  <Upload className="w-4 h-4 text-zinc-400" />
                  <span className="text-zinc-300">{coverFile ? coverFile.name : (track.cover_path ? 'Replace cover' : 'Choose image')}</span>
                  <input 
                    type="file" 
                    accept="image/jpeg,image/png,image/webp,image/gif"
                    onChange={handleCoverSelect}
                    className="hidden"
                  />
                </label>
                {coverFile && (
                  <button
                    onClick={handleCoverUpload}
                    disabled={uploadingCover}
                    className="w-full px-3 py-1.5 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-500 disabled:opacity-50 transition-colors flex items-center justify-center gap-1"
                  >
                    {uploadingCover ? 'Uploading...' : coverSuccess ? '✓ Uploaded' : 'Upload Cover'}
                  </button>
                )}
                {!coverFile && coverSuccess && (
                  <p className="text-xs text-emerald-400">✓ Cover updated successfully</p>
                )}
              </div>
            </div>
          </div>

          <div>
            <label className="block text-sm text-zinc-400 mb-1">Lyrics</label>
            <p className="text-xs text-zinc-500 mb-2">
              Import a timed .lrc file or a .txt file. A .lrc next to the audio is also picked up on scan.
              If the lyrics are early or late, shift the timing before upload.
            </p>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs text-zinc-500">Timing</span>
              <button
                type="button"
                className="px-2 py-1 rounded-lg bg-zinc-800 border border-zinc-700 text-zinc-300 text-sm hover:border-amber-500 disabled:opacity-40"
                disabled={lyricsOffset <= -10}
                onClick={() => setLyricsOffset((v) => Math.round((v - 0.5) * 10) / 10)}
              >
                −
              </button>
              <span className="text-sm tabular-nums text-zinc-300 min-w-[3.5rem] text-center">
                {lyricsOffset === 0 ? '0.0s' : `${lyricsOffset > 0 ? '+' : ''}${lyricsOffset.toFixed(1)}s`}
              </span>
              <button
                type="button"
                className="px-2 py-1 rounded-lg bg-zinc-800 border border-zinc-700 text-zinc-300 text-sm hover:border-amber-500 disabled:opacity-40"
                disabled={lyricsOffset >= 10}
                onClick={() => setLyricsOffset((v) => Math.round((v + 0.5) * 10) / 10)}
              >
                +
              </button>
              <span className="text-[11px] text-zinc-600">+ delays, − earlier</span>
            </div>
            <label className="flex items-center gap-2 px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg cursor-pointer hover:border-amber-500 transition-colors text-sm">
              <Upload className="w-4 h-4 text-zinc-400" />
              <span className="text-zinc-300">{lyricsFile ? lyricsFile.name : 'Choose .lrc / .txt'}</span>
              <input
                type="file"
                accept=".lrc,.txt,text/plain"
                onChange={handleLyricsSelect}
                className="hidden"
              />
            </label>
            {lyricsFile && (
              <button
                type="button"
                onClick={handleLyricsUpload}
                disabled={uploadingLyrics}
                className="w-full mt-2 px-3 py-1.5 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-500 disabled:opacity-50 transition-colors"
              >
                {uploadingLyrics ? 'Uploading...' : lyricsSuccess ? '✓ Uploaded' : 'Upload lyrics'}
              </button>
            )}
            {!lyricsFile && lyricsSuccess && (
              <p className="text-xs text-emerald-400 mt-2">✓ Lyrics updated</p>
            )}
          </div>

          <div className="flex gap-3 pt-2">
            <button 
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-zinc-700 rounded-lg hover:bg-zinc-800 transition-colors"
            >
              Cancel
            </button>
            <button 
              onClick={handleSave}
              disabled={saving}
              className="flex-1 px-4 py-2 bg-amber-500 text-black font-medium rounded-lg hover:bg-amber-400 disabled:opacity-50 transition-colors"
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

// Rename Dialog Component
function RenameDialog({ type, name, onClose, onSave }) {
  const [newName, setNewName] = useState(name);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSave = async () => {
    if (!newName.trim()) {
      setError('Name cannot be empty');
      return;
    }
    if (newName === name) {
      onClose();
      return;
    }

    setSaving(true);
    setError('');
    try {
      await onSave(newName);
    } catch (err) {
      setError(parseErrorMessage(err, 'Failed to rename'));
      setSaving(false);
    }
  };

  const handleBackdropClick = (e) => {
    e.stopPropagation();
    onClose();
  };

  return (
    <motion.div 
      initial={{ opacity: 0 }} 
      animate={{ opacity: 1 }} 
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60] flex items-center justify-center p-4" 
      onClick={handleBackdropClick}
    >
      <motion.div 
        initial={{ scale: 0.95, opacity: 0 }} 
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 w-full max-w-md" 
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold">Rename {type === 'directory' ? 'Folder' : 'File'}</h2>
          <button 
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-500/20 border border-red-500/30 rounded-lg flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <p className="text-sm text-red-400">{error}</p>
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-zinc-400 mb-1">New Name</label>
            <input 
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="w-full px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg focus:outline-none focus:border-amber-500"
              placeholder={`Enter new ${type === 'directory' ? 'folder' : 'file'} name`}
              autoFocus
              onKeyDown={(e) => e.key === 'Enter' && handleSave()}
            />
          </div>

          <div className="flex gap-3 pt-2">
            <button 
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-zinc-700 rounded-lg hover:bg-zinc-800 transition-colors"
            >
              Cancel
            </button>
            <button 
              onClick={handleSave}
              disabled={saving}
              className="flex-1 px-4 py-2 bg-amber-500 text-black font-medium rounded-lg hover:bg-amber-400 disabled:opacity-50 transition-colors"
            >
              {saving ? 'Saving...' : 'Rename'}
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

// Move Dialog Component
function MoveDialog({ type, item, directories, currentPath, onClose, onMove, onRefreshDirectories }) {
  const [selectedPath, setSelectedPath] = useState('');
  const [browsePath, setBrowsePath] = useState('');
  const [browseDirectories, setBrowseDirectories] = useState(directories);
  const [moving, setMoving] = useState(false);
  const [error, setError] = useState('');

  const loadDirectories = async (path) => {
    try {
      const res = await api.get('/music/directories', { params: { current_path: path } });
      setBrowseDirectories(res.data);
      setBrowsePath(path);
    } catch (err) {
      setError('Failed to load directories');
    }
  };

  const handleMove = async () => {
    if (selectedPath === currentPath) {
      setError('Cannot move to the same location');
      return;
    }

    setMoving(true);
    setError('');
    try {
      await onMove(selectedPath);
    } catch (err) {
      setError(parseErrorMessage(err, 'Failed to move'));
      setMoving(false);
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0 }} 
      animate={{ opacity: 1 }} 
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60] flex items-center justify-center p-4" 
      onClick={onClose}
    >
      <motion.div 
        initial={{ scale: 0.95, opacity: 0 }} 
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 w-full max-w-md" 
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Move className="w-5 h-5 text-blue-400" />
            <h2 className="text-xl font-bold">Move {type === 'directory' ? 'Folder' : 'File'}</h2>
          </div>
          <button 
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-500/20 border border-red-500/30 rounded-lg flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <p className="text-sm text-red-400">{error}</p>
          </div>
        )}

        {/* Current location */}
        <div className="mb-4 p-3 bg-zinc-800/50 rounded-lg">
          <p className="text-xs text-zinc-400 mb-1">Current Location</p>
          <p className="text-sm font-medium truncate">{item.name}</p>
          <p className="text-xs text-zinc-500">in: /{currentPath || 'Music'}</p>
        </div>

        {/* Destination selector */}
        <div className="mb-4">
          <p className="text-sm text-zinc-400 mb-2">Select Destination</p>
          
          {/* Breadcrumb */}
          <div className="flex items-center gap-2 mb-2 text-sm text-zinc-400 flex-wrap">
            <button 
              onClick={() => loadDirectories('')}
              className="hover:text-white transition-colors"
            >
              <Home className="w-4 h-4" />
            </button>
            <span>/</span>
            {browsePath && (
              <>
                {browsePath.split('/').map((part, i, arr) => (
                  <React.Fragment key={i}>
                    <ChevronRight className="w-3 h-3" />
                    <button
                      onClick={() => loadDirectories(arr.slice(0, i + 1).join('/'))}
                      className={`hover:text-white transition-colors ${i === arr.length - 1 ? 'text-white' : ''}`}
                    >
                      {part}
                    </button>
                  </React.Fragment>
                ))}
              </>
            )}
          </div>

          {/* Directory list */}
          <div className="max-h-64 overflow-y-auto border border-zinc-700 rounded-lg">
            {/* Current directory option */}
            <button
              onClick={() => setSelectedPath(browsePath)}
              className={`w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-zinc-700 transition-colors ${
                selectedPath === browsePath ? 'bg-blue-500/20 text-blue-400' : ''
              }`}
            >
              <Folder className="w-4 h-4 text-blue-400" />
              <span className="text-sm flex-1">{browsePath ? 'This folder' : 'Music (root)'}</span>
              {selectedPath === browsePath && <Check className="w-4 h-4" />}
            </button>

            {/* Parent directory */}
            {browseDirectories?.parent_path !== null && (
              <button
                onClick={() => loadDirectories(browseDirectories.parent_path || '')}
                className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-zinc-700 transition-colors"
              >
                <Folder className="w-4 h-4 text-blue-400" />
                <span className="text-sm">..</span>
              </button>
            )}
            
            {/* Subdirectories */}
            {browseDirectories?.items
              .filter(item => item.type === 'directory')
              .map(dir => (
                <button
                  key={dir.path}
                  onClick={() => loadDirectories(dir.path)}
                  className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-zinc-700 transition-colors"
                >
                  <Folder className="w-4 h-4 text-blue-400" />
                  <span className="text-sm flex-1">{dir.name}</span>
                  <ChevronRight className="w-4 h-4 text-zinc-500" />
                </button>
              ))}

            {browseDirectories?.items.filter(item => item.type === 'directory').length === 0 && 
             browseDirectories?.parent_path === null && (
              <div className="text-center py-4 text-sm text-zinc-500">
                No subfolders
              </div>
            )}
          </div>
        </div>

        {/* Selected destination */}
        {selectedPath !== '' && (
          <div className="mb-4 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
            <div className="flex items-center gap-2 text-sm">
              <ArrowRight className="w-4 h-4 text-blue-400" />
              <span className="text-blue-400">Move to: /{selectedPath || 'Music'}</span>
            </div>
          </div>
        )}

        <div className="flex gap-3">
          <button 
            onClick={onClose}
            className="flex-1 px-4 py-2 border border-zinc-700 rounded-lg hover:bg-zinc-800 transition-colors"
          >
            Cancel
          </button>
          <button 
            onClick={handleMove}
            disabled={moving || selectedPath === ''}
            className="flex-1 px-4 py-2 bg-blue-500 text-white font-medium rounded-lg hover:bg-blue-400 disabled:opacity-50 transition-colors"
          >
            {moving ? 'Moving...' : 'Move Here'}
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

// Context Menu Component
function ContextMenu({ item, position, onClose, onRename, onDelete, onMove }) {
  const handleBackdropClick = (e) => {
    e.stopPropagation();
    onClose();
  };

  const handleRenameClick = (e) => {
    e.stopPropagation();
    onRename();
    onClose();
  };

  const handleMoveClick = (e) => {
    e.stopPropagation();
    onMove();
    onClose();
  };

  const handleDeleteClick = (e) => {
    e.stopPropagation();
    onDelete();
    onClose();
  };

  return (
    <>
      <div 
        className="fixed inset-0 z-[55]" 
        onClick={handleBackdropClick} 
      />
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="fixed z-[56] bg-zinc-800 border border-zinc-700 rounded-lg shadow-xl py-1 min-w-[140px]"
        style={{ top: position.y, left: position.x }}
        onClick={e => e.stopPropagation()}
      >
        <button
          onClick={handleRenameClick}
          className="w-full px-4 py-2 text-left text-sm hover:bg-zinc-700 flex items-center gap-2 transition-colors"
        >
          <Pencil className="w-4 h-4" />
          Rename
        </button>
        <button
          onClick={handleMoveClick}
          className="w-full px-4 py-2 text-left text-sm hover:bg-zinc-700 flex items-center gap-2 transition-colors text-blue-400"
        >
          <Move className="w-4 h-4" />
          Move
        </button>
        <button
          onClick={handleDeleteClick}
          className="w-full px-4 py-2 text-left text-sm text-red-400 hover:bg-zinc-700 flex items-center gap-2 transition-colors"
        >
          <Trash2 className="w-4 h-4" />
          Delete
        </button>
      </motion.div>
    </>
  );
}

// Batch Upload Dialog Component
function BatchUploadDialog({ onClose, onSuccess }) {
  const [currentPath, setCurrentPath] = useState('');
  const [directories, setDirectories] = useState(null);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadResults, setUploadResults] = useState(null);
  const [showCreateDir, setShowCreateDir] = useState(false);
  const [newDirName, setNewDirName] = useState('');
  const [createDirError, setCreateDirError] = useState('');
  const [contextMenu, setContextMenu] = useState(null);
  const [renameItem, setRenameItem] = useState(null);
  const [moveItem, setMoveItem] = useState(null);
  const [notification, setNotification] = useState(null);

  const showNotification = (message, type = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 3000);
  };

  React.useEffect(() => {
    loadDirectories(currentPath);
  }, [currentPath]);

  const loadDirectories = async (path) => {
    try {
      const res = await api.get('/music/directories', { params: { current_path: path } });
      setDirectories(res.data);
    } catch (err) {
      console.error('Failed to load directories:', err);
    }
  };

  const handleCreateDirectory = async () => {
    if (!newDirName.trim()) return;
    setCreateDirError('');
    
    try {
      const formData = new FormData();
      formData.append('path', currentPath);
      formData.append('name', newDirName);
      
      await api.post('/music/directories', formData);
      setNewDirName('');
      setShowCreateDir(false);
      loadDirectories(currentPath);
      showNotification('Folder created successfully');
    } catch (err) {
      const message = parseErrorMessage(err, 'Failed to create directory');
      setCreateDirError(message);
    }
  };

  const handleContextMenu = (e, item) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({
      item,
      position: { x: Math.min(e.clientX, window.innerWidth - 160), y: e.clientY }
    });
  };

  const handleMoreClick = (e, item) => {
    e.preventDefault();
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    setContextMenu({
      item,
      position: { x: Math.min(rect.left, window.innerWidth - 160), y: rect.bottom + 4 }
    });
  };

  const handleRename = async (newName) => {
    if (!renameItem) return;
    
    const formData = new FormData();
    formData.append('path', renameItem.path);
    formData.append('new_name', newName);
    
    if (renameItem.type === 'directory') {
      await api.put('/music/directories/rename', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
    } else {
      await api.put('/music/files/rename', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
    }
    
    setRenameItem(null);
    loadDirectories(currentPath);
    onSuccess();
    showNotification(`${renameItem.type === 'directory' ? 'Folder' : 'File'} renamed successfully`);
  };

  const handleMove = async (destinationPath) => {
    if (!moveItem) return;

    const formData = new FormData();
    formData.append('source_path', moveItem.path);
    formData.append('destination_path', destinationPath);

    try {
      if (moveItem.type === 'directory') {
        await api.put('/music/directories/move', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
      } else {
        await api.put('/music/files/move', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
      }

      setMoveItem(null);
      loadDirectories(currentPath);
      onSuccess();
      showNotification(`${moveItem.type === 'directory' ? 'Folder' : 'File'} moved successfully`);
    } catch (err) {
      throw err;
    }
  };

  const handleDelete = async (item) => {
    const typeLabel = item.type === 'directory' ? 'folder' : 'file';
    const warning = item.type === 'directory' 
      ? 'This will delete the folder and all its contents including any music files inside.'
      : 'This will permanently delete this file.';
    
    if (!confirm(`Delete ${typeLabel} "${item.name}"?\n\n${warning}`)) return;
    
    try {
      if (item.type === 'directory') {
        await api.delete('/music/directories', { params: { path: item.path } });
      } else {
        await api.delete('/music/files', { params: { path: item.path } });
      }
      loadDirectories(currentPath);
      onSuccess();
      showNotification(`${typeLabel.charAt(0).toUpperCase() + typeLabel.slice(1)} deleted successfully`);
    } catch (err) {
      showNotification(parseErrorMessage(err, `Failed to delete ${typeLabel}`), 'error');
    }
  };

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    setSelectedFiles(files);
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return;

    setUploading(true);
    setUploadResults(null);

    try {
      const formData = new FormData();
      selectedFiles.forEach(file => {
        formData.append('files', file);
      });
      formData.append('directory', currentPath);

      const res = await api.post('/music/batch-upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      setUploadResults(res.data);
      setSelectedFiles([]);
      loadDirectories(currentPath);
      
      if (res.data.success.length > 0) {
        setTimeout(() => {
          onSuccess();
        }, 2000);
      }
    } catch (err) {
      const message = parseErrorMessage(err, 'Upload failed');
      showNotification(message, 'error');
    } finally {
      setUploading(false);
    }
  };

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0 }} 
      animate={{ opacity: 1 }} 
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" 
      onClick={handleBackdropClick}
    >
      <motion.div 
        initial={{ scale: 0.95, opacity: 0 }} 
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 w-full max-w-3xl max-h-[80vh] flex flex-col" 
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold">Batch Import Music</h2>
          <button 
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Notification */}
        <AnimatePresence>
          {notification && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className={`mb-4 p-3 rounded-lg flex items-center gap-2 ${
                notification.type === 'error' 
                  ? 'bg-red-500/20 border border-red-500/30 text-red-400'
                  : 'bg-emerald-500/20 border border-emerald-500/30 text-emerald-400'
              }`}
            >
              {notification.type === 'error' ? (
                <AlertCircle className="w-4 h-4" />
              ) : (
                <Check className="w-4 h-4" />
              )}
              <span className="text-sm">{notification.message}</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Directory Browser */}
        <div className="mb-4 p-4 bg-zinc-800/50 rounded-xl">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2 text-sm text-zinc-400 flex-wrap">
              <button 
                onClick={() => setCurrentPath('')}
                className="hover:text-white transition-colors"
              >
                <Home className="w-4 h-4" />
              </button>
              <span>/</span>
              {currentPath && (
                <>
                  {currentPath.split('/').map((part, i, arr) => (
                    <React.Fragment key={i}>
                      <ChevronRight className="w-3 h-3" />
                      <button
                        onClick={() => setCurrentPath(arr.slice(0, i + 1).join('/'))}
                        className={`hover:text-white transition-colors ${i === arr.length - 1 ? 'text-white' : ''}`}
                      >
                        {part}
                      </button>
                    </React.Fragment>
                  ))}
                </>
              )}
            </div>
            <button
              onClick={() => {
                setShowCreateDir(!showCreateDir);
                setCreateDirError('');
              }}
              className="flex items-center gap-2 px-3 py-1.5 bg-zinc-700 hover:bg-zinc-600 rounded-lg text-sm transition-colors shrink-0"
            >
              <FolderPlus className="w-4 h-4" />
              New Folder
            </button>
          </div>

          {showCreateDir && (
            <div className="mb-3">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newDirName}
                  onChange={(e) => setNewDirName(e.target.value)}
                  placeholder="Enter folder name"
                  className="flex-1 px-3 py-2 bg-zinc-700 border border-zinc-600 rounded-lg text-sm focus:outline-none focus:border-amber-500"
                  onKeyDown={(e) => e.key === 'Enter' && handleCreateDirectory()}
                  autoFocus
                />
                <button
                  onClick={handleCreateDirectory}
                  className="px-4 py-2 bg-amber-500 text-black rounded-lg hover:bg-amber-400 transition-colors"
                >
                  Create
                </button>
                <button
                  onClick={() => { setShowCreateDir(false); setNewDirName(''); setCreateDirError(''); }}
                  className="px-4 py-2 border border-zinc-600 rounded-lg hover:bg-zinc-700 transition-colors"
                >
                  Cancel
                </button>
              </div>
              {createDirError && (
                <p className="mt-2 text-sm text-red-400 flex items-center gap-1">
                  <AlertCircle className="w-4 h-4" />
                  {createDirError}
                </p>
              )}
            </div>
          )}

          <div className="max-h-48 overflow-y-auto space-y-1">
            {directories?.parent_path !== null && (
              <button
                onClick={() => setCurrentPath(directories.parent_path || '')}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-zinc-700 transition-colors text-left"
              >
                <Folder className="w-4 h-4 text-blue-400" />
                <span className="text-sm">..</span>
              </button>
            )}
            
            {directories?.items.filter(item => item.type === 'directory').map(item => (
              <div
                key={item.path}
                className="group flex items-center rounded-lg hover:bg-zinc-700 transition-colors"
                onContextMenu={(e) => handleContextMenu(e, item)}
              >
                <button
                  onClick={() => setCurrentPath(item.path)}
                  className="flex-1 flex items-center gap-2 px-3 py-2 text-left"
                >
                  <Folder className="w-4 h-4 text-blue-400" />
                  <span className="text-sm">{item.name}</span>
                </button>
                <button
                  onClick={(e) => handleMoreClick(e, item)}
                  className="p-2 opacity-0 group-hover:opacity-100 hover:bg-zinc-600 rounded transition-all mr-1"
                >
                  <MoreVertical className="w-4 h-4" />
                </button>
              </div>
            ))}

            {directories?.items.filter(item => item.type === 'file').map(item => (
              <div
                key={item.path}
                className="group flex items-center px-3 py-2 text-zinc-400 rounded-lg hover:bg-zinc-700/50 transition-colors"
                onContextMenu={(e) => handleContextMenu(e, item)}
              >
                <Music className="w-4 h-4 mr-2 shrink-0" />
                <span className="text-sm flex-1 truncate">{item.name}</span>
                <button
                  onClick={(e) => handleMoreClick(e, item)}
                  className="p-1 opacity-0 group-hover:opacity-100 hover:bg-zinc-600 rounded transition-all shrink-0"
                >
                  <MoreVertical className="w-4 h-4" />
                </button>
              </div>
            ))}

            {directories?.items.length === 0 && (
              <div className="text-center py-4 text-zinc-500 text-sm">
                Empty folder
              </div>
            )}
          </div>
        </div>

        {/* File Selection */}
        <div className="mb-4">
          <label className="block text-sm text-zinc-400 mb-2">Select Music Files</label>
          <input
            type="file"
            multiple
            accept=".mp3,.flac,.wav,.m4a,.ogg,.aac,.wma"
            onChange={handleFileSelect}
            className="w-full px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:bg-amber-500 file:text-black file:cursor-pointer hover:file:bg-amber-400"
          />
          {selectedFiles.length > 0 && (
            <p className="mt-2 text-sm text-zinc-400">
              {selectedFiles.length} file{selectedFiles.length > 1 ? 's' : ''} selected
            </p>
          )}
        </div>

        {/* Upload Results */}
        <AnimatePresence>
          {uploadResults && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="mb-4 p-4 bg-zinc-800/50 rounded-xl space-y-2 max-h-48 overflow-y-auto"
            >
              {uploadResults.success.length > 0 && (
                <div className="flex items-start gap-2 text-emerald-400 text-sm">
                  <Check className="w-4 h-4 mt-0.5 shrink-0" />
                  <div>
                    <p className="font-medium">Successfully imported {uploadResults.success.length} track{uploadResults.success.length > 1 ? 's' : ''}</p>
                    {uploadResults.success.slice(0, 3).map((item, i) => (
                      <p key={i} className="text-xs text-zinc-400">
                        • {item.title} - {item.artist}
                      </p>
                    ))}
                    {uploadResults.success.length > 3 && (
                      <p className="text-xs text-zinc-500">
                        ...and {uploadResults.success.length - 3} more
                      </p>
                    )}
                  </div>
                </div>
              )}
              
              {uploadResults.duplicate.length > 0 && (
                <div className="flex items-start gap-2 text-amber-400 text-sm">
                  <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                  <div>
                    <p className="font-medium">Skipped {uploadResults.duplicate.length} duplicate{uploadResults.duplicate.length > 1 ? 's' : ''}</p>
                  </div>
                </div>
              )}
              
              {uploadResults.failed.length > 0 && (
                <div className="flex items-start gap-2 text-red-400 text-sm">
                  <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                  <div>
                    <p className="font-medium">{uploadResults.failed.length} failed</p>
                    {uploadResults.failed.slice(0, 3).map((item, i) => (
                      <p key={i} className="text-xs text-zinc-400">
                        • {item.filename}: {item.reason}
                      </p>
                    ))}
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Action Buttons */}
        <div className="flex gap-3 mt-auto">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 border border-zinc-700 rounded-lg hover:bg-zinc-800 transition-colors"
          >
            Close
          </button>
          <button
            onClick={handleUpload}
            disabled={uploading || selectedFiles.length === 0}
            className="flex-1 px-4 py-2 bg-amber-500 text-black font-medium rounded-lg hover:bg-amber-400 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
          >
            {uploading && <RefreshCw className="w-4 h-4 animate-spin" />}
            {uploading ? 'Uploading...' : `Upload ${selectedFiles.length || 0} file${selectedFiles.length !== 1 ? 's' : ''}`}
          </button>
        </div>
      </motion.div>

      {/* Context Menu */}
      <AnimatePresence>
        {contextMenu && (
          <ContextMenu
            item={contextMenu.item}
            position={contextMenu.position}
            onClose={() => setContextMenu(null)}
            onRename={() => setRenameItem(contextMenu.item)}
            onMove={() => setMoveItem(contextMenu.item)}
            onDelete={() => handleDelete(contextMenu.item)}
          />
        )}
      </AnimatePresence>

      {/* Rename Dialog */}
      <AnimatePresence>
        {renameItem && (
          <RenameDialog
            type={renameItem.type}
            name={renameItem.name}
            onClose={() => setRenameItem(null)}
            onSave={handleRename}
          />
        )}
      </AnimatePresence>

      {/* Move Dialog */}
      <AnimatePresence>
        {moveItem && (
          <MoveDialog
            type={moveItem.type}
            item={moveItem}
            directories={directories}
            currentPath={currentPath}
            onClose={() => setMoveItem(null)}
            onMove={handleMove}
            onRefreshDirectories={loadDirectories}
          />
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function ManageMusicPage({ tracks, setTracks, onRefresh }) {
  const [scanning, setScanning] = useState(false);
  const [editingTrack, setEditingTrack] = useState(null);
  const [showBatchUpload, setShowBatchUpload] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showGarbledOnly, setShowGarbledOnly] = useState(false);

  // Replace the existing filteredTracks useMemo with this:
  const filteredTracks = useMemo(() => {
    let filtered = tracks;
    
    // 搜索过滤（如果有搜索词）
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(track => 
        track.title.toLowerCase().includes(query) ||
        track.artist.toLowerCase().includes(query) ||
        (track.album && track.album.toLowerCase().includes(query)) ||
        track.file_path.toLowerCase().includes(query)
      );
    }
    
    // 乱码过滤（独立于搜索）
    if (showGarbledOnly) {
      filtered = filtered.filter(track => {
        const filename = track.file_path.split('/').pop()?.toLowerCase() || '';
        const titleChars = new Set(track.title.toLowerCase());
        const artistChars = new Set(track.artist.toLowerCase());
        const filenameChars = new Set(filename.toLowerCase());
        
        const titleCommon = [...titleChars].some(c => filenameChars.has(c));
        const artistCommon = [...artistChars].some(c => filenameChars.has(c));
        
        return !titleCommon || !artistCommon;
      });
    }
    
    return filtered;
  }, [tracks, searchQuery, showGarbledOnly]);
  const garbledCount = useMemo(() => {
    return tracks.filter(track => {
      const filename = track.file_path.split('/').pop()?.toLowerCase() || '';
      const titleChars = new Set(track.title.toLowerCase());
      const artistChars = new Set(track.artist.toLowerCase());
      const filenameChars = new Set(filename.toLowerCase());
      
      const titleCommon = [...titleChars].some(c => filenameChars.has(c));
      const artistCommon = [...artistChars].some(c => filenameChars.has(c));
      
      return !titleCommon || !artistCommon;
    }).length;
  }, [tracks]);

  const scanMusic = async () => {
    setScanning(true);
    try {
      await api.post('/music/scan');
      onRefresh();
    } catch (err) {
      console.error(err);
    } finally {
      setScanning(false);
    }
  };

  const deleteTrack = async (id) => {
    if (!confirm('Are you sure you want to delete this track?')) return;
    try {
      await api.delete(`/music/${id}?delete_file=true`);
      setTracks(tracks.filter(t => t.id !== id));
    } catch (err) {
      const message = parseErrorMessage(err, 'Failed to delete track');
      alert(message);
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }} 
      animate={{ opacity: 1, y: 0 }} 
      exit={{ opacity: 0 }} 
      className="p-4 md:p-8"
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-6">
        <Shield className="w-5 h-5 text-amber-400" />
        <h1 className="text-xl md:text-2xl font-bold">Music Manager</h1>
        <span className="px-2 py-0.5 rounded-full text-xs bg-amber-500/20 text-amber-400">Admin</span>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-3 mb-6">
        <button
          onClick={() => setShowBatchUpload(true)}
          className="flex items-center gap-2 px-4 py-2 bg-amber-500 text-black font-medium rounded-lg hover:bg-amber-400 transition-colors"
        >
          <Upload className="w-4 h-4" />
          Batch Import
        </button>
        <button
          onClick={scanMusic}
          disabled={scanning}
          className="flex items-center gap-2 px-4 py-2 bg-zinc-700 text-white font-medium rounded-lg hover:bg-zinc-600 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${scanning ? 'animate-spin' : ''}`} />
          {scanning ? 'Scanning...' : 'Scan Directory'}
        </button>
        <button
          onClick={() => setShowGarbledOnly(!showGarbledOnly)}
          className={`flex items-center gap-2 px-4 py-2 font-medium rounded-lg transition-all ${
            showGarbledOnly
              ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
              : 'bg-zinc-700 text-white hover:bg-zinc-600'
          }`}
        >
          <AlertCircle className="w-4 h-4" />
          <span>{showGarbledOnly ? 'Show All' : 'Filter Garbled'}</span>
          {garbledCount > 0 && (
            <span className="px-2 py-0.5 rounded-full text-xs bg-amber-500 text-black font-bold">
              {garbledCount}
            </span>
          )}
        </button>
      </div>

      <p className="text-sm text-zinc-500 mb-6">
        Place music files in the <code className="bg-zinc-800 px-2 py-1 rounded">Music</code> folder and click "Scan Directory" to auto-import
      </p>

      {/* Search Input */}
      <div className="mb-6">
        <div className="relative max-w-md">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-400" />
          <input 
            type="text" 
            placeholder="Search tracks by title, artist, album, or file path..." 
            value={searchQuery} 
            onChange={(e) => setSearchQuery(e.target.value)} 
            className="w-full h-11 pl-12 pr-4 bg-zinc-800/50 border border-zinc-700/50 rounded-xl text-sm focus:outline-none focus:border-amber-500/50 transition-colors" 
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 p-1 hover:bg-zinc-700 rounded-full transition-colors"
            >
              <X className="w-4 h-4 text-zinc-400" />
            </button>
          )}
        </div>
        {(searchQuery || showGarbledOnly) && (
          <p className="mt-2 text-sm text-zinc-500">
            {showGarbledOnly && !searchQuery && `Showing ${filteredTracks.length} garbled track${filteredTracks.length !== 1 ? 's' : ''}`}
            {showGarbledOnly && searchQuery && `Found ${filteredTracks.length} garbled track${filteredTracks.length !== 1 ? 's' : ''} matching "${searchQuery}"`}
            {!showGarbledOnly && searchQuery && `Found ${filteredTracks.length} track${filteredTracks.length !== 1 ? 's' : ''}`}
          </p>
        )}
      </div>

      {/* Tracks table */}
      <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl overflow-hidden">
        {!searchQuery && !showGarbledOnly ? (
          <div className="text-center py-12">
            <Music className="w-12 h-12 mx-auto mb-4 text-zinc-600" />
            <p className="text-zinc-400 mb-2">All tracks loaded</p>
            <p className="text-zinc-500 text-sm">Use search or filter to find specific tracks</p>
          </div>
        ) : filteredTracks.length === 0 ? (
          <div className="text-center py-12">
            <AlertCircle className="w-12 h-12 mx-auto mb-4 text-zinc-600" />
            <p className="text-zinc-400">
              {showGarbledOnly ? 'No garbled tracks found' : `No tracks found for "${searchQuery}"`}
            </p>
            <button 
              onClick={() => {
                setSearchQuery('');
                setShowGarbledOnly(false);
              }}
              className="mt-2 text-amber-400 hover:text-amber-300 text-sm"
            >
              Clear filters
            </button>
          </div>
        ) : (
          <>
            {/* Desktop table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-zinc-800">
                    <th className="px-4 py-4 text-left text-sm font-medium text-zinc-400">Track</th>
                    <th className="px-4 py-4 text-left text-sm font-medium text-zinc-400">Artist</th>
                    <th className="px-4 py-4 text-left text-sm font-medium text-zinc-400">Album</th>
                    <th className="px-4 py-4 text-left text-sm font-medium text-zinc-400">File Path</th>
                    <th className="px-4 py-4 text-right text-sm font-medium text-zinc-400">Plays</th>
                    <th className="px-4 py-4 text-right text-sm font-medium text-zinc-400">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTracks.map(track => (
                    <tr key={track.id} className="border-b border-zinc-800/50 hover:bg-white/5 transition-colors">
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded bg-zinc-800 flex items-center justify-center shrink-0">
                            <Music className="w-4 h-4 text-zinc-600" />
                          </div>
                          <span className="font-medium truncate max-w-[150px]" title={track.title}>
                            {track.title}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-4 text-zinc-400">
                        <span className="truncate block max-w-[120px]" title={track.artist}>
                          {track.artist}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-zinc-400">
                        <span className="truncate block max-w-[120px]" title={track.album || '-'}>
                          {track.album || '-'}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        <div 
                          className="flex items-center gap-2 text-zinc-500 text-sm max-w-[200px]"
                          title={track.file_path}
                        >
                          <FileAudio className="w-4 h-4 shrink-0 text-zinc-600" />
                          <span className="truncate">{track.file_path}</span>
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-3">
                          {/* ADD GARBLED INDICATOR */}
                          {(() => {
                            const filename = track.file_path.split('/').pop().toLowerCase();
                            const titleChars = new Set(track.title.toLowerCase());
                            const filenameChars = new Set(filename.toLowerCase());
                            const hasCommon = [...titleChars].some(c => filenameChars.has(c));
                            const isGarbled = !hasCommon;
                            
                            return isGarbled && (
                              <div 
                                className="w-2 h-2 rounded-full bg-amber-500 animate-pulse shrink-0" 
                                title="Garbled metadata detected"
                              />
                            );
                          })()}
                          
                          <div className="w-10 h-10 rounded bg-zinc-800 flex items-center justify-center shrink-0">
                            <Music className="w-4 h-4 text-zinc-600" />
                          </div>
                          <span className="font-medium truncate max-w-[150px]" title={track.title}>
                            {track.title}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-4 text-right text-zinc-400">
                        {formatPlayCount(track.play_count)}
                      </td>
                      <td className="px-4 py-4 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => setEditingTrack(track)}
                            className="p-2 rounded-lg text-amber-400 hover:bg-amber-500/20 transition-colors"
                            title="Edit"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => deleteTrack(track.id)}
                            className="p-2 rounded-lg text-red-400 hover:bg-red-500/20 transition-colors"
                            title="Delete"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile list */}
            <div className="md:hidden divide-y divide-zinc-800">
              {filteredTracks.map(track => (
                <div key={track.id} className="p-4">
                  <div className="flex items-start gap-3 mb-3">
                    <div className="w-10 h-10 rounded bg-zinc-800 flex items-center justify-center shrink-0">
                      <Music className="w-4 h-4 text-zinc-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{track.title}</p>
                      <p className="text-sm text-zinc-400 truncate">{track.artist}</p>
                      {track.album && (
                        <p className="text-xs text-zinc-500 truncate">{track.album}</p>
                      )}
                    </div>
                  </div>
                  
                  <div className="mb-3 p-2 bg-zinc-800/50 rounded-lg">
                    <div className="flex items-center gap-2 text-zinc-500 text-xs">
                      <FileAudio className="w-3 h-3 shrink-0" />
                      <span className="truncate">{track.file_path}</span>
                    </div>
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-zinc-500">
                      {formatPlayCount(track.play_count)} plays
                    </p>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setEditingTrack(track)}
                        className="flex items-center justify-center gap-2 px-3 py-1.5 bg-amber-500/20 text-amber-400 rounded-lg hover:bg-amber-500/30 transition-colors text-sm"
                      >
                        <Edit2 className="w-3 h-3" />
                        Edit
                      </button>
                      <button
                        onClick={() => deleteTrack(track.id)}
                        className="flex items-center justify-center gap-2 px-3 py-1.5 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-colors text-sm"
                      >
                        <Trash2 className="w-3 h-3" />
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Edit Dialog */}
      <AnimatePresence>
        {editingTrack && (
          <EditTrackDialog
            track={editingTrack}
            onClose={() => setEditingTrack(null)}
            onSave={() => {
              setEditingTrack(null);
              onRefresh();
            }}
          />
        )}
      </AnimatePresence>

      {/* Batch Upload Dialog */}
      <AnimatePresence>
        {showBatchUpload && (
          <BatchUploadDialog
            onClose={() => setShowBatchUpload(false)}
            onSuccess={() => {
              onRefresh();
            }}
          />
        )}
      </AnimatePresence>
    </motion.div>
  );
}