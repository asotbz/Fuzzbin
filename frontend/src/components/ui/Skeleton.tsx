import React from 'react';
import { cn } from '@/lib/utils/cn';

interface SkeletonProps {
  className?: string;
  variant?: 'text' | 'circular' | 'rectangular';
  width?: string | number;
  height?: string | number;
  count?: number;
}

export const Skeleton: React.FC<SkeletonProps> = ({
  className,
  variant = 'rectangular',
  width,
  height,
  count = 1,
}) => {
  const baseClasses = cn(
    'bg-surface relative overflow-hidden',
    variant === 'text' && 'h-4 rounded',
    variant === 'circular' && 'rounded-full',
    variant === 'rectangular' && 'rounded-lg',
    className
  );

  const style = {
    width: width,
    height: height,
  };

  const skeletonElement = (
    <div className={baseClasses} style={style}>
      {/* Shimmer animation */}
      <div className="absolute inset-0 -translate-x-full animate-[shimmer_1.5s_infinite] bg-gradient-to-r from-transparent via-surface-light to-transparent" />
    </div>
  );

  if (count === 1) {
    return skeletonElement;
  }

  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i}>{skeletonElement}</div>
      ))}
    </div>
  );
};

export default Skeleton;
