// Fuzzbin UI - Component Examples
// Neo-MTV Maximalism Design System Implementation

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// ============================================
// 1. VIDEO CARD COMPONENT
// ============================================

interface VideoCardProps {
  id: string;
  title: string;
  artist: string;
  thumbnail?: string;
  duration: number;
  tags: string[];
  viewCount?: number;
  onClick?: () => void;
}

export const VideoCard: React.FC<VideoCardProps> = ({
  title,
  artist,
  thumbnail,
  duration,
  tags,
  viewCount,
  onClick
}) => {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <motion.div
      className="video-card"
      onHoverStart={() => setIsHovered(true)}
      onHoverEnd={() => setIsHovered(false)}
      whileHover={{
        y: -8,
        rotate: -1,
        transition: { type: 'spring', stiffness: 300, damping: 20 }
      }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      style={{
        background: 'var(--bg-surface)',
        border: `3px solid ${isHovered ? 'var(--channel-library)' : 'var(--bg-surface-light)'}`,
        borderRadius: 'var(--radius-lg)',
        overflow: 'hidden',
        cursor: 'pointer',
        boxShadow: isHovered
          ? 'var(--shadow-xl), var(--shadow-glow-cyan)'
          : 'var(--shadow-md)',
        transition: 'border-color 0.3s, box-shadow 0.3s'
      }}
    >
      {/* Thumbnail */}
      <div style={{
        aspectRatio: '16/9',
        background: thumbnail
          ? `url(${thumbnail}) center/cover`
          : 'linear-gradient(135deg, var(--channel-library) 0%, var(--channel-import) 100%)',
        position: 'relative',
        overflow: 'hidden'
      }}>
        {/* Gradient overlay on hover */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: isHovered ? 1 : 0 }}
          style={{
            position: 'absolute',
            inset: 0,
            background: 'linear-gradient(180deg, transparent 0%, rgba(10, 0, 20, 0.9) 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: isHovered ? 1 : 0 }}
            transition={{ type: 'spring', stiffness: 400, damping: 15 }}
            style={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              background: 'var(--channel-library)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: 'var(--shadow-glow-cyan)'
            }}
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="var(--bg-base)">
              <path d="M8 5v14l11-7z"/>
            </svg>
          </motion.div>
        </motion.div>

        {/* Duration badge */}
        <div style={{
          position: 'absolute',
          bottom: 8,
          right: 8,
          padding: '4px 8px',
          background: 'rgba(10, 0, 20, 0.9)',
          borderRadius: 'var(--radius-sm)',
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          color: 'var(--text-primary)',
          border: '2px solid var(--bg-surface-light)'
        }}>
          {Math.floor(duration / 60)}:{String(duration % 60).padStart(2, '0')}
        </div>
      </div>

      {/* Content */}
      <div style={{ padding: 'var(--space-4)' }}>
        <h3 style={{
          fontFamily: 'var(--font-display)',
          fontSize: 'var(--text-lg)',
          fontWeight: 700,
          color: 'var(--text-primary)',
          marginBottom: 'var(--space-2)',
          lineHeight: 1.2,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical'
        }}>
          {title}
        </h3>

        <p style={{
          fontFamily: 'var(--font-body)',
          fontSize: 'var(--text-sm)',
          color: 'var(--text-secondary)',
          marginBottom: 'var(--space-3)'
        }}>
          {artist}
        </p>

        {/* Tags */}
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 'var(--space-2)',
          marginBottom: 'var(--space-3)'
        }}>
          {tags.slice(0, 3).map((tag, i) => (
            <span
              key={tag}
              style={{
                padding: '2px 8px',
                fontFamily: 'var(--font-ui)',
                fontSize: 'var(--text-xs)',
                fontWeight: 700,
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
                border: '2px solid var(--channel-library)',
                borderRadius: 'var(--radius-full)',
                background: 'var(--bg-surface-light)',
                color: 'var(--channel-library)',
                transform: i % 2 === 0 ? 'rotate(-2deg)' : 'rotate(2deg)',
                whiteSpace: 'nowrap'
              }}
            >
              {tag}
            </span>
          ))}
        </div>

        {/* Stats */}
        {viewCount !== undefined && (
          <div style={{
            fontFamily: 'var(--font-body)',
            fontSize: 'var(--text-xs)',
            color: 'var(--text-tertiary)',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-2)'
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/>
            </svg>
            {viewCount.toLocaleString()} views
          </div>
        )}
      </div>
    </motion.div>
  );
};

// ============================================
// 2. CHUNKY BUTTON COMPONENT
// ============================================

