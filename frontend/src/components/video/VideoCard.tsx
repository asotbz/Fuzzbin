import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Badge } from '@/components/ui';
import type { Video } from '@/lib/api/endpoints/videos';
import { formatDuration, formatNumber } from '@/lib/utils/formatting';
import { videosApi } from '@/lib/api/endpoints/videos';

interface VideoCardProps {
  video: Video;
  index?: number;
}

export const VideoCard: React.FC<VideoCardProps> = ({ video, index = 0 }) => {
  const navigate = useNavigate();
  const [isHovered, setIsHovered] = useState(false);
  const [imageError, setImageError] = useState(false);

  const thumbnailUrl = imageError ? null : videosApi.getThumbnailUrl(video.id);

  const handleClick = () => {
    navigate(`/library/videos/${video.id}`);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, type: 'spring', stiffness: 300, damping: 25 }}
      onHoverStart={() => setIsHovered(true)}
      onHoverEnd={() => setIsHovered(false)}
      whileHover={{
        y: -8,
        rotate: -1,
        transition: { type: 'spring', stiffness: 300, damping: 20 },
      }}
      whileTap={{ scale: 0.98 }}
      onClick={handleClick}
      className="cursor-pointer bg-surface border-2 rounded-lg overflow-hidden transition-all duration-200"
      style={{
        borderColor: isHovered ? 'var(--channel-library)' : 'var(--bg-surface-light)',
        boxShadow: isHovered
          ? 'var(--shadow-xl), var(--shadow-glow-cyan)'
          : 'var(--shadow-md)',
      }}
    >
      {/* Thumbnail */}
      <div className="relative aspect-video bg-surface-light overflow-hidden">
        {thumbnailUrl ? (
          <img
            src={thumbnailUrl}
            alt={video.title}
            className="w-full h-full object-cover"
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-library/20 to-import/20">
            <svg
              width="64"
              height="64"
              viewBox="0 0 24 24"
              fill="none"
              stroke="var(--text-tertiary)"
              strokeWidth="1.5"
            >
              <rect x="2" y="7" width="20" height="15" rx="2" ry="2" />
              <polyline points="17 2 12 7 7 2" />
            </svg>
          </div>
        )}

        {/* Hover Overlay */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: isHovered ? 1 : 0 }}
          className="absolute inset-0 bg-gradient-to-t from-base/90 to-transparent flex items-center justify-center"
        >
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: isHovered ? 1 : 0 }}
            transition={{ type: 'spring', stiffness: 400, damping: 15 }}
            className="w-16 h-16 rounded-full bg-library flex items-center justify-center shadow-glow-cyan"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="var(--bg-base)">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
          </motion.div>
        </motion.div>

        {/* Duration Badge */}
        {video.duration && (
          <div className="absolute bottom-2 right-2 px-2 py-1 bg-base/90 backdrop-blur-sm rounded border-2 border-surface-light">
            <span className="font-ui text-xs font-bold text-primary">
              {formatDuration(video.duration)}
            </span>
          </div>
        )}

        {/* Status Badge */}
        {video.status && video.status !== 'available' && (
          <div className="absolute top-2 left-2">
            <Badge variant="library" size="sm">
              {video.status}
            </Badge>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-4">
        {/* Title */}
        <h3 className="font-display text-lg font-bold text-primary mb-1 line-clamp-2 leading-tight">
          {video.title}
        </h3>

        {/* Artist */}
        {video.artist_name && (
          <p className="font-body text-sm text-secondary mb-3 line-clamp-1">
            {video.artist_name}
          </p>
        )}

        {/* Tags */}
        {video.tags && video.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-3">
            {video.tags.slice(0, 3).map((tag, i) => (
              <span
                key={tag}
                className="px-2 py-0.5 text-xs font-ui font-bold uppercase bg-surface-light border border-library/50 rounded-full text-library"
                style={{
                  transform: i % 2 === 0 ? 'rotate(-1deg)' : 'rotate(1deg)',
                }}
              >
                {tag}
              </span>
            ))}
            {video.tags.length > 3 && (
              <span className="px-2 py-0.5 text-xs font-ui font-bold text-tertiary">
                +{video.tags.length - 3}
              </span>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between text-xs text-tertiary">
          {/* View Count */}
          {video.view_count !== undefined && (
            <div className="flex items-center gap-1.5">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
              <span className="font-ui">{formatNumber(video.view_count)}</span>
            </div>
          )}

          {/* Year */}
          {video.release_year && (
            <span className="font-ui">{video.release_year}</span>
          )}
        </div>
      </div>
    </motion.div>
  );
};

export default VideoCard;
