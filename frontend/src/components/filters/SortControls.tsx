import React from 'react';
import { motion } from 'framer-motion';

export type SortField = 'title' | 'artist_name' | 'release_year' | 'created_at' | 'updated_at';
export type SortOrder = 'asc' | 'desc';

interface SortControlsProps {
  sortBy: SortField;
  order: SortOrder;
  onSortChange: (sortBy: SortField, order: SortOrder) => void;
}

const SORT_OPTIONS: { value: SortField; label: string }[] = [
  { value: 'title', label: 'Title' },
  { value: 'artist_name', label: 'Artist' },
  { value: 'release_year', label: 'Year' },
  { value: 'created_at', label: 'Date Added' },
  { value: 'updated_at', label: 'Last Updated' },
];

export const SortControls: React.FC<SortControlsProps> = ({
  sortBy,
  order,
  onSortChange,
}) => {
  return (
    <div className="flex items-center gap-3">
      <label className="font-ui text-sm font-bold uppercase text-secondary">Sort by:</label>

      <select
        value={sortBy}
        onChange={(e) => onSortChange(e.target.value as SortField, order)}
        className="px-3 py-2 bg-surface border-2 border-surface-light rounded-lg font-body text-primary transition-all duration-200 focus:outline-none focus:border-library focus:shadow-glow-cyan cursor-pointer"
      >
        {SORT_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>

      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={() => onSortChange(sortBy, order === 'asc' ? 'desc' : 'asc')}
        className="w-10 h-10 rounded-lg bg-surface border-2 border-library/50 hover:border-library hover:shadow-glow-cyan transition-all duration-200 flex items-center justify-center"
        title={order === 'asc' ? 'Ascending' : 'Descending'}
      >
        <motion.svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--channel-library)"
          strokeWidth="2"
          animate={{ rotate: order === 'asc' ? 0 : 180 }}
          transition={{ type: 'spring', stiffness: 300, damping: 20 }}
        >
          <path d="M12 5v14M19 12l-7 7-7-7" />
        </motion.svg>
      </motion.button>
    </div>
  );
};

export default SortControls;
