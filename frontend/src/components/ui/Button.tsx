import React from 'react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils/cn';

export type ButtonVariant = 'library' | 'import' | 'player' | 'manage' | 'system' | 'ghost';
export type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: React.ReactNode;
  loading?: boolean;
  children: React.ReactNode;
}

const channelColors: Record<Exclude<ButtonVariant, 'ghost'>, string> = {
  library: 'var(--channel-library)',
  import: 'var(--channel-import)',
  player: 'var(--channel-player)',
  manage: 'var(--channel-manage)',
  system: 'var(--channel-system)',
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-4 py-2 text-sm',
  md: 'px-6 py-3 text-base',
  lg: 'px-8 py-4 text-lg',
};

export const Button: React.FC<ButtonProps> = ({
  variant = 'library',
  size = 'md',
  icon,
  loading = false,
  disabled,
  children,
  className,
  onClick,
  ...props
}) => {
  const isGhost = variant === 'ghost';
  const channelColor = !isGhost ? channelColors[variant] : undefined;

  return (
    <motion.button
      whileHover={!disabled && !loading ? { y: -2, scale: 1.02 } : undefined}
      whileTap={!disabled && !loading ? { scale: 0.98, y: 0 } : undefined}
      transition={{ type: 'spring', stiffness: 400, damping: 17 }}
      onClick={onClick}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center gap-2',
        'font-ui font-bold uppercase tracking-wider',
        'border-2 rounded-lg',
        'transition-all duration-200',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
        sizeClasses[size],
        isGhost
          ? 'border-current text-secondary bg-transparent hover:bg-surface-light'
          : 'border-current bg-surface shadow-lg',
        disabled || loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer',
        className
      )}
      style={
        !isGhost
          ? {
              color: channelColor,
              borderColor: channelColor,
            }
          : undefined
      }
      onMouseEnter={(e) => {
        if (!disabled && !loading && !isGhost && channelColor) {
          e.currentTarget.style.boxShadow = `var(--shadow-xl), 0 0 30px ${channelColor}40`;
        }
      }}
      onMouseLeave={(e) => {
        if (!isGhost) {
          e.currentTarget.style.boxShadow = 'var(--shadow-lg)';
        }
      }}
      {...props}
    >
      {loading ? (
        <motion.svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
        >
          <circle cx="12" cy="12" r="10" opacity="0.25" />
          <path d="M12 2a10 10 0 0 1 10 10" />
        </motion.svg>
      ) : (
        icon
      )}
      {children}
    </motion.button>
  );
};

export default Button;
