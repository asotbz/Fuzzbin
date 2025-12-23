import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Input, Button } from '@/components/ui';

interface YouTubeSearchFormProps {
  onSearch: (artist: string, trackTitle: string) => void;
  isLoading?: boolean;
}

export const YouTubeSearchForm: React.FC<YouTubeSearchFormProps> = ({ onSearch, isLoading }) => {
  const [artist, setArtist] = useState('');
  const [trackTitle, setTrackTitle] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (artist.trim() || trackTitle.trim()) {
      onSearch(artist.trim(), trackTitle.trim());
    }
  };

  return (
    <motion.form
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      onSubmit={handleSubmit}
      className="space-y-4"
    >
      <div className="grid md:grid-cols-2 gap-4">
        <Input
          label="Artist Name"
          value={artist}
          onChange={(e) => setArtist(e.target.value)}
          placeholder="e.g., Daft Punk"
        />
        <Input
          label="Track Title"
          value={trackTitle}
          onChange={(e) => setTrackTitle(e.target.value)}
          placeholder="e.g., Around the World"
        />
      </div>

      <Button
        type="submit"
        variant="import"
        loading={isLoading}
        disabled={!artist.trim() && !trackTitle.trim()}
      >
        Search YouTube
      </Button>
    </motion.form>
  );
};

export default YouTubeSearchForm;
