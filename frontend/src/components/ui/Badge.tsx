import React from 'react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils/cn';

type BadgeVariant = 'library' | 'import' | 'player' | 'manage' | 'system' | 'default';
type BadgeSize = 'sm' | 'md' | 'lg';

interface BadgeProps {
  variant?: BadgeVariant;
  size?: BadgeSize;
  children: React.ReactNode;
  className?: string;
  rotate?: boolean;
}

const channelColors: Record<Exclude<BadgeVariant, 'default'>, string> = {
  library: 'var(--channel-library)',
  import: 'var(--channel-import)',
  player: 'var(--channel-player)',
  manage: 'var(--channel-manage)',
  system: 'var(--channel-system)',
};

const sizeClasses: Record<BadgeSize, string> = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-3 py-1 text-xs',
  lg: 'px-4 py-1.5 text-sm',
};

export const Badge: React.FC<BadgeProps> = ({
  variant = 'default',
  size = 'md',
  children,
  className,
  rotate = true,
}) => {
  const channelColor = variant !== 'default' ? channelColors[variant] : undefined;

  return (
    <motion.span
      initial={{ scale: 0, rotate: 0 }}
      animate={{
        scale: 1,
        rotate: rotate ? (Math.random() > 0.5 ? 2 : -2) : 0,
      }}
      transition={{ type: 'spring', stiffness: 400, damping: 15 }}
      className={cn(
        'inline-flex items-center gap-1.5',
        'font-ui font-bold uppercase tracking-wider',
        'border-2 rounded-full whitespace-nowrap',
        'shadow-sm',
        sizeClasses[size],
        variant === 'default'
          ? 'bg-surface border-surface-light text-secondary'
          : 'bg-surface',
        className
      )}
      style={
        channelColor
          ? {
              color: channelColor,
              borderColor: channelColor,
            }
          : undefined
      }
    >
      {children}
    </motion.span>
  );
};

export default Badge;
