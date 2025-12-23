import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  debounceMs?: number;
}

export const SearchBar: React.FC<SearchBarProps> = ({
  value,
  onChange,
  placeholder = 'Search videos, artists, collections...',
  debounceMs = 300,
}) => {
  const [localValue, setLocalValue] = useState(value);

  useEffect(() => {
    setLocalValue(value);
  }, [value]);

  useEffect(() => {
    const timer = setTimeout(() => {
      onChange(localValue);
    }, debounceMs);

    return () => clearTimeout(timer);
  }, [localValue, debounceMs, onChange]);

  return (
    <div className="relative">
      <motion.input
        type="search"
        value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        placeholder={placeholder}
        className="w-full px-4 py-3 pl-12 bg-surface border-2 border-surface-light rounded-lg font-body text-primary placeholder:text-tertiary transition-all duration-200 focus:outline-none focus:border-library focus:shadow-glow-cyan"
        whileFocus={{ scale: 1.01 }}
      />
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="var(--text-tertiary)"
        strokeWidth="2"
        className="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none"
      >
        <circle cx="11" cy="11" r="8" />
        <path d="m21 21-4.35-4.35" />
      </svg>
      {localValue && (
        <motion.button
          initial={{ opacity: 0, scale: 0 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0 }}
          onClick={() => setLocalValue('')}
          className="absolute right-4 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-surface-light hover:bg-library/20 transition-colors flex items-center justify-center"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </motion.button>
      )}
    </div>
  );
};

export default SearchBar;
