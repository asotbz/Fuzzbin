import React from 'react';
import { motion } from 'framer-motion';
import type { HTMLMotionProps } from 'framer-motion';
import { cn } from '@/lib/utils/cn';

interface CardProps extends HTMLMotionProps<'div'> {
  variant?: 'default' | 'elevated' | 'outlined';
  padding?: 'none' | 'sm' | 'md' | 'lg';
  hoverable?: boolean;
  children: React.ReactNode;
}

const paddingClasses = {
  none: 'p-0',
  sm: 'p-4',
  md: 'p-6',
  lg: 'p-8',
};

export const Card: React.FC<CardProps> = ({
  variant = 'default',
  padding = 'md',
  hoverable = false,
  children,
  className,
  ...props
}) => {
  return (
    <motion.div
      whileHover={
        hoverable
          ? {
              y: -4,
              rotate: -0.5,
              transition: { type: 'spring', stiffness: 300, damping: 20 },
            }
          : undefined
      }
      className={cn(
        'rounded-lg',
        paddingClasses[padding],
        variant === 'default' && 'bg-surface border-2 border-surface-light shadow-md',
        variant === 'elevated' && 'bg-surface border-2 border-surface-light shadow-lg',
        variant === 'outlined' && 'bg-transparent border-2 border-surface-light',
        hoverable && 'cursor-pointer transition-all duration-200',
        className
      )}
      {...props}
    >
      {children}
    </motion.div>
  );
};

export default Card;
