import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import { useLogout } from '@/features/auth/hooks/useLogin';
import { Input, Button } from '@/components/ui';

export const Header: React.FC = () => {
  const user = useAuthStore((state) => state.user);
  const navigate = useNavigate();
  const logoutMutation = useLogout();
  const [searchQuery, setSearchQuery] = useState('');
  const [showUserMenu, setShowUserMenu] = useState(false);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      // Navigate to search results (will implement later)
      console.log('Search for:', searchQuery);
    }
  };

  return (
    <header className="sticky top-0 z-30 border-b-2 border-surface-light bg-surface/90 backdrop-blur-xl">
      <div className="flex items-center justify-between gap-4 px-6 py-4">
        {/* Search Bar */}
        <motion.form
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          onSubmit={handleSearch}
          className="flex-1 max-w-2xl"
        >
          <div className="relative">
            <Input
              type="search"
              placeholder="Search videos, artists, collections..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              icon={
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.35-4.35" />
                </svg>
              }
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-secondary hover:text-primary transition-colors"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            )}
          </div>
        </motion.form>

        {/* User Menu */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="relative"
        >
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-3 px-4 py-2 rounded-lg border-2 border-surface-light hover:border-library transition-all bg-surface-hover"
          >
            {/* Avatar */}
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-library to-import flex items-center justify-center font-display text-base font-bold uppercase text-base">
              {user?.username?.[0] || 'U'}
            </div>

            {/* Username */}
            <span className="font-ui text-sm font-semibold uppercase text-primary hidden md:block">
              {user?.username || 'User'}
            </span>

            {/* Chevron */}
            <motion.svg
              animate={{ rotate: showUserMenu ? 180 : 0 }}
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <polyline points="6 9 12 15 18 9" />
            </motion.svg>
          </button>

          {/* Dropdown Menu */}
          <AnimatePresence>
            {showUserMenu && (
              <>
                {/* Backdrop */}
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setShowUserMenu(false)}
                />

                {/* Menu */}
                <motion.div
                  initial={{ opacity: 0, y: -10, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -10, scale: 0.95 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 25 }}
                  className="absolute right-0 mt-2 w-64 bg-surface border-2 border-surface-light rounded-lg shadow-xl overflow-hidden z-50"
                >
                  {/* User Info */}
                  <div className="p-4 border-b-2 border-surface-light bg-surface-hover">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-full bg-gradient-to-br from-library to-import flex items-center justify-center font-display text-xl font-bold uppercase text-base">
                        {user?.username?.[0] || 'U'}
                      </div>
                      <div>
                        <p className="font-ui text-sm font-bold uppercase text-primary">
                          {user?.username || 'User'}
                        </p>
                        <p className="text-xs text-tertiary">
                          User ID: {user?.id || 'N/A'}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Menu Items */}
                  <div className="py-2">
                    <button
                      onClick={() => {
                        setShowUserMenu(false);
                        navigate('/system');
                      }}
                      className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface-hover transition-colors text-secondary hover:text-primary"
                    >
                      <svg
                        width="20"
                        height="20"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                      >
                        <circle cx="12" cy="12" r="3" />
                        <path d="M12 1v6m0 6v6m8.66-15.66l-4.24 4.24m-4.24 4.24l-4.24 4.24m15.66-8.66l-4.24-4.24m-4.24-4.24l-4.24-4.24" />
                      </svg>
                      <span className="font-ui text-sm font-semibold uppercase">
                        Settings
                      </span>
                    </button>

                    <button
                      onClick={() => {
                        setShowUserMenu(false);
                        // Open help modal (will implement later)
                        console.log('Help');
                      }}
                      className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface-hover transition-colors text-secondary hover:text-primary"
                    >
                      <svg
                        width="20"
                        height="20"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                      >
                        <circle cx="12" cy="12" r="10" />
                        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
                        <line x1="12" y1="17" x2="12.01" y2="17" />
                      </svg>
                      <span className="font-ui text-sm font-semibold uppercase">
                        Help
                      </span>
                    </button>
                  </div>

                  {/* Logout */}
                  <div className="p-2 border-t-2 border-surface-light">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setShowUserMenu(false);
                        logoutMutation.mutate();
                      }}
                      loading={logoutMutation.isPending}
                      className="w-full justify-start"
                      icon={
                        <svg
                          width="20"
                          height="20"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                        >
                          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                          <polyline points="16 17 21 12 16 7" />
                          <line x1="21" y1="12" x2="9" y2="12" />
                        </svg>
                      }
                    >
                      Logout
                    </Button>
                  </div>
                </motion.div>
              </>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    </header>
  );
};

export default Header;
