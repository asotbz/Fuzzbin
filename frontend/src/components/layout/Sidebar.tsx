import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { CHANNELS, type ChannelId } from '@/config/channels';
import { useUIStore } from '@/stores/uiStore';

interface NavItem {
  id: ChannelId;
  label: string;
  path: string;
  icon: React.ReactNode;
  color: string;
}

const navItems: NavItem[] = [
  {
    id: 'library',
    label: 'Library',
    path: '/library',
    color: CHANNELS.library.color,
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="2" y="7" width="20" height="15" rx="2" ry="2" />
        <polyline points="17 2 12 7 7 2" />
      </svg>
    ),
  },
  {
    id: 'import',
    label: 'Import',
    path: '/import',
    color: CHANNELS.import.color,
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="7 10 12 15 17 10" />
        <line x1="12" y1="15" x2="12" y2="3" />
      </svg>
    ),
  },
  {
    id: 'player',
    label: 'Player',
    path: '/player',
    color: CHANNELS.player.color,
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="10" />
        <polygon points="10 8 16 12 10 16 10 8" fill="currentColor" />
      </svg>
    ),
  },
  {
    id: 'manage',
    label: 'Manage',
    path: '/manage',
    color: CHANNELS.manage.color,
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
      </svg>
    ),
  },
  {
    id: 'system',
    label: 'System',
    path: '/system',
    color: CHANNELS.system.color,
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="3" />
        <path d="M12 1v6m0 6v6m8.66-15.66l-4.24 4.24m-4.24 4.24l-4.24 4.24m15.66-8.66l-4.24-4.24m-4.24-4.24l-4.24-4.24" />
      </svg>
    ),
  },
];

export const Sidebar: React.FC = () => {
  const location = useLocation();
  const sidebarOpen = useUIStore((state) => state.sidebarOpen);
  const toggleSidebar = useUIStore((state) => state.toggleSidebar);

  return (
    <>
      {/* Mobile Overlay */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={toggleSidebar}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside
        initial={{ x: -280 }}
        animate={{ x: sidebarOpen ? 0 : -280 }}
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        className="fixed left-0 top-0 h-screen w-[280px] bg-surface border-r-2 border-surface-light z-50 lg:z-auto overflow-y-auto"
      >
        <div className="flex flex-col h-full p-6">
          {/* Logo */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="mb-8 pb-6 border-b-2 border-surface-light"
          >
            <NavLink to="/library" className="block">
              <h1
                className="font-display text-4xl font-extrabold uppercase leading-tight"
                style={{
                  background: 'linear-gradient(135deg, var(--channel-library), var(--channel-import))',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                  letterSpacing: '-0.02em',
                }}
              >
                FUZZ
                <br />
                BIN
              </h1>
            </NavLink>
            <p className="font-ui text-xs uppercase tracking-widest text-tertiary mt-1">
              Music Videos
            </p>
          </motion.div>

          {/* Navigation */}
          <nav className="flex-1 space-y-2">
            {navItems.map((item, index) => {
              const isActive = location.pathname.startsWith(item.path);

              return (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.1 + index * 0.05 }}
                >
                  <NavLink
                    to={item.path}
                    className="block relative"
                  >
                    {({ isActive: navIsActive }) => {
                      const active = navIsActive || isActive;

                      return (
                        <motion.div
                          whileHover={{ x: 4 }}
                          whileTap={{ scale: 0.98 }}
                          className="relative flex items-center gap-4 px-4 py-3 rounded-lg border-2 transition-colors"
                          style={{
                            borderColor: active ? item.color : 'transparent',
                            backgroundColor: active ? 'var(--bg-surface-hover)' : 'transparent',
                            color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
                          }}
                        >
                          {/* Channel accent bar */}
                          <motion.div
                            initial={{ height: 0 }}
                            animate={{ height: active ? 32 : 0 }}
                            transition={{ type: 'spring', stiffness: 400, damping: 25 }}
                            className="absolute left-0 top-1/2 -translate-y-1/2 w-1 rounded-full"
                            style={{ backgroundColor: item.color }}
                          />

                          {/* Icon */}
                          <span style={{ color: item.color }}>
                            {item.icon}
                          </span>

                          {/* Label */}
                          <span className="font-ui text-base font-semibold uppercase tracking-wide">
                            {item.label}
                          </span>

                          {/* Active indicator */}
                          {active && (
                            <motion.div
                              layoutId="activeNav"
                              className="absolute right-3 w-2 h-2 rounded-full"
                              style={{ backgroundColor: item.color }}
                              transition={{ type: 'spring', stiffness: 400, damping: 25 }}
                            />
                          )}
                        </motion.div>
                      );
                    }}
                  </NavLink>
                </motion.div>
              );
            })}
          </nav>

          {/* Footer */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="pt-6 mt-6 border-t-2 border-surface-light"
          >
            <div className="text-center">
              <p className="text-xs font-ui uppercase tracking-wider text-tertiary">
                Fuzzbin v0.1.0
              </p>
              <p className="text-xs text-tertiary mt-1">
                Neo-MTV Edition
              </p>
            </div>
          </motion.div>
        </div>
      </motion.aside>

      {/* Mobile Toggle Button */}
      <button
        onClick={toggleSidebar}
        className="fixed bottom-6 left-6 z-50 lg:hidden w-14 h-14 rounded-full bg-library border-2 border-library shadow-xl flex items-center justify-center"
        aria-label="Toggle sidebar"
      >
        <motion.svg
          animate={{ rotate: sidebarOpen ? 180 : 0 }}
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--bg-base)"
          strokeWidth="2"
        >
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </motion.svg>
      </button>
    </>
  );
};

export default Sidebar;
