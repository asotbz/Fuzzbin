import { useState } from 'react'
import type { AddSearchResponse, AddPreviewResponse } from '../../lib/api/types'

export interface MetadataFields {
  // Basic fields
  title: string
  artist: string
  year: number | null

  // Extended fields
  album: string | null
  directors: string | null
  label: string | null

  // Video source
  youtubeId: string | null

  // Import config
  initialStatus: 'discovered' | 'imported'
  skipExisting: boolean
}

interface WizardState {
  currentStep: number
  searchQuery: { artist: string; trackTitle: string }
  searchResults: AddSearchResponse | null
  selectedSource: { source: string; id: string } | null
  previewData: AddPreviewResponse | null
  editedMetadata: MetadataFields
  compareWithDiscogs: boolean
}

const initialMetadata: MetadataFields = {
  title: '',
  artist: '',
  year: null,
  album: null,
  directors: null,
  label: null,
  youtubeId: null,
  initialStatus: 'discovered',
  skipExisting: true,
}

const initialState: WizardState = {
  currentStep: 0,
  searchQuery: { artist: '', trackTitle: '' },
  searchResults: null,
  selectedSource: null,
  previewData: null,
  editedMetadata: initialMetadata,
  compareWithDiscogs: false,
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

  const setCompareWithDiscogs = (compare: boolean) => {
    setState((prev) => ({
      ...prev,
      compareWithDiscogs: compare,
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
    setCompareWithDiscogs,
    nextStep,
    prevStep,
    goToStep,
    resetWizard,
  }
}
