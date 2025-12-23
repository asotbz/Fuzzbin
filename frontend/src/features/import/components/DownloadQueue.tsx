import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button, Progress, Card } from '@/components/ui';
import { useJobProgress } from '@/lib/ws/hooks';

interface DownloadQueueItemProps {
  jobId: string;
  onComplete?: () => void;
  onCancel?: (jobId: string) => void;
}

const DownloadQueueItem: React.FC<DownloadQueueItemProps> = ({ jobId, onComplete, onCancel }) => {
  const { progress, cancel } = useJobProgress(jobId, {
    onComplete: () => {
      if (onComplete) onComplete();
    },
  });

  const handleCancel = () => {
    cancel();
    if (onCancel) onCancel(jobId);
  };

  if (!progress) {
    return (
      <div className="p-4 bg-surface border-2 border-surface-light rounded-lg">
        <div className="flex items-center gap-3">
          <div className="w-4 h-4 border-2 border-import border-t-transparent rounded-full animate-spin" />
          <span className="font-ui text-sm text-secondary">Initializing download...</span>
        </div>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      className="p-4 bg-surface border-2 border-import/50 rounded-lg"
    >
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <p className="font-ui text-sm font-bold text-primary truncate">
              {progress.message || `Job ${jobId.slice(0, 8)}`}
            </p>
            <div className="flex items-center gap-3 mt-1 text-xs text-tertiary">
              {progress.speed && (
                <span className="font-ui">{progress.speed}</span>
              )}
              {progress.eta && (
                <span className="font-ui">ETA: {progress.eta}</span>
              )}
            </div>
          </div>

          {progress.status !== 'completed' && progress.status !== 'failed' && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCancel}
            >
              Cancel
            </Button>
          )}
        </div>

        {/* Progress Bar */}
        {progress.status === 'running' && progress.progress !== undefined && (
          <Progress
            value={progress.progress}
            variant="import"
            showPercentage
          />
        )}

        {/* Status Messages */}
        {progress.status === 'completed' && (
          <div className="flex items-center gap-2 text-sm text-success">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            <span className="font-ui font-bold">Download completed!</span>
          </div>
        )}

        {progress.status === 'failed' && (
          <div className="flex items-center gap-2 text-sm text-import">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span className="font-ui font-bold">{progress.error || 'Download failed'}</span>
          </div>
        )}
      </div>
    </motion.div>
  );
};

interface DownloadQueueProps {
  jobIds: string[];
  onJobComplete?: () => void;
  onCancelJob?: (jobId: string) => void;
}

export const DownloadQueue: React.FC<DownloadQueueProps> = ({ jobIds, onJobComplete, onCancelJob }) => {
  if (jobIds.length === 0) {
    return null;
  }

  return (
    <Card padding="lg">
      <h3 className="font-display text-xl font-bold text-import mb-4">
        Active Downloads ({jobIds.length})
      </h3>

      <div className="space-y-3">
        <AnimatePresence mode="popLayout">
          {jobIds.map((jobId) => (
            <DownloadQueueItem
              key={jobId}
              jobId={jobId}
              onComplete={onJobComplete}
              onCancel={onCancelJob}
            />
          ))}
        </AnimatePresence>
      </div>
    </Card>
  );
};

export default DownloadQueue;
