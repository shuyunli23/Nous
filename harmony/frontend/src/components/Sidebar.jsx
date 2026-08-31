import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Music, Home, Search, Library, Bell, Users, Shield, 
  Upload, LogOut, Menu, X, TrendingUp, History, Settings, ArrowLeft
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useSidebar } from '../contexts/SidebarContext';

function NavItem({ icon: Icon, label, active, onClick, badge, small }) {
  const { isMobile, close } = useSidebar();
  
  const handleClick = () => {
    onClick();
    if (isMobile) close();
  };
  
  return (
    <button 
      onClick={handleClick} 
      className={`
        w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all
        ${active ? 'bg-white/10 text-white' : 'text-zinc-400 hover:text-white hover:bg-white/5'}
        ${small ? 'py-2 text-sm' : ''}
      `}
    >
      <Icon className={small ? 'w-4 h-4' : 'w-5 h-5'} />
      <span className="flex-1 text-left truncate">{label}</span>
      {badge === 'HOT' && (
        <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-gradient-to-r from-orange-500 to-red-500 animate-pulse">
          HOT
        </span>
      )}
      {badge === 'NEW' && (
        <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-gradient-to-r from-purple-500 to-violet-500">
          NEW
        </span>
      )}
      {typeof badge === 'number' && badge > 0 && (
        <span className="w-5 h-5 rounded-full bg-emerald-500 text-xs flex items-center justify-center text-black font-bold">
          {badge}
        </span>
      )}
    </button>
  );
}

export default function Sidebar({ currentPage, setCurrentPage, pendingCount, onOpenProfileSettings }) {
  const { user, logout, fromNous } = useAuth();
  const { isOpen, isMobile, toggle, close } = useSidebar();
  const isAdmin = user?.role === 'admin';

  const sidebarContent = (
    <aside className={`
      ${isMobile ? 'fixed inset-y-0 left-0 z-50' : 'relative'}
      w-64 bg-black/90 backdrop-blur-xl border-r border-white/5 flex flex-col
      transition-transform duration-300 ease-in-out
      ${isMobile && !isOpen ? '-translate-x-full' : 'translate-x-0'}
    `}>
      {/* Header */}
      <div className="p-4 md:p-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-400 to-cyan-500 flex items-center justify-center">
            <Music className="w-5 h-5 text-black" />
          </div>
          <span className="text-xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
            Harmony
          </span>
        </div>
        {isMobile && (
          <button onClick={close} className="p-2 rounded-lg hover:bg-white/10">
            <X className="w-5 h-5" />
          </button>
        )}
      </div>
      
      {/* Navigation */}
      <nav className="flex-1 px-3 space-y-1 overflow-y-auto">
        <NavItem 
          icon={Home} 
          label="Home" 
          active={currentPage === 'home'} 
          onClick={() => setCurrentPage('home')} 
        />
        <NavItem 
          icon={TrendingUp} 
          label="Charts" 
          active={currentPage === 'top'} 
          onClick={() => setCurrentPage('top')} 
          badge="HOT" 
        />
        <NavItem 
          icon={Search} 
          label="Search" 
          active={currentPage === 'search'} 
          onClick={() => setCurrentPage('search')} 
        />
        <NavItem 
          icon={Library} 
          label="My Library" 
          active={currentPage === 'library'} 
          onClick={() => setCurrentPage('library')} 
        />
        <NavItem 
          icon={History} 
          label="History" 
          active={currentPage === 'history'} 
          onClick={() => setCurrentPage('history')}
        />
        <NavItem 
          icon={Bell} 
          label="Requests" 
          active={currentPage === 'requests'} 
          onClick={() => setCurrentPage('requests')} 
          badge={pendingCount > 0 ? pendingCount : undefined} 
        />
        
        {isAdmin && (
          <>
            <div className="pt-4 pb-2 px-3">
              <div className="flex items-center gap-2 text-xs text-amber-400/70 uppercase tracking-wider">
                <Shield className="w-3 h-3" />Admin
              </div>
            </div>
            <div className="pl-3 border-l border-amber-500/30 ml-3 space-y-1">
              <NavItem 
                icon={Upload} 
                label="Music Manager" 
                active={currentPage === 'manage-music'} 
                onClick={() => setCurrentPage('manage-music')} 
                small 
              />
              <NavItem 
                icon={Users} 
                label="User Manager" 
                active={currentPage === 'users'} 
                onClick={() => setCurrentPage('users')} 
                small 
              />
            </div>
          </>
        )}
      </nav>
      
      {/* User profile */}
      <div className="p-4 border-t border-white/5">
        {fromNous && (
          <a
            href="/"
            className="mb-3 flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-zinc-400 hover:text-white hover:bg-white/5 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Nous
          </a>
        )}
        <div className="flex items-center gap-3 p-2 rounded-lg">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-sm font-bold">
            {user?.username?.[0]?.toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{user?.username}</p>
            <p className="text-xs text-zinc-500">{isAdmin ? 'Administrator' : 'User'}</p>
          </div>
          
          {/* Settings button - only for non-admin users */}
          {!isAdmin && (
            <button 
              onClick={() => {
                if (isMobile) close();
                onOpenProfileSettings();
              }} 
              className="p-2 text-zinc-400 hover:text-white transition-colors" 
              title="Profile Settings"
            >
              <Settings className="w-4 h-4" />
            </button>
          )}
          
          <button 
            onClick={logout} 
            className="p-2 text-zinc-400 hover:text-white transition-colors" 
            title="Sign Out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );

  return (
    <>
      {/* Mobile menu button */}
      {isMobile && (
        <button 
          onClick={toggle}
          className="fixed top-4 left-4 z-40 p-2 rounded-lg bg-zinc-900/90 backdrop-blur-xl border border-white/10 hover:bg-zinc-800"
        >
          <Menu className="w-5 h-5" />
        </button>
      )}
      
      {/* Backdrop for mobile */}
      <AnimatePresence>
        {isMobile && isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={close}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
          />
        )}
      </AnimatePresence>
      
      {sidebarContent}
    </>
  );
}