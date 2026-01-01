import { useState } from 'react'
import type { AddSearchResponse, AddPreviewResponse } from '../../lib/api/types'

export interface YouTubeSourceInfo {
  youtube_id: string
  available: boolean | null  // null = not yet checked
  view_count: number | null
  duration: number | null
  channel: string | null
  title: string | null
  error: string | null
}

export interface MetadataFields {
  // Basic fields
  title: string
  artist: string
  year: number | null

  // Extended fields
  album: string | null
  directors: string | null
  label: string | null
  genre: string | null

  // Video source
  youtubeId: string | null

  // Import config
  skipExisting: boolean
  autoDownload: boolean  // Whether to queue download job on import
}

interface WizardState {
  currentStep: number
  searchQuery: { artist: string; trackTitle: string }
  searchResults: AddSearchResponse | null
  selectedSource: { source: string; id: string } | null
  previewData: AddPreviewResponse | null
  editedMetadata: MetadataFields
  // YouTube source info for availability checking
  youtubeSourceInfo: YouTubeSourceInfo | null
  availableYouTubeSources: string[]  // List of YouTube IDs from IMVDb sources
  // YouTube metadata cache for all available sources
  youtubeMetadataCache: Record<string, YouTubeSourceInfo>
}

const initialMetadata: MetadataFields = {
  title: '',
  artist: '',
  year: null,
  album: null,
  directors: null,
  label: null,
  genre: null,
  youtubeId: null,
  skipExisting: true,
  autoDownload: true,  // Default to download enabled
}

const initialState: WizardState = {
  currentStep: 0,
  searchQuery: { artist: '', trackTitle: '' },
  searchResults: null,
  selectedSource: null,
  previewData: null,
  editedMetadata: initialMetadata,
  youtubeSourceInfo: null,
  availableYouTubeSources: [],
  youtubeMetadataCache: {},
}

export function useSearchWizard() {
  const [state, setState] = useState<WizardState>(initialState)

  const setSearchQuery = (artist: string, trackTitle: string) => {
    setState((prev) => ({
      ...prev,
      searchQuery: { artist, trackTitle },
    }))
  }

  const setSearchResults = (results: AddSearchResponse) => {
    setState((prev) => ({
      ...prev,
      searchResults: results,
    }))
  }

  const selectSource = (source: string, id: string) => {
    setState((prev) => ({
      ...prev,
      selectedSource: { source, id },
    }))
  }

  const setPreviewData = (data: AddPreviewResponse) => {
    setState((prev) => ({
      ...prev,
      previewData: data,
    }))
  }

  const updateMetadata = (updates: Partial<MetadataFields>) => {
    setState((prev) => ({
      ...prev,
      editedMetadata: { ...prev.editedMetadata, ...updates },
    }))
  }

  const setMetadata = (metadata: MetadataFields) => {
    setState((prev) => ({
      ...prev,
      editedMetadata: metadata,
    }))
  }

  const setYouTubeSourceInfo = (info: YouTubeSourceInfo | null) => {
    setState((prev) => ({
      ...prev,
      youtubeSourceInfo: info,
    }))
  }

  const setAvailableYouTubeSources = (sources: string[]) => {
    setState((prev) => ({
      ...prev,
      availableYouTubeSources: sources,
    }))
  }

  const updateYouTubeMetadataCache = (youtubeId: string, info: YouTubeSourceInfo) => {
    setState((prev) => ({
      ...prev,
      youtubeMetadataCache: { ...prev.youtubeMetadataCache, [youtubeId]: info },
    }))
  }

  const nextStep = () => {
    setState((prev) => ({
      ...prev,
      currentStep: Math.min(prev.currentStep + 1, 3),
    }))
  }

  const prevStep = () => {
    setState((prev) => ({
      ...prev,
      currentStep: Math.max(prev.currentStep - 1, 0),
    }))
  }

  const goToStep = (step: number) => {
    setState((prev) => ({
      ...prev,
      currentStep: Math.max(0, Math.min(step, 3)),
    }))
  }

  const resetWizard = () => {
    setState(initialState)
  }

  return {
    ...state,
    setSearchQuery,
    setSearchResults,
    selectSource,
    setPreviewData,
    updateMetadata,
    setMetadata,
    setYouTubeSourceInfo,
    setAvailableYouTubeSources,
    updateYouTubeMetadataCache,
    nextStep,
    prevStep,
    goToStep,
    resetWizard,
  }
}
