import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useQueryClient } from '@tanstack/react-query';
import { YouTubeSearchForm } from '../components/YouTubeSearchForm';
import { YouTubeResultCard } from '../components/YouTubeResultCard';
import { DownloadQueue } from '../components/DownloadQueue';
import { Card } from '@/components/ui';
import { useYouTubeSearch, useYouTubeDownload } from '../hooks/useYouTube';
import { queryKeys } from '@/lib/api/queryKeys';

export const ImportPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useState<{ artist: string; track_title: string } | null>(null);
  const [activeDownloads, setActiveDownloads] = useState<string[]>([]);

  // Search YouTube
  const { data: searchResults, isLoading: isSearching } = useYouTubeSearch(
    searchParams || {},
    { enabled: !!searchParams }
  );

  // Start download
  const downloadMutation = useYouTubeDownload();

  const handleSearch = (artist: string, trackTitle: string) => {
    setSearchParams({ artist, track_title: trackTitle });
  };

  const handleDownload = (url: string) => {
    downloadMutation.mutate(
      { url },
      {
        onSuccess: (data) => {
          setActiveDownloads((prev) => [...prev, data.job_id]);
        },
      }
    );
  };

  const handleJobComplete = () => {
    // Invalidate videos query to show newly downloaded video
    queryClient.invalidateQueries({ queryKey: queryKeys.videos.lists() });
  };

  const handleCancelJob = (jobId: string) => {
    setActiveDownloads((prev) => prev.filter((id) => id !== jobId));
  };

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1
          className="font-display text-5xl font-extrabold uppercase mb-2"
          style={{
            background: 'linear-gradient(135deg, var(--channel-import), var(--channel-library))',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
          }}
        >
          YouTube Import
        </h1>
        <p className="font-body text-lg text-secondary">
          Search and download music videos from YouTube
        </p>
      </motion.div>

      {/* Search Form */}
      <Card padding="lg">
        <h2 className="font-display text-2xl font-bold text-import mb-4">
          Search YouTube
        </h2>
        <YouTubeSearchForm onSearch={handleSearch} isLoading={isSearching} />
      </Card>

      {/* Active Downloads */}
      {activeDownloads.length > 0 && (
        <DownloadQueue
          jobIds={activeDownloads}
          onJobComplete={handleJobComplete}
          onCancelJob={handleCancelJob}
        />
      )}

      {/* Search Results */}
      {searchParams && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-2xl font-bold text-primary">
              Search Results
            </h2>
            {searchResults && (
              <p className="font-ui text-sm text-tertiary">
                {searchResults.length} results found
              </p>
            )}
          </div>

          {isSearching && (
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <div className="w-16 h-16 border-4 border-import border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                <p className="font-ui text-sm uppercase text-secondary">Searching YouTube...</p>
              </div>
            </div>
          )}

          {!isSearching && searchResults && searchResults.length === 0 && (
            <Card padding="lg">
              <div className="text-center py-8">
                <svg
                  width="64"
                  height="64"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="var(--text-tertiary)"
                  strokeWidth="1.5"
                  className="mx-auto mb-4"
                >
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.35-4.35" />
                </svg>
                <p className="font-ui text-lg font-semibold uppercase text-tertiary mb-2">
                  No results found
                </p>
                <p className="font-body text-sm text-tertiary">
                  Try different search terms or check your spelling
                </p>
              </div>
            </Card>
          )}

          {!isSearching && searchResults && searchResults.length > 0 && (
            <div className="space-y-3">
              <AnimatePresence mode="popLayout">
                {searchResults.map((result, index) => (
                  <YouTubeResultCard
                    key={result.id}
                    result={result}
                    index={index}
                    onDownload={handleDownload}
                    isDownloading={downloadMutation.isPending}
                  />
                ))}
              </AnimatePresence>
            </div>
          )}
        </div>
      )}

      {/* Empty State */}
      {!searchParams && activeDownloads.length === 0 && (
        <Card padding="lg">
          <div className="text-center py-12">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', stiffness: 200, damping: 15 }}
            >
              <svg
                width="80"
                height="80"
                viewBox="0 0 24 24"
                fill="none"
                stroke="var(--channel-import)"
                strokeWidth="1.5"
                className="mx-auto mb-4"
              >
                <path d="M23 7l-7 5 7 5V7z" />
                <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
              </svg>
            </motion.div>
            <h3 className="font-display text-2xl font-bold text-primary mb-2">
              Ready to Import
            </h3>
            <p className="font-body text-secondary">
              Enter an artist and track title above to search YouTube
            </p>
          </div>
        </Card>
      )}
    </div>
  );
};

export default ImportPage;
