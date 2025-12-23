import React from 'react';
import { motion } from 'framer-motion';

interface FilterBarProps {
  selectedTags: string[];
  onTagsChange: (tags: string[]) => void;
  selectedStatus: string | null;
  onStatusChange: (status: string | null) => void;
  yearRange: { min?: number; max?: number };
  onYearRangeChange: (range: { min?: number; max?: number }) => void;
  availableTags?: string[];
  availableStatuses?: string[];
}

export const FilterBar: React.FC<FilterBarProps> = ({
  selectedTags,
  onTagsChange,
  selectedStatus,
  onStatusChange,
  yearRange,
  onYearRangeChange,
  availableTags = [],
  availableStatuses = ['available', 'processing', 'error', 'deleted'],
}) => {
  const toggleTag = (tag: string) => {
    if (selectedTags.includes(tag)) {
      onTagsChange(selectedTags.filter((t) => t !== tag));
    } else {
      onTagsChange([...selectedTags, tag]);
    }
  };

  return (
    <div className="space-y-4">
      {/* Status Filter */}
      <div className="space-y-2">
        <label className="font-ui text-sm font-bold uppercase text-secondary">Status:</label>
        <div className="flex flex-wrap gap-2">
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => onStatusChange(null)}
            className={`px-4 py-2 rounded-lg font-ui text-sm font-bold uppercase border-2 transition-all ${
              selectedStatus === null
                ? 'bg-library text-base border-library shadow-glow-cyan'
                : 'bg-surface text-secondary border-surface-light hover:border-library/50'
            }`}
          >
            All
          </motion.button>
          {availableStatuses.map((status) => (
            <motion.button
              key={status}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => onStatusChange(status)}
              className={`px-4 py-2 rounded-lg font-ui text-sm font-bold uppercase border-2 transition-all ${
                selectedStatus === status
                  ? 'bg-library text-base border-library shadow-glow-cyan'
                  : 'bg-surface text-secondary border-surface-light hover:border-library/50'
              }`}
            >
              {status}
            </motion.button>
          ))}
        </div>
      </div>

      {/* Tags Filter */}
      {availableTags.length > 0 && (
        <div className="space-y-2">
          <label className="font-ui text-sm font-bold uppercase text-secondary">Tags:</label>
          <div className="flex flex-wrap gap-2">
            {availableTags.map((tag) => (
              <motion.button
                key={tag}
                whileHover={{ scale: 1.05, rotate: selectedTags.includes(tag) ? 0 : 2 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => toggleTag(tag)}
                className={`px-3 py-1.5 rounded-full font-ui text-xs font-bold uppercase border-2 transition-all ${
                  selectedTags.includes(tag)
                    ? 'bg-library text-base border-library shadow-glow-cyan'
                    : 'bg-surface text-tertiary border-library/30 hover:border-library/50'
                }`}
                style={{
                  transform: selectedTags.includes(tag) ? 'rotate(0deg)' : 'rotate(-1deg)',
                }}
              >
                {tag}
              </motion.button>
            ))}
          </div>
        </div>
      )}

      {/* Year Range Filter */}
      <div className="space-y-2">
        <label className="font-ui text-sm font-bold uppercase text-secondary">Year Range:</label>
        <div className="flex items-center gap-4">
          <input
            type="number"
            placeholder="Min"
            value={yearRange.min || ''}
            onChange={(e) =>
              onYearRangeChange({
                ...yearRange,
                min: e.target.value ? parseInt(e.target.value) : undefined,
              })
            }
            className="w-24 px-3 py-2 bg-surface border-2 border-surface-light rounded-lg font-body text-primary placeholder:text-tertiary transition-all duration-200 focus:outline-none focus:border-library focus:shadow-glow-cyan"
          />
          <span className="font-ui text-tertiary">to</span>
          <input
            type="number"
            placeholder="Max"
            value={yearRange.max || ''}
            onChange={(e) =>
              onYearRangeChange({
                ...yearRange,
                max: e.target.value ? parseInt(e.target.value) : undefined,
              })
            }
            className="w-24 px-3 py-2 bg-surface border-2 border-surface-light rounded-lg font-body text-primary placeholder:text-tertiary transition-all duration-200 focus:outline-none focus:border-library focus:shadow-glow-cyan"
          />
          {(yearRange.min || yearRange.max) && (
            <motion.button
              initial={{ opacity: 0, scale: 0 }}
              animate={{ opacity: 1, scale: 1 }}
              onClick={() => onYearRangeChange({ min: undefined, max: undefined })}
              className="px-3 py-2 rounded-lg bg-surface-light border-2 border-library/50 hover:border-library hover:shadow-glow-cyan transition-all font-ui text-xs font-bold uppercase text-library"
            >
              Clear
            </motion.button>
          )}
        </div>
      </div>
    </div>
  );
};

export default FilterBar;
