import React, { forwardRef } from 'react';
import { cn } from '@/lib/utils/cn';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  icon?: React.ReactNode;
  fullWidth?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, icon, fullWidth, className, ...props }, ref) => {
    return (
      <div className={cn('flex flex-col gap-2', fullWidth && 'w-full')}>
        {label && (
          <label
            htmlFor={props.id}
            className="font-ui text-sm font-bold uppercase tracking-wider text-secondary"
          >
            {label}
          </label>
        )}
        <div className="relative">
          {icon && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-tertiary">
              {icon}
            </div>
          )}
          <input
            ref={ref}
            className={cn(
              'w-full px-4 py-3 rounded-lg',
              'bg-surface border-2 border-surface-light',
              'text-primary font-body text-base',
              'transition-all duration-200',
              'placeholder:text-tertiary',
              'focus:outline-none focus:border-library focus:shadow-glow-cyan',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              error && 'border-error focus:border-error focus:shadow-[0_0_20px_rgba(255,0,110,0.5)]',
              icon && 'pl-10',
              className
            )}
            style={
              error
                ? {
                    borderColor: 'var(--error)',
                  }
                : undefined
            }
            {...props}
          />
        </div>
        {error && (
          <span className="text-xs font-ui font-semibold text-error">{error}</span>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';

export default Input;
