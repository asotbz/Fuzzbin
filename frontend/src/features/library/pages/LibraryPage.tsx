import React, { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { useSearchParams } from 'react-router-dom';
import { VideoGrid } from '@/components/video/VideoGrid';
import { SearchBar } from '@/components/search/SearchBar';
import { FilterBar } from '@/components/filters/FilterBar';
import { SortControls, type SortField, type SortOrder } from '@/components/filters/SortControls';
import { FilterChips } from '@/components/filters/FilterChips';
import { Button } from '@/components/ui';
import { useVideos } from '../hooks/useVideos';

export const LibraryPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [showFilters, setShowFilters] = useState(false);

  // Parse URL params
  const search = searchParams.get('search') || '';
  const sortBy = (searchParams.get('sort_by') as SortField) || 'created_at';
  const order = (searchParams.get('order') as SortOrder) || 'desc';
  const selectedStatus = searchParams.get('status') || null;
  const selectedTags = searchParams.getAll('tags');
  const yearMin = searchParams.get('year_min');
  const yearMax = searchParams.get('year_max');
  const page = parseInt(searchParams.get('page') || '1');

  // Build query params for API
  const queryParams = useMemo(() => ({
    search: search || undefined,
    sort_by: sortBy,
    order,
    status: selectedStatus || undefined,
    tags: selectedTags.length > 0 ? selectedTags : undefined,
    year_min: yearMin ? parseInt(yearMin) : undefined,
    year_max: yearMax ? parseInt(yearMax) : undefined,
    page,
    page_size: 20,
  }), [search, sortBy, order, selectedStatus, selectedTags, yearMin, yearMax, page]);

  // Fetch videos
  const { data, isLoading, isError } = useVideos(queryParams);

  // Update URL params
  const updateParams = (updates: Record<string, string | string[] | null>) => {
    const newParams = new URLSearchParams(searchParams);

    Object.entries(updates).forEach(([key, value]) => {
      if (value === null || value === '' || (Array.isArray(value) && value.length === 0)) {
        newParams.delete(key);
      } else if (Array.isArray(value)) {
        newParams.delete(key);
        value.forEach((v) => newParams.append(key, v));
      } else {
        newParams.set(key, value);
      }
    });

    // Reset to page 1 when filters change (unless explicitly setting page)
    if (!updates.page) {
      newParams.set('page', '1');
    }

    setSearchParams(newParams);
  };

  // Filter chips for active filters
  const filterChips = useMemo(() => {
    const chips = [];

    if (search) {
      chips.push({
        id: 'search',
        label: `Search: "${search}"`,
        onRemove: () => updateParams({ search: null }),
      });
    }

    if (selectedStatus) {
      chips.push({
        id: 'status',
        label: `Status: ${selectedStatus}`,
        onRemove: () => updateParams({ status: null }),
      });
    }

    selectedTags.forEach((tag) => {
      chips.push({
        id: `tag-${tag}`,
        label: `Tag: ${tag}`,
        onRemove: () => updateParams({ tags: selectedTags.filter((t) => t !== tag) }),
      });
    });

    if (yearMin) {
      chips.push({
        id: 'year-min',
        label: `Year ≥ ${yearMin}`,
        onRemove: () => updateParams({ year_min: null }),
      });
    }

    if (yearMax) {
      chips.push({
        id: 'year-max',
        label: `Year ≤ ${yearMax}`,
        onRemove: () => updateParams({ year_max: null }),
      });
    }

    return chips;
  }, [search, selectedStatus, selectedTags, yearMin, yearMax]);

  const clearAllFilters = () => {
    setSearchParams(new URLSearchParams({ sort_by: sortBy, order }));
  };

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-4xl font-bold text-primary mb-2">
            Video Library
          </h1>
          <p className="font-body text-lg text-secondary">
            {data?.total ? `${data.total} videos in your collection` : 'Browse your collection'}
          </p>
        </div>

        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => setShowFilters(!showFilters)}
          className={`px-4 py-2 rounded-lg font-ui text-sm font-bold uppercase border-2 transition-all ${
            showFilters
              ? 'bg-library text-base border-library shadow-glow-cyan'
              : 'bg-surface text-secondary border-surface-light hover:border-library/50'
          }`}
        >
          <div className="flex items-center gap-2">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="4" y1="21" x2="4" y2="14" />
              <line x1="4" y1="10" x2="4" y2="3" />
              <line x1="12" y1="21" x2="12" y2="12" />
              <line x1="12" y1="8" x2="12" y2="3" />
              <line x1="20" y1="21" x2="20" y2="16" />
              <line x1="20" y1="12" x2="20" y2="3" />
              <line x1="1" y1="14" x2="7" y2="14" />
              <line x1="9" y1="8" x2="15" y2="8" />
              <line x1="17" y1="16" x2="23" y2="16" />
            </svg>
            {showFilters ? 'Hide Filters' : 'Show Filters'}
          </div>
        </motion.button>
      </div>

      {/* Search Bar */}
      <SearchBar
        value={search}
        onChange={(value) => updateParams({ search: value })}
      />

      {/* Active Filter Chips */}
      {filterChips.length > 0 && (
        <FilterChips filters={filterChips} onClearAll={clearAllFilters} />
      )}

      {/* Sort Controls */}
      <div className="flex items-center justify-between">
        <SortControls
          sortBy={sortBy}
          order={order}
          onSortChange={(newSortBy, newOrder) =>
            updateParams({ sort_by: newSortBy, order: newOrder })
          }
        />

        {data && (
          <div className="font-body text-sm text-tertiary">
            Page {data.page} of {data.pages}
          </div>
        )}
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="bg-surface border-2 border-surface-light rounded-lg p-6"
        >
          <FilterBar
            selectedTags={selectedTags}
            onTagsChange={(tags) => updateParams({ tags })}
            selectedStatus={selectedStatus}
            onStatusChange={(status) => updateParams({ status })}
            yearRange={{ min: yearMin ? parseInt(yearMin) : undefined, max: yearMax ? parseInt(yearMax) : undefined }}
            onYearRangeChange={(range) =>
              updateParams({
                year_min: range.min?.toString() || null,
                year_max: range.max?.toString() || null,
              })
            }
            availableTags={[]} // TODO: Fetch from API
            availableStatuses={['available', 'processing', 'error', 'deleted']}
          />
        </motion.div>
      )}

      {/* Error State */}
      {isError && (
        <div className="bg-import/10 border-2 border-import rounded-lg p-6 text-center">
          <svg
            width="48"
            height="48"
            viewBox="0 0 24 24"
            fill="none"
            stroke="var(--channel-import)"
            strokeWidth="2"
            className="mx-auto mb-4"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <p className="font-ui text-lg font-bold text-import">Failed to load videos</p>
          <p className="font-body text-sm text-secondary mt-2">
            Please try again or check your connection
          </p>
        </div>
      )}

      {/* Video Grid */}
      <VideoGrid videos={data?.items || []} loading={isLoading} />

      {/* Pagination */}
      {data && data.pages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="library"
            size="sm"
            onClick={() => updateParams({ page: (page - 1).toString() })}
            disabled={page <= 1}
          >
            Previous
          </Button>

          <div className="flex items-center gap-1">
            {Array.from({ length: Math.min(data.pages, 7) }, (_, i) => {
              let pageNum;
              if (data.pages <= 7) {
                pageNum = i + 1;
              } else if (page <= 4) {
                pageNum = i + 1;
              } else if (page >= data.pages - 3) {
                pageNum = data.pages - 6 + i;
              } else {
                pageNum = page - 3 + i;
              }

              return (
                <motion.button
                  key={pageNum}
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.9 }}
                  onClick={() => updateParams({ page: pageNum.toString() })}
                  className={`w-10 h-10 rounded-lg font-ui text-sm font-bold transition-all ${
                    page === pageNum
                      ? 'bg-library text-base border-2 border-library shadow-glow-cyan'
                      : 'bg-surface text-secondary border-2 border-surface-light hover:border-library/50'
                  }`}
                >
                  {pageNum}
                </motion.button>
              );
            })}
          </div>

          <Button
            variant="library"
            size="sm"
            onClick={() => updateParams({ page: (page + 1).toString() })}
            disabled={page >= data.pages}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
};

export default LibraryPage;
