/**
 * Fuzzbin Channel Definitions
 * Each major feature area has a signature color and icon
 */

export type ChannelId = 'library' | 'import' | 'player' | 'manage' | 'system';

export interface Channel {
  id: ChannelId;
  name: string;
  color: string;
  description: string;
  path: string;
}

export const CHANNELS: Record<ChannelId, Channel> = {
  library: {
    id: 'library',
    name: 'Library',
    color: '#00F0FF', // Electric Cyan
    description: 'Browse and search your video library',
    path: '/library',
  },
  import: {
    id: 'import',
    name: 'Import',
    color: '#FF006E', // Hot Magenta
    description: 'Search and download videos from YouTube',
    path: '/import',
  },
  player: {
    id: 'player',
    name: 'Player',
    color: '#FFD60A', // Laser Yellow
    description: 'Watch videos with full playback controls',
    path: '/player',
  },
  manage: {
    id: 'manage',
    name: 'Manage',
    color: '#39FF14', // Neon Green
    description: 'Organize collections, artists, and tags',
    path: '/manage',
  },
  system: {
    id: 'system',
    name: 'System',
    color: '#9D4EDD', // Purple
    description: 'Configuration, backups, and job monitoring',
    path: '/system',
  },
};

export const getChannelColor = (channelId: ChannelId): string => {
  return CHANNELS[channelId].color;
};

export const getChannel = (channelId: ChannelId): Channel => {
  return CHANNELS[channelId];
};
