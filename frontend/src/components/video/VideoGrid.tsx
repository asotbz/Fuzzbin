import React from 'react';
import { VideoCard } from './VideoCard';
import { Skeleton } from '@/components/ui';
import type { Video } from '@/lib/api/endpoints/videos';

interface VideoGridProps {
  videos: Video[];
  loading?: boolean;
  emptyMessage?: string;
}

export const VideoGrid: React.FC<VideoGridProps> = ({
  videos,
  loading = false,
  emptyMessage = 'No videos found',
}) => {
  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="space-y-3">
            <Skeleton variant="rectangular" className="aspect-video rounded-lg" />
            <Skeleton variant="text" className="w-3/4" />
            <Skeleton variant="text" className="w-1/2" />
          </div>
        ))}
      </div>
    );
  }

  if (!videos || videos.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <svg
          width="80"
          height="80"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--text-tertiary)"
          strokeWidth="1.5"
          className="mb-4"
        >
          <rect x="2" y="7" width="20" height="15" rx="2" ry="2" />
          <polyline points="17 2 12 7 7 2" />
        </svg>
        <p className="font-ui text-lg font-semibold uppercase text-tertiary">
          {emptyMessage}
        </p>
        <p className="font-body text-sm text-tertiary mt-2">
          Try adjusting your filters or search query
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      {videos.map((video, index) => (
        <VideoCard key={video.id} video={video} index={index} />
      ))}
    </div>
  );
};

export default VideoGrid;
