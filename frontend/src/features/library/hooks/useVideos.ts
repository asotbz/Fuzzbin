import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { videosApi, type VideosListParams, type VideoUpdateRequest } from '@/lib/api/endpoints/videos';
import { queryKeys } from '@/lib/api/queryKeys';
import toast from 'react-hot-toast';

/**
 * Fetch paginated list of videos
 */
export function useVideos(params?: VideosListParams) {
  return useQuery({
    queryKey: queryKeys.videos.list(params),
    queryFn: () => videosApi.list(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Fetch single video by ID
 */
export function useVideo(id: number) {
  return useQuery({
    queryKey: queryKeys.videos.detail(id),
    queryFn: () => videosApi.getById(id),
    enabled: !!id,
  });
}

/**
 * Update video metadata
 */
export function useUpdateVideo() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: VideoUpdateRequest }) =>
      videosApi.update(id, data),
    onSuccess: (updatedVideo) => {
      // Invalidate video lists
      queryClient.invalidateQueries({ queryKey: queryKeys.videos.lists() });

      // Update single video cache
      queryClient.setQueryData(queryKeys.videos.detail(updatedVideo.id), updatedVideo);

      toast.success('Video updated successfully', {
        icon: '✓',
      });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to update video', {
        icon: '⚠️',
      });
    },
  });
}

/**
 * Delete video (soft delete)
 */
export function useDeleteVideo() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => videosApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.videos.lists() });
      toast.success('Video deleted successfully', {
        icon: '🗑️',
      });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to delete video', {
        icon: '⚠️',
      });
    },
  });
}

/**
 * Update video status
 */
export function useUpdateVideoStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, status, reason }: { id: number; status: string; reason?: string }) =>
      videosApi.updateStatus(id, status, reason),
    onSuccess: (updatedVideo) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.videos.lists() });
      queryClient.setQueryData(queryKeys.videos.detail(updatedVideo.id), updatedVideo);
      queryClient.invalidateQueries({ queryKey: queryKeys.videos.statusHistory(updatedVideo.id) });

      toast.success('Status updated successfully', {
        icon: '✓',
      });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to update status', {
        icon: '⚠️',
      });
    },
  });
}

/**
 * Get video status history
 */
export function useVideoStatusHistory(id: number) {
  return useQuery({
    queryKey: queryKeys.videos.statusHistory(id),
    queryFn: () => videosApi.getStatusHistory(id),
    enabled: !!id,
  });
}

/**
 * Restore deleted video
 */
export function useRestoreVideo() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => videosApi.restore(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.videos.lists() });
      toast.success('Video restored successfully', {
        icon: '♻️',
      });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to restore video', {
        icon: '⚠️',
      });
    },
  });
}
