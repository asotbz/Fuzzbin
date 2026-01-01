import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useSearchWizard } from '../useSearchWizard'

describe('useSearchWizard', () => {
  describe('initial state', () => {
    it('starts at step 0', () => {
      const { result } = renderHook(() => useSearchWizard())

      expect(result.current.currentStep).toBe(0)
    })

    it('has empty search query', () => {
      const { result } = renderHook(() => useSearchWizard())

      expect(result.current.searchQuery).toEqual({ artist: '', trackTitle: '' })
    })

    it('has null results and preview', () => {
      const { result } = renderHook(() => useSearchWizard())

      expect(result.current.searchResults).toBeNull()
      expect(result.current.selectedSource).toBeNull()
      expect(result.current.previewData).toBeNull()
    })

    it('has default metadata values', () => {
      const { result } = renderHook(() => useSearchWizard())

      expect(result.current.editedMetadata).toMatchObject({
        title: '',
        artist: '',
        year: null,
        skipExisting: true,
      })
    })
  })

  describe('search query', () => {
    it('updates search query', () => {
      const { result } = renderHook(() => useSearchWizard())

      act(() => {
        result.current.setSearchQuery('Nirvana', 'Smells Like Teen Spirit')
      })

      expect(result.current.searchQuery).toEqual({
        artist: 'Nirvana',
        trackTitle: 'Smells Like Teen Spirit',
      })
    })
  })

  describe('search results', () => {
    it('sets search results', () => {
      const { result } = renderHook(() => useSearchWizard())

      const mockResults = {
        artist: 'Test Artist',
        track_title: 'Test Song',
        results: [
          { source: 'imvdb' as const, id: 'test-1', title: 'Test Video' },
        ],
      }

      act(() => {
        result.current.setSearchResults(mockResults)
      })

      expect(result.current.searchResults).toEqual(mockResults)
    })
  })

  describe('source selection', () => {
    it('selects a source', () => {
      const { result } = renderHook(() => useSearchWizard())

      act(() => {
        result.current.selectSource('imvdb', 'video-123')
      })

      expect(result.current.selectedSource).toEqual({
        source: 'imvdb',
        id: 'video-123',
      })
    })
  })

  describe('preview data', () => {
    it('sets preview data', () => {
      const { result } = renderHook(() => useSearchWizard())

      const mockPreview = {
        source: 'imvdb' as const,
        id: 'video-123',
        data: {
          title: 'Test Video',
          artist: 'Test Artist',
        },
      }

      act(() => {
        result.current.setPreviewData(mockPreview)
      })

      expect(result.current.previewData).toEqual(mockPreview)
    })
  })

  describe('metadata editing', () => {
    it('updates individual metadata fields', () => {
      const { result } = renderHook(() => useSearchWizard())

      act(() => {
        result.current.updateMetadata({ title: 'Updated Title' })
      })

      expect(result.current.editedMetadata.title).toBe('Updated Title')
      // Other fields should remain default
      expect(result.current.editedMetadata.artist).toBe('')
    })

    it('updates multiple metadata fields at once', () => {
      const { result } = renderHook(() => useSearchWizard())

      act(() => {
        result.current.updateMetadata({
          title: 'New Title',
          artist: 'New Artist',
          year: 2024,
        })
      })

      expect(result.current.editedMetadata.title).toBe('New Title')
      expect(result.current.editedMetadata.artist).toBe('New Artist')
      expect(result.current.editedMetadata.year).toBe(2024)
    })

    it('replaces all metadata with setMetadata', () => {
      const { result } = renderHook(() => useSearchWizard())

      const newMetadata = {
        title: 'Complete Title',
        artist: 'Complete Artist',
        year: 2023,
        album: 'Complete Album',
        directors: 'Test Director',
        label: 'Test Label',
        genre: 'Rock',
        youtubeId: 'yt-123',
        skipExisting: false,
        autoDownload: true,
      }

      act(() => {
        result.current.setMetadata(newMetadata)
      })

      expect(result.current.editedMetadata).toEqual(newMetadata)
    })
  })

  describe('step navigation', () => {
    it('advances to next step', () => {
      const { result } = renderHook(() => useSearchWizard())

      act(() => {
        result.current.nextStep()
      })

      expect(result.current.currentStep).toBe(1)
    })

    it('goes back to previous step', () => {
      const { result } = renderHook(() => useSearchWizard())

      act(() => {
        result.current.nextStep()
        result.current.nextStep()
      })
      expect(result.current.currentStep).toBe(2)

      act(() => {
        result.current.prevStep()
      })
      expect(result.current.currentStep).toBe(1)
    })

    it('does not go below step 0', () => {
      const { result } = renderHook(() => useSearchWizard())

      act(() => {
        result.current.prevStep()
        result.current.prevStep()
      })

      expect(result.current.currentStep).toBe(0)
    })

    it('does not go above step 3', () => {
      const { result } = renderHook(() => useSearchWizard())

      act(() => {
        for (let i = 0; i < 10; i++) {
          result.current.nextStep()
        }
      })

      expect(result.current.currentStep).toBe(3)
    })

    it('goes to specific step with goToStep', () => {
      const { result } = renderHook(() => useSearchWizard())

      act(() => {
        result.current.goToStep(2)
      })

      expect(result.current.currentStep).toBe(2)
    })

    it('clamps goToStep to valid range', () => {
      const { result } = renderHook(() => useSearchWizard())

      act(() => {
        result.current.goToStep(-5)
      })
      expect(result.current.currentStep).toBe(0)

      act(() => {
        result.current.goToStep(100)
      })
      expect(result.current.currentStep).toBe(3)
    })
  })

  describe('reset', () => {
    it('resets wizard to initial state', () => {
      const { result } = renderHook(() => useSearchWizard())

      // Make some changes
      act(() => {
        result.current.setSearchQuery('Artist', 'Song')
        result.current.nextStep()
        result.current.nextStep()
        result.current.updateMetadata({ title: 'Changed' })
      })

      // Reset
      act(() => {
        result.current.resetWizard()
      })

      expect(result.current.currentStep).toBe(0)
      expect(result.current.searchQuery).toEqual({ artist: '', trackTitle: '' })
      expect(result.current.editedMetadata.title).toBe('')
    })
  })
})