interface ChunkyButtonProps {
  children: React.ReactNode;
  variant?: 'library' | 'import' | 'player' | 'manage';
  size?: 'sm' | 'md' | 'lg';
  onClick?: () => void;
  disabled?: boolean;
  icon?: React.ReactNode;
}

export const ChunkyButton: React.FC<ChunkyButtonProps> = ({
  children,
  variant = 'library',
  size = 'md',
  onClick,
  disabled = false,
  icon
}) => {
  const channelColors = {
    library: 'var(--channel-library)',
    import: 'var(--channel-import)',
    player: 'var(--channel-player)',
    manage: 'var(--channel-manage)'
  };

  const sizes = {
    sm: { padding: 'var(--space-2) var(--space-4)', fontSize: 'var(--text-sm)' },
    md: { padding: 'var(--space-3) var(--space-6)', fontSize: 'var(--text-base)' },
    lg: { padding: 'var(--space-4) var(--space-8)', fontSize: 'var(--text-lg)' }
  };

  return (
    <motion.button
      whileHover={{ y: -2, scale: 1.02 }}
      whileTap={{ scale: 0.98, y: 0 }}
      onClick={onClick}
      disabled={disabled}
      style={{
        ...sizes[size],
        fontFamily: 'var(--font-ui)',
        fontWeight: 700,
        letterSpacing: '0.05em',
        textTransform: 'uppercase',
        border: `3px solid ${channelColors[variant]}`,
        borderRadius: 'var(--radius-lg)',
        background: 'var(--bg-surface)',
        color: channelColors[variant],
        boxShadow: 'var(--shadow-lg)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 'var(--space-2)',
        transition: 'box-shadow 0.2s',
      }}
      onMouseEnter={(e) => {
        if (!disabled) {
          e.currentTarget.style.boxShadow = `var(--shadow-xl), 0 0 30px ${channelColors[variant]}40`;
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = 'var(--shadow-lg)';
      }}
    >
      {icon}
      {children}
    </motion.button>
  );
};

// ============================================
// 3. NAVIGATION SIDEBAR
// ============================================

interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  channel: 'library' | 'import' | 'player' | 'manage' | 'system';
  path: string;
}

interface SidebarProps {
  items: NavItem[];
  activeId: string;
  onNavigate: (id: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ items, activeId, onNavigate }) => {
  const channelColors = {
    library: 'var(--channel-library)',
    import: 'var(--channel-import)',
    player: 'var(--channel-player)',
    manage: 'var(--channel-manage)',
    system: 'var(--channel-system)'
  };

  return (
    <div style={{
      width: 280,
      background: 'var(--bg-surface)',
      borderRight: '3px solid var(--bg-surface-light)',
      padding: 'var(--space-6)',
      height: '100vh',
      overflow: 'auto'
    }}>
      {/* Logo */}
      <div style={{
        marginBottom: 'var(--space-8)',
        paddingBottom: 'var(--space-6)',
        borderBottom: '3px solid var(--bg-surface-light)'
      }}>
        <h1 style={{
          fontFamily: 'var(--font-display)',
          fontSize: 'var(--text-3xl)',
          fontWeight: 800,
          color: 'var(--text-primary)',
          textTransform: 'uppercase',
          lineHeight: 0.9,
          background: 'linear-gradient(135deg, var(--channel-library), var(--channel-import))',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          letterSpacing: '-0.02em'
        }}>
          FUZZ<br/>BIN
        </h1>
      </div>

      {/* Navigation Items */}
      <nav>
        {items.map((item) => {
          const isActive = item.id === activeId;
          const channelColor = channelColors[item.channel];

          return (
            <motion.button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              whileHover={{ x: 4 }}
              whileTap={{ scale: 0.98 }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-4)',
                width: '100%',
                padding: 'var(--space-4)',
                marginBottom: 'var(--space-2)',
                borderRadius: 'var(--radius-lg)',
                border: `2px solid ${isActive ? channelColor : 'transparent'}`,
                fontFamily: 'var(--font-ui)',
                fontWeight: 600,
                fontSize: 'var(--text-base)',
                color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                background: isActive ? 'var(--bg-surface-hover)' : 'transparent',
                cursor: 'pointer',
                position: 'relative',
                transition: 'all 0.2s'
              }}
            >
              {/* Channel accent bar */}
              <motion.div
                initial={{ height: 0 }}
                animate={{ height: isActive ? 32 : 0 }}
                transition={{ type: 'spring', stiffness: 400, damping: 25 }}
                style={{
                  position: 'absolute',
                  left: 0,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  width: 4,
                  background: channelColor,
                  borderRadius: 'var(--radius-full)'
                }}
              />

              <span style={{ color: channelColor, display: 'flex' }}>
                {item.icon}
              </span>
              {item.label}
            </motion.button>
          );
        })}
      </nav>
    </div>
  );
};

