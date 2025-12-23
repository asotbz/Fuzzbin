import React from 'react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils/cn';

type SpinnerSize = 'sm' | 'md' | 'lg' | 'xl';
type SpinnerVariant = 'library' | 'import' | 'player' | 'manage' | 'system';

interface SpinnerProps {
  size?: SpinnerSize;
  variant?: SpinnerVariant;
  fullScreen?: boolean;
  className?: string;
}

const sizeClasses: Record<SpinnerSize, string> = {
  sm: 'w-4 h-4',
  md: 'w-8 h-8',
  lg: 'w-12 h-12',
  xl: 'w-16 h-16',
};

const channelColors: Record<SpinnerVariant, string> = {
  library: 'var(--channel-library)',
  import: 'var(--channel-import)',
  player: 'var(--channel-player)',
  manage: 'var(--channel-manage)',
  system: 'var(--channel-system)',
};

export const Spinner: React.FC<SpinnerProps> = ({
  size = 'md',
  variant = 'library',
  fullScreen = false,
  className,
}) => {
  const spinner = (
    <motion.svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
      animate={{ rotate: 360 }}
      transition={{
        duration: 1,
        repeat: Infinity,
        ease: 'linear',
      }}
      className={cn(sizeClasses[size], className)}
      style={{ color: channelColors[variant] }}
    >
      <circle cx="12" cy="12" r="10" opacity="0.25" />
      <path d="M12 2a10 10 0 0 1 10 10" />
    </motion.svg>
  );

  if (fullScreen) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-base/80 backdrop-blur-sm">
        {spinner}
      </div>
    );
  }

  return spinner;
};

export default Spinner;
