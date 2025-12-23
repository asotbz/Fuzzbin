import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { authApi } from '@/lib/api/endpoints/auth';
import type { LoginRequest } from '@/lib/api/endpoints/auth';
import { useAuthStore } from '@/stores/authStore';
import toast from 'react-hot-toast';

export function useLogin() {
  const navigate = useNavigate();
  const { setTokens, setUser } = useAuthStore();

  return useMutation({
    mutationFn: (credentials: LoginRequest) => authApi.login(credentials),
    onSuccess: (data) => {
      // Store tokens and user info
      setTokens(data.access_token, data.refresh_token);
      setUser(data.user);

      // Show success message
      toast.success(`Welcome back, ${data.user.username}!`, {
        duration: 3000,
        icon: '🎸',
      });

      // Navigate to library
      navigate('/library');
    },
    onError: (error: any) => {
      // Handle different error cases
      const message = error.response?.data?.detail || 'Login failed. Please try again.';

      toast.error(message, {
        duration: 4000,
        icon: '⚠️',
      });
    },
  });
}

export function useLogout() {
  const navigate = useNavigate();
  const { logout } = useAuthStore();

  return useMutation({
    mutationFn: () => authApi.logout(),
    onSuccess: () => {
      logout();
      navigate('/login');
      toast.success('Logged out successfully', {
        icon: '👋',
      });
    },
    onError: () => {
      // Even if logout fails, clear local state
      logout();
      navigate('/login');
    },
  });
}
