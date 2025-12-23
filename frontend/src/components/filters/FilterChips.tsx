import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface FilterChip {
  id: string;
  label: string;
  onRemove: () => void;
}

interface FilterChipsProps {
  filters: FilterChip[];
  onClearAll?: () => void;
}

export const FilterChips: React.FC<FilterChipsProps> = ({ filters, onClearAll }) => {
  if (filters.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="font-ui text-xs font-bold uppercase text-tertiary">Active Filters:</span>

      <AnimatePresence mode="popLayout">
        {filters.map((filter) => (
          <motion.div
            key={filter.id}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            className="flex items-center gap-2 px-3 py-1.5 bg-library/20 border-2 border-library/50 rounded-full"
          >
            <span className="font-ui text-xs font-bold text-library">{filter.label}</span>
            <button
              onClick={filter.onRemove}
              className="w-4 h-4 rounded-full bg-library/30 hover:bg-library hover:text-base transition-colors flex items-center justify-center"
            >
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </motion.div>
        ))}
      </AnimatePresence>

      {onClearAll && filters.length > 1 && (
        <motion.button
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={onClearAll}
          className="px-3 py-1.5 rounded-lg bg-surface border-2 border-library/50 hover:border-library hover:shadow-glow-cyan transition-all font-ui text-xs font-bold uppercase text-library"
        >
          Clear All
        </motion.button>
      )}
    </div>
  );
};

export default FilterChips;
