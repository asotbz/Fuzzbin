import React from 'react';
import { motion } from 'framer-motion';
import { Button, Badge } from '@/components/ui';
import { formatDuration, formatNumber } from '@/lib/utils/formatting';
import type { YouTubeSearchResult } from '@/lib/api/endpoints/youtube';

interface YouTubeResultCardProps {
  result: YouTubeSearchResult;
  index: number;
  onDownload: (url: string) => void;
  isDownloading?: boolean;
}

export const YouTubeResultCard: React.FC<YouTubeResultCardProps> = ({
  result,
  index,
  onDownload,
  isDownloading,
}) => {
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05 }}
      className="bg-surface border-2 border-surface-light rounded-lg overflow-hidden hover:border-import/50 transition-all"
    >
      <div className="grid md:grid-cols-[200px_1fr_auto] gap-4 p-4">
        {/* Thumbnail */}
        <div className="relative aspect-video md:aspect-auto md:w-[200px] bg-base rounded-lg overflow-hidden">
          <img
            src={result.thumbnail}
            alt={result.title}
            className="w-full h-full object-cover"
          />
          {result.duration && (
            <div className="absolute bottom-2 right-2 px-2 py-1 bg-base/90 backdrop-blur-sm rounded border-2 border-surface-light">
              <span className="font-ui text-xs font-bold text-primary">
                {formatDuration(result.duration)}
              </span>
            </div>
          )}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <h3 className="font-display text-lg font-bold text-primary mb-1 line-clamp-2">
            {result.title}
          </h3>
          <p className="font-body text-sm text-secondary mb-2">{result.channel}</p>

          <div className="flex flex-wrap gap-3 text-xs text-tertiary">
            {result.view_count !== undefined && (
              <div className="flex items-center gap-1">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
                <span className="font-ui">{formatNumber(result.view_count)} views</span>
              </div>
            )}
            {result.upload_date && (
              <div className="flex items-center gap-1">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                  <line x1="16" y1="2" x2="16" y2="6" />
                  <line x1="8" y1="2" x2="8" y2="6" />
                  <line x1="3" y1="10" x2="21" y2="10" />
                </svg>
                <span className="font-ui">{result.upload_date}</span>
              </div>
            )}
          </div>
        </div>

        {/* Download Button */}
        <div className="flex items-center">
          <Button
            variant="import"
            size="sm"
            onClick={() => onDownload(result.url)}
            loading={isDownloading}
            disabled={isDownloading}
          >
            {isDownloading ? 'Downloading...' : 'Download'}
          </Button>
        </div>
      </div>
    </motion.div>
  );
};

export default YouTubeResultCard;
