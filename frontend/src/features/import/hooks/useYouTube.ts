import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { youtubeApi, type YouTubeSearchParams, type YouTubeDownloadRequest } from '@/lib/api/endpoints/youtube';
import { queryKeys } from '@/lib/api/queryKeys';
import toast from 'react-hot-toast';

/**
 * Search YouTube for videos
 */
export function useYouTubeSearch(params: YouTubeSearchParams, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.youtube.search(params),
    queryFn: () => youtubeApi.search(params),
    enabled: options.enabled !== false && (!!params.artist || !!params.track_title || !!params.query),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Start YouTube video download
 */
export function useYouTubeDownload() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: YouTubeDownloadRequest) => youtubeApi.download(data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.youtube.downloads() });
      toast.success(`Download started: ${data.job_id}`, {
        icon: '⬇️',
      });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to start download', {
        icon: '⚠️',
      });
    },
  });
}

/**
 * Cancel YouTube download
 */
export function useCancelYouTubeDownload() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (jobId: string) => youtubeApi.cancel(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.youtube.downloads() });
      toast.success('Download cancelled', {
        icon: '🚫',
      });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to cancel download', {
        icon: '⚠️',
      });
    },
  });
}

/**
 * Get active downloads
 */
export function useActiveDownloads() {
  return useQuery({
    queryKey: queryKeys.youtube.downloads(),
    queryFn: () => youtubeApi.getActiveDownloads(),
    refetchInterval: 5000, // Poll every 5 seconds as fallback
  });
}