// ============================================
// 4. YOUTUBE IMPORT CARD
// ============================================

interface YouTubeImportCardProps {
  videoId: string;
  title: string;
  channel: string;
  thumbnail: string;
  duration: number;
  viewCount: number;
  onImport: () => void;
  isImporting?: boolean;
}

export const YouTubeImportCard: React.FC<YouTubeImportCardProps> = ({
  title,
  channel,
  thumbnail,
  duration,
  viewCount,
  onImport,
  isImporting = false
}) => {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        background: 'var(--bg-surface)',
        border: '2px solid var(--bg-surface-light)',
        borderRadius: 'var(--radius-lg)',
        padding: 'var(--space-4)',
        display: 'flex',
        gap: 'var(--space-4)',
        alignItems: 'flex-start'
      }}
    >
      {/* Thumbnail */}
      <div style={{
        width: 160,
        aspectRatio: '16/9',
        background: `url(${thumbnail}) center/cover`,
        borderRadius: 'var(--radius-md)',
        flexShrink: 0,
        position: 'relative'
      }}>
        <div style={{
          position: 'absolute',
          bottom: 4,
          right: 4,
          padding: '2px 6px',
          background: 'rgba(10, 0, 20, 0.95)',
          borderRadius: 'var(--radius-sm)',
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          color: 'var(--text-primary)'
        }}>
          {Math.floor(duration / 60)}:{String(duration % 60).padStart(2, '0')}
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1 }}>
        <h3 style={{
          fontFamily: 'var(--font-body)',
          fontSize: 'var(--text-base)',
          fontWeight: 600,
          color: 'var(--text-primary)',
          marginBottom: 'var(--space-1)',
          lineHeight: 1.3
        }}>
          {title}
        </h3>

        <p style={{
          fontFamily: 'var(--font-body)',
          fontSize: 'var(--text-sm)',
          color: 'var(--text-secondary)',
          marginBottom: 'var(--space-2)'
        }}>
          {channel}
        </p>

        <div style={{
          fontFamily: 'var(--font-body)',
          fontSize: 'var(--text-xs)',
          color: 'var(--text-tertiary)',
          marginBottom: 'var(--space-3)'
        }}>
          {viewCount.toLocaleString()} views
        </div>

        <ChunkyButton
          variant="import"
          size="sm"
          onClick={onImport}
          disabled={isImporting}
          icon={
            isImporting ? (
              <motion.svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="3"
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              >
                <circle cx="12" cy="12" r="10" opacity="0.25"/>
                <path d="M12 2a10 10 0 0 1 10 10"/>
              </motion.svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M19 12v7H5v-7H3v7c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-7h-2zm-6 .67l2.59-2.58L17 11.5l-5 5-5-5 1.41-1.41L11 12.67V3h2z"/>
              </svg>
            )
          }
        >
          {isImporting ? 'Importing...' : 'Import'}
        </ChunkyButton>
      </div>
    </motion.div>
  );
};

// ============================================
// 5. PROGRESS BAR (Job Downloads)
// ============================================

interface ProgressBarProps {
  progress: number; // 0-100
  label?: string;
  variant?: 'library' | 'import' | 'player';
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  progress,
  label,
  variant = 'import'
}) => {
  const channelColors = {
    library: 'var(--channel-library)',
    import: 'var(--channel-import)',
    player: 'var(--channel-player)'
  };

  return (
    <div>
      {label && (
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: 'var(--space-2)',
          fontFamily: 'var(--font-ui)',
          fontSize: 'var(--text-sm)',
          fontWeight: 600,
          color: 'var(--text-secondary)'
        }}>
          <span>{label}</span>
          <span>{Math.round(progress)}%</span>
        </div>
      )}

      <div style={{
        height: 24,
        background: 'var(--bg-surface-light)',
        borderRadius: 'var(--radius-lg)',
        border: '2px solid var(--bg-surface-hover)',
        overflow: 'hidden',
        position: 'relative'
      }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ type: 'spring', stiffness: 100, damping: 20 }}
          style={{
            height: '100%',
            background: `linear-gradient(90deg, ${channelColors[variant]}, ${channelColors[variant]}dd)`,
            borderRadius: 'var(--radius-md)',
            boxShadow: `0 0 20px ${channelColors[variant]}60`,
            position: 'relative',
            overflow: 'hidden'
          }}
        >
          {/* Animated shimmer */}
          <motion.div
            animate={{
              x: ['-100%', '200%']
            }}
            transition={{
              duration: 1.5,
              repeat: Infinity,
              ease: 'linear'
            }}
            style={{
              position: 'absolute',
              inset: 0,
              background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent)',
              width: '50%'
            }}
          />
        </motion.div>
      </div>
    </div>
  );
};

