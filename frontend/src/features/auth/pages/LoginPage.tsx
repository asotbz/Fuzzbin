import React from 'react';
import { motion } from 'framer-motion';
import { Navigate } from 'react-router-dom';
import { LoginForm } from '../components/LoginForm';
import { useAuthStore } from '@/stores/authStore';

export const LoginPage: React.FC = () => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  // Redirect if already authenticated
  if (isAuthenticated) {
    return <Navigate to="/library" replace />;
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6 relative overflow-hidden">
      {/* Animated Background Gradient Orbs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <motion.div
          animate={{
            x: [0, 100, 0],
            y: [0, -100, 0],
            scale: [1, 1.2, 1],
          }}
          transition={{
            duration: 20,
            repeat: Infinity,
            ease: 'linear',
          }}
          className="absolute top-0 left-0 w-96 h-96 rounded-full blur-3xl opacity-30"
          style={{ background: 'radial-gradient(circle, var(--channel-library) 0%, transparent 70%)' }}
        />
        <motion.div
          animate={{
            x: [0, -100, 0],
            y: [0, 100, 0],
            scale: [1, 1.1, 1],
          }}
          transition={{
            duration: 25,
            repeat: Infinity,
            ease: 'linear',
          }}
          className="absolute bottom-0 right-0 w-96 h-96 rounded-full blur-3xl opacity-30"
          style={{ background: 'radial-gradient(circle, var(--channel-import) 0%, transparent 70%)' }}
        />
        <motion.div
          animate={{
            x: [0, 50, 0],
            y: [0, 50, 0],
            scale: [1, 1.15, 1],
          }}
          transition={{
            duration: 30,
            repeat: Infinity,
            ease: 'linear',
          }}
          className="absolute top-1/2 left-1/2 w-96 h-96 rounded-full blur-3xl opacity-20"
          style={{ background: 'radial-gradient(circle, var(--channel-player) 0%, transparent 70%)' }}
        />
      </div>

      {/* Login Container */}
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ type: 'spring', stiffness: 300, damping: 25 }}
        className="relative z-10 w-full max-w-md"
      >
        {/* Card */}
        <div className="bg-surface/90 backdrop-blur-xl border-2 border-surface-light rounded-lg shadow-xl p-8 md:p-12">
          {/* Logo / Branding */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-center mb-8 flex justify-center"
          >
            <img
              src="/fuzzbin_logo.png"
              alt="Fuzzbin"
              className="w-48 mx-auto"
            />
          </motion.div>

          {/* Divider */}
          <motion.div
            initial={{ scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ delay: 0.15, duration: 0.5 }}
            className="h-1 bg-gradient-to-r from-transparent via-library to-transparent mb-8 rounded-full mx-auto max-w-xs"
          />

          {/* Login Form */}
          <LoginForm />
        </div>
      </motion.div>
    </div>
  );
};

export default LoginPage;
