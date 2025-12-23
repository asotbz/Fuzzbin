import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useVideo, useUpdateVideo, useDeleteVideo } from '../hooks/useVideos';
import { Button, Badge, Card, Input, Modal } from '@/components/ui';
import { formatDuration, formatFileSize, formatRelativeTime } from '@/lib/utils/formatting';

type TabId = 'details' | 'tags' | 'history';

export const VideoDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const videoId = parseInt(id || '0');

  const { data: video, isLoading, isError } = useVideo(videoId);
  const updateVideo = useUpdateVideo();
  const deleteVideo = useDeleteVideo();

  const [activeTab, setActiveTab] = useState<TabId>('details');
  const [isEditing, setIsEditing] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  // Edit form state
  const [editForm, setEditForm] = useState({
    title: '',
    artist_name: '',
    release_year: '',
  });

  React.useEffect(() => {
    if (video) {
      setEditForm({
        title: video.title || '',
        artist_name: video.artist_name || '',
        release_year: video.release_year?.toString() || '',
      });
    }
  }, [video]);

  const handleSave = () => {
    updateVideo.mutate(
      {
        id: videoId,
        data: {
          title: editForm.title,
          artist_name: editForm.artist_name || undefined,
          release_year: editForm.release_year ? parseInt(editForm.release_year) : undefined,
        },
      },
      {
        onSuccess: () => {
          setIsEditing(false);
        },
      }
    );
  };

  const handleDelete = () => {
    deleteVideo.mutate(videoId, {
      onSuccess: () => {
        navigate('/library');
      },
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-library border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="font-ui text-sm uppercase text-secondary">Loading video...</p>
        </div>
      </div>
    );
  }

  if (isError || !video) {
    return (
      <div className="p-8">
        <div className="max-w-2xl mx-auto text-center">
          <svg
            width="64"
            height="64"
            viewBox="0 0 24 24"
            fill="none"
            stroke="var(--channel-import)"
            strokeWidth="2"
            className="mx-auto mb-4"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <h1 className="font-display text-2xl font-bold text-primary mb-2">Video Not Found</h1>
          <p className="font-body text-secondary mb-6">
            The video you're looking for doesn't exist or has been deleted.
          </p>
          <Button variant="library" onClick={() => navigate('/library')}>
            Back to Library
          </Button>
        </div>
      </div>
    );
  }

  const tabs = [
    { id: 'details' as TabId, label: 'Details', icon: '📋' },
    { id: 'tags' as TabId, label: 'Tags', icon: '🏷️' },
    { id: 'history' as TabId, label: 'History', icon: '📜' },
  ];

  return (
    <div className="p-8 space-y-6">
      {/* Header with Back Button */}
      <div className="flex items-center gap-4 mb-6">
        <motion.button
          whileHover={{ x: -4 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => navigate('/library')}
          className="w-10 h-10 rounded-lg bg-surface border-2 border-library/50 hover:border-library hover:shadow-glow-cyan transition-all flex items-center justify-center"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--channel-library)" strokeWidth="2">
            <path d="m15 18-6-6 6-6" />
          </svg>
        </motion.button>
        <div>
          <h1 className="font-display text-3xl font-bold text-primary">Video Details</h1>
          <p className="font-body text-sm text-tertiary">
            ID: {video.id} • Added {formatRelativeTime(video.created_at)}
          </p>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Video Player */}
        <div className="lg:col-span-2">
          <Card padding="none">
            <div className="relative aspect-video bg-base overflow-hidden">
              <video
                controls
                className="w-full h-full"
                poster={`/api/videos/${video.id}/thumbnail`}
                src={`/api/videos/${video.id}/stream`}
              >
                Your browser does not support the video tag.
              </video>
            </div>

            {/* Video Info */}
            <div className="p-6 space-y-4">
              {isEditing ? (
                <div className="space-y-4">
                  <Input
                    label="Title"
                    value={editForm.title}
                    onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                  />
                  <Input
                    label="Artist"
                    value={editForm.artist_name}
                    onChange={(e) => setEditForm({ ...editForm, artist_name: e.target.value })}
                  />
                  <Input
                    label="Release Year"
                    type="number"
                    value={editForm.release_year}
                    onChange={(e) => setEditForm({ ...editForm, release_year: e.target.value })}
                  />

                  <div className="flex gap-3">
                    <Button variant="library" onClick={handleSave} loading={updateVideo.isPending}>
                      Save Changes
                    </Button>
                    <Button variant="ghost" onClick={() => setIsEditing(false)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h2 className="font-display text-2xl font-bold text-primary mb-1">{video.title}</h2>
                      {video.artist_name && (
                        <p className="font-body text-lg text-secondary">{video.artist_name}</p>
                      )}
                    </div>
                    <Badge variant="library">{video.status}</Badge>
                  </div>

                  <div className="flex flex-wrap gap-4 text-sm">
                    {video.duration && (
                      <div className="flex items-center gap-2">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <circle cx="12" cy="12" r="10" />
                          <polyline points="12 6 12 12 16 14" />
                        </svg>
                        <span className="font-ui text-tertiary">{formatDuration(video.duration)}</span>
                      </div>
                    )}
                    {video.release_year && (
                      <div className="flex items-center gap-2">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                          <line x1="16" y1="2" x2="16" y2="6" />
                          <line x1="8" y1="2" x2="8" y2="6" />
                          <line x1="3" y1="10" x2="21" y2="10" />
                        </svg>
                        <span className="font-ui text-tertiary">{video.release_year}</span>
                      </div>
                    )}
                    {video.view_count !== undefined && (
                      <div className="flex items-center gap-2">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                          <circle cx="12" cy="12" r="3" />
                        </svg>
                        <span className="font-ui text-tertiary">{video.view_count} views</span>
                      </div>
                    )}
                  </div>

                  <div className="flex gap-3 pt-4 border-t-2 border-surface-light">
                    <Button variant="library" size="sm" onClick={() => setIsEditing(true)}>
                      Edit Metadata
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setShowDeleteModal(true)}>
                      Delete Video
                    </Button>
                  </div>
                </>
              )}
            </div>
          </Card>
        </div>

        {/* Sidebar with Tabs */}
        <div className="space-y-6">
          {/* Tab Navigation */}
          <div className="flex gap-2">
            {tabs.map((tab) => (
              <motion.button
                key={tab.id}
                whileHover={{ y: -2 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 px-4 py-3 rounded-lg font-ui text-sm font-bold uppercase border-2 transition-all ${
                  activeTab === tab.id
                    ? 'bg-library text-base border-library shadow-glow-cyan'
                    : 'bg-surface text-secondary border-surface-light hover:border-library/50'
                }`}
              >
                <div className="flex flex-col items-center gap-1">
                  <span className="text-lg">{tab.icon}</span>
                  <span>{tab.label}</span>
                </div>
              </motion.button>
            ))}
          </div>

          {/* Tab Content */}
          <Card padding="lg">
            <AnimatePresence mode="wait">
              {activeTab === 'details' && (
                <motion.div
                  key="details"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="space-y-4"
                >
                  <h3 className="font-display text-lg font-bold text-primary mb-4">File Information</h3>

                  <div className="space-y-3 text-sm">
                    <div>
                      <label className="font-ui font-bold uppercase text-tertiary text-xs">File Path</label>
                      <p className="font-body text-secondary break-all">{video.file_path}</p>
                    </div>

                    {video.file_size && (
                      <div>
                        <label className="font-ui font-bold uppercase text-tertiary text-xs">File Size</label>
                        <p className="font-body text-secondary">{formatFileSize(video.file_size)}</p>
                      </div>
                    )}

                    <div>
                      <label className="font-ui font-bold uppercase text-tertiary text-xs">Created At</label>
                      <p className="font-body text-secondary">
                        {new Date(video.created_at).toLocaleString()}
                      </p>
                    </div>

                    <div>
                      <label className="font-ui font-bold uppercase text-tertiary text-xs">Last Updated</label>
                      <p className="font-body text-secondary">
                        {new Date(video.updated_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                </motion.div>
              )}

              {activeTab === 'tags' && (
                <motion.div
                  key="tags"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="space-y-4"
                >
                  <h3 className="font-display text-lg font-bold text-primary mb-4">Tags</h3>

                  {video.tags && video.tags.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {video.tags.map((tag, i) => (
                        <motion.span
                          key={tag}
                          initial={{ opacity: 0, scale: 0.8 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ delay: i * 0.05 }}
                          className="px-3 py-1.5 bg-library/20 border-2 border-library/50 rounded-full font-ui text-xs font-bold uppercase text-library"
                          style={{ transform: i % 2 === 0 ? 'rotate(-1deg)' : 'rotate(1deg)' }}
                        >
                          {tag}
                        </motion.span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-tertiary">No tags assigned yet</p>
                  )}

                  <Button variant="library" size="sm">
                    Manage Tags
                  </Button>
                </motion.div>
              )}

              {activeTab === 'history' && (
                <motion.div
                  key="history"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="space-y-4"
                >
                  <h3 className="font-display text-lg font-bold text-primary mb-4">Status History</h3>
                  <p className="text-sm text-tertiary">Status history will appear here</p>
                </motion.div>
              )}
            </AnimatePresence>
          </Card>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        title="Delete Video"
        size="sm"
      >
        <div className="space-y-4">
          <p className="font-body text-secondary">
            Are you sure you want to delete "{video.title}"? This action can be undone later by restoring the video.
          </p>

          <div className="flex gap-3">
            <Button
              variant="library"
              onClick={handleDelete}
              loading={deleteVideo.isPending}
            >
              Delete Video
            </Button>
            <Button variant="ghost" onClick={() => setShowDeleteModal(false)}>
              Cancel
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default VideoDetailPage;