// ============================================
// 6. SEARCH BAR
// ============================================

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  placeholder?: string;
  suggestions?: string[];
}

export const SearchBar: React.FC<SearchBarProps> = ({
  value,
  onChange,
  onSubmit,
  placeholder = 'Search videos...',
  suggestions = []
}) => {
  const [isFocused, setIsFocused] = useState(false);

  return (
    <div style={{ position: 'relative', width: '100%', maxWidth: 600 }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        background: 'var(--bg-surface)',
        border: `3px solid ${isFocused ? 'var(--channel-library)' : 'var(--bg-surface-light)'}`,
        borderRadius: 'var(--radius-lg)',
        padding: 'var(--space-3) var(--space-4)',
        boxShadow: isFocused ? 'var(--shadow-glow-cyan)' : 'var(--shadow-md)',
        transition: 'all 0.3s'
      }}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="var(--channel-library)" style={{ marginRight: 'var(--space-3)' }}>
          <path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
        </svg>

        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setTimeout(() => setIsFocused(false), 200)}
          onKeyPress={(e) => e.key === 'Enter' && onSubmit()}
          placeholder={placeholder}
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            fontFamily: 'var(--font-body)',
            fontSize: 'var(--text-base)',
            color: 'var(--text-primary)',
            '::placeholder': {
              color: 'var(--text-tertiary)'
            }
          }}
        />

        {value && (
          <motion.button
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            onClick={() => onChange('')}
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-secondary)',
              padding: 4,
              display: 'flex'
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </motion.button>
        )}
      </div>

      {/* Suggestions dropdown */}
      <AnimatePresence>
        {isFocused && suggestions.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            style={{
              position: 'absolute',
              top: 'calc(100% + var(--space-2))',
              left: 0,
              right: 0,
              background: 'var(--bg-surface)',
              border: '2px solid var(--bg-surface-light)',
              borderRadius: 'var(--radius-lg)',
              boxShadow: 'var(--shadow-xl)',
              overflow: 'hidden',
              zIndex: 10
            }}
          >
            {suggestions.map((suggestion, i) => (
              <motion.button
                key={suggestion}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.03 }}
                onClick={() => {
                  onChange(suggestion);
                  onSubmit();
                }}
                style={{
                  width: '100%',
                  padding: 'var(--space-3) var(--space-4)',
                  background: 'transparent',
                  border: 'none',
                  textAlign: 'left',
                  fontFamily: 'var(--font-body)',
                  fontSize: 'var(--text-sm)',
                  color: 'var(--text-primary)',
                  cursor: 'pointer',
                  borderBottom: i < suggestions.length - 1 ? '1px solid var(--bg-surface-light)' : 'none',
                  transition: 'background 0.2s'
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-surface-hover)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
              >
                {suggestion}
              </motion.button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

// ============================================
// USAGE EXAMPLE - VIDEO LIBRARY PAGE
// ============================================

export const VideoLibraryExample = () => {
  const [searchQuery, setSearchQuery] = useState('');

  const mockVideos = [
    {
      id: '1',
      title: 'Virtual Insanity',
      artist: 'Jamiroquai',
      duration: 245,
      tags: ['funk', '90s', 'classic'],
      viewCount: 12500
    },
    // ... more videos
  ];

  return (
    <div style={{ background: 'var(--bg-base)', minHeight: '100vh' }}>
      {/* Header */}
      <div style={{
        padding: 'var(--space-6)',
        background: 'var(--gradient-mesh)',
        borderBottom: '3px solid var(--bg-surface-light)'
      }}>
        <h1 style={{
          fontFamily: 'var(--font-display)',
          fontSize: 'var(--text-3xl)',
          fontWeight: 800,
          color: 'var(--channel-library)',
          textTransform: 'uppercase',
          marginBottom: 'var(--space-6)',
          textShadow: '0 0 20px rgba(0, 240, 255, 0.5)'
        }}>
          Video Library
        </h1>

        <SearchBar
          value={searchQuery}
          onChange={setSearchQuery}
          onSubmit={() => console.log('Search:', searchQuery)}
          suggestions={['Nirvana', 'MTV Unplugged', '90s rock']}
        />
      </div>

      {/* Video Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
        gap: 'var(--space-6)',
        padding: 'var(--space-6)'
      }}>
        {mockVideos.map((video, i) => (
          <motion.div
            key={video.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
          >
            <VideoCard {...video} />
          </motion.div>
        ))}
      </div>
    </div>
  );
};
