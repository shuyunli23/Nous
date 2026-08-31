# Harmony Music Player v2.1.0

A modern, responsive music player with user management, playlists, and admin features.

## ✨ What's New in v2.1.0

- **🔧 Modular Code Structure** - Backend and frontend code has been split into logical modules for better maintainability
- **🎨 Audio Visualization** - Dynamic visualizer bars that respond to music playback and volume
- **📱 Responsive Design** - Collapsible sidebar and optimized layout for mobile devices
- **🎭 Enhanced Animations** - Smooth transitions and visual feedback throughout the UI

## Features

- 🎵 **Music Playback** - Stream audio files with full playback controls
- 📊 **Audio Visualization** - Dynamic visualizer bars that respond to playback
- 📱 **Responsive Design** - Optimized for both desktop and mobile devices
- 👥 **User Management** - Admin can create and manage user accounts
- 📋 **Playlists** - Create and manage personal playlists
- 📝 **Music Requests** - Users can request songs, admins can process them
- 🎨 **Modern UI** - Beautiful dark theme with smooth animations

## Project Structure

```
hm/
├── backend/
│   ├── config.py           # Configuration settings
│   ├── main.py             # FastAPI application entry
│   ├── requirements.txt    # Python dependencies
│   ├── models/
│   │   ├── database.py     # SQLAlchemy models
│   │   └── schemas.py      # Pydantic schemas
│   ├── routes/
│   │   ├── auth.py         # Authentication routes
│   │   ├── music.py        # Music management routes
│   │   ├── playlists.py    # Playlist routes
│   │   ├── requests.py     # Music request routes
│   │   └── admin.py        # Admin routes
│   └── services/
│       ├── auth.py         # Auth service
│       └── music.py        # Music service
├── frontend/
│   ├── src/
│   │   ├── api/            # API client
│   │   ├── components/     # Reusable UI components
│   │   ├── contexts/       # React contexts
│   │   ├── hooks/          # Custom React hooks
│   │   ├── pages/          # Page components
│   │   ├── utils/          # Utility functions
│   │   ├── App.jsx         # Main app component
│   │   └── main.jsx        # Entry point
│   └── ...config files
└── Music/                   # Place music files here
```

## Getting Started

### Backend Setup

```bash
cd hm/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python main.py
# or
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
cd hm/frontend

# Install dependencies
npm install

# Run development server
npm run dev -- --host
```

### Adding Music

1. Place audio files (.mp3, .flac, .wav, .m4a, .ogg, .aac, .wma) in the `Music/` folder
2. Login as admin
3. Go to "Music Manager" and click "Scan Directory"

## Default Credentials

- **Username:** admin
- **Password:** admin123

⚠️ Change the admin password in production by setting environment variables:
```bash
export ADMIN_USERNAME="your_username"
export ADMIN_PASSWORD="your_secure_password"
export SECRET_KEY="your_secret_key"
```

## Mobile Experience

The app is fully responsive:
- **Sidebar** - Collapses to a hamburger menu on mobile
- **Mini Player** - Compact layout with essential controls
- **Full Player** - Swipe-friendly with large touch targets
- **Queue Panel** - Full-width on mobile devices

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | User login |
| `/api/auth/me` | GET | Get current user |
| `/api/music` | GET | List all tracks |
| `/api/music/{id}/stream` | GET | Stream audio file |
| `/api/playlists` | GET/POST | List/create playlists |
| `/api/requests` | GET/POST | List/create music requests |
| `/api/admin/users` | GET/POST | Manage users (admin) |

## License

MIT
