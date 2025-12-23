import React from 'react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils/cn';

type ProgressVariant = 'library' | 'import' | 'player' | 'manage' | 'system';

interface ProgressProps {
  value: number; // 0-100
  label?: string;
  variant?: ProgressVariant;
  showPercentage?: boolean;
  height?: 'sm' | 'md' | 'lg';
  className?: string;
}

const channelColors: Record<ProgressVariant, string> = {
  library: 'var(--channel-library)',
  import: 'var(--channel-import)',
  player: 'var(--channel-player)',
  manage: 'var(--channel-manage)',
  system: 'var(--channel-system)',
};

const heightClasses = {
  sm: 'h-2',
  md: 'h-6',
  lg: 'h-8',
};

export const Progress: React.FC<ProgressProps> = ({
  value,
  label,
  variant = 'import',
  showPercentage = true,
  height = 'md',
  className,
}) => {
  const channelColor = channelColors[variant];
  const percentage = Math.min(100, Math.max(0, value));

  return (
    <div className={cn('w-full', className)}>
      {(label || showPercentage) && (
        <div className="flex items-center justify-between mb-2">
          {label && (
            <span className="font-ui text-sm font-semibold text-secondary">
              {label}
            </span>
          )}
          {showPercentage && (
            <span className="font-ui text-sm font-bold text-primary">
              {Math.round(percentage)}%
            </span>
          )}
        </div>
      )}

      <div
        className={cn(
          'relative overflow-hidden rounded-lg border-2 bg-surface-light',
          heightClasses[height]
        )}
        style={{ borderColor: 'var(--bg-surface-hover)' }}
      >
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ type: 'spring', stiffness: 100, damping: 20 }}
          className="relative h-full rounded-md overflow-hidden"
          style={{
            background: `linear-gradient(90deg, ${channelColor}, ${channelColor}dd)`,
            boxShadow: `0 0 20px ${channelColor}60`,
          }}
        >
          {/* Animated shimmer effect */}
          <motion.div
            animate={{
              x: ['-100%', '200%'],
            }}
            transition={{
              duration: 1.5,
              repeat: Infinity,
              ease: 'linear',
            }}
            className="absolute inset-0 w-1/2"
            style={{
              background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent)',
            }}
          />
        </motion.div>
      </div>
    </div>
  );
};

export default Progress;
