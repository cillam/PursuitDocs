import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import ResultsDisplay from '../components/ResultsDisplay'

// Mock the API module (used by the export-docx button)
vi.mock('../services/api', () => ({
  exportDocx: vi.fn().mockResolvedValue(new Blob(['fake docx'])),
}))

// Mock URL.createObjectURL and URL.revokeObjectURL (not available in jsdom)
global.URL.createObjectURL = vi.fn().mockReturnValue('blob:fake')
global.URL.revokeObjectURL = vi.fn()

const READY_RESULT = {
  status: 'ready_for_review',
  final_letter: 'Dear Selection Committee,\n\nWe are pleased to submit this proposal.\n\nSincerely,\nTest Firm LLP',
  change_log: [],
  parsed_rfp: { summary: 'Annual financial audit for City of Testville', services: ['Financial audit'] },
  iterations: 1,
}

const NOT_APPLICABLE_RESULT = {
  status: 'not_applicable',
  final_letter: 'This RFP is seeking community satisfaction research, not audit services.',
  change_log: [],
  parsed_rfp: {},
  iterations: 0,
}

const WITH_CHANGES_RESULT = {
  ...READY_RESULT,
  iterations: 2,
  change_log: [
    {
      iteration: 0,
      flagged_text: 'We will continue to work with you',
      reason: 'Implies ongoing relationship that could impair independence',
      pcaob_citation: 'ET Section 1.100.001',
      suggested_alternative: 'We propose to provide the following services',
    },
  ],
}

function renderResults(result = READY_RESULT, overrides = {}) {
  const onRegenerate = vi.fn()
  const onRetry = vi.fn()
  render(
    <ResultsDisplay
      result={result}
      onRegenerate={onRegenerate}
      canRegenerate={true}
      onRetry={onRetry}
      {...overrides}
    />
  )
  return { onRegenerate, onRetry }
}

describe('ResultsDisplay — ready_for_review', () => {
  it('shows Ready for Review heading', () => {
    renderResults()
    expect(screen.getByText('Your Proposal Letter is Ready')).toBeInTheDocument()
  })

  it('shows Ready for Review status badge', () => {
    renderResults()
    expect(screen.getByText('Ready for Review')).toBeInTheDocument()
  })

  it('shows iteration count', () => {
    renderResults()
    expect(screen.getByText(/1 revision pass/i)).toBeInTheDocument()
  })

  it('displays the letter text in the default tab', () => {
    renderResults()
    expect(screen.getByText(/dear selection committee/i)).toBeInTheDocument()
  })

  it('shows Regenerate button when canRegenerate is true', () => {
    renderResults()
    expect(screen.getByRole('button', { name: /regenerate/i })).toBeInTheDocument()
  })

  it('hides Regenerate button when canRegenerate is false', () => {
    renderResults(READY_RESULT, { canRegenerate: false })
    expect(screen.queryByRole('button', { name: /regenerate/i })).not.toBeInTheDocument()
  })

  it('calls onRegenerate when Regenerate button is clicked', async () => {
    const user = userEvent.setup()
    const { onRegenerate } = renderResults()
    await user.click(screen.getByRole('button', { name: /regenerate/i }))
    expect(onRegenerate).toHaveBeenCalledOnce()
  })

  it('shows Copy Letter button', () => {
    renderResults()
    expect(screen.getByRole('button', { name: /copy letter/i })).toBeInTheDocument()
  })

  it('shows Download .txt button', () => {
    renderResults()
    expect(screen.getByRole('button', { name: /download .txt/i })).toBeInTheDocument()
  })

  it('shows Download .docx button', () => {
    renderResults()
    expect(screen.getByRole('button', { name: /download .docx/i })).toBeInTheDocument()
  })

  it('shows Download JSON button', () => {
    renderResults()
    expect(screen.getByRole('button', { name: /download json/i })).toBeInTheDocument()
  })
})

describe('ResultsDisplay — needs_revision', () => {
  const needsRevision = { ...READY_RESULT, status: 'needs_revision' }

  it('shows Review Required heading', () => {
    renderResults(needsRevision)
    expect(screen.getByText('Review Required')).toBeInTheDocument()
  })

  it('shows Needs Revision status badge', () => {
    renderResults(needsRevision)
    expect(screen.getByText('Needs Revision')).toBeInTheDocument()
  })
})

describe('ResultsDisplay — not_applicable', () => {
  it('shows Document Not Accepted heading', () => {
    renderResults(NOT_APPLICABLE_RESULT)
    expect(screen.getByText('Document Not Accepted')).toBeInTheDocument()
  })

  it('shows the not_applicable message from final_letter', () => {
    renderResults(NOT_APPLICABLE_RESULT)
    expect(screen.getByText('This RFP is seeking community satisfaction research, not audit services.')).toBeInTheDocument()
  })

  it('shows Submit Another RFP button', () => {
    renderResults(NOT_APPLICABLE_RESULT)
    expect(screen.getByRole('button', { name: /submit another rfp/i })).toBeInTheDocument()
  })

  it('Submit Another RFP calls onRetry', async () => {
    const user = userEvent.setup()
    const { onRetry, onRegenerate } = renderResults(NOT_APPLICABLE_RESULT)
    await user.click(screen.getByRole('button', { name: /submit another rfp/i }))
    expect(onRetry).toHaveBeenCalledOnce()
    expect(onRegenerate).not.toHaveBeenCalled()
  })

  it('does not show the tab bar', () => {
    renderResults(NOT_APPLICABLE_RESULT)
    expect(screen.queryByRole('button', { name: /proposal letter/i })).not.toBeInTheDocument()
  })
})

describe('ResultsDisplay — tab navigation', () => {
  it('Change Log tab shows empty state when no changes', async () => {
    const user = userEvent.setup()
    renderResults()
    await user.click(screen.getByRole('button', { name: /change log/i }))
    expect(screen.getByText(/no independence issues were found/i)).toBeInTheDocument()
  })

  it('Change Log tab shows count badge when changes exist', () => {
    renderResults(WITH_CHANGES_RESULT)
    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('Change Log tab displays flagged text', async () => {
    const user = userEvent.setup()
    renderResults(WITH_CHANGES_RESULT)
    await user.click(screen.getByRole('button', { name: /change log/i }))
    expect(screen.getByText(/we will continue to work with you/i)).toBeInTheDocument()
  })

  it('Change Log tab displays PCAOB citation', async () => {
    const user = userEvent.setup()
    renderResults(WITH_CHANGES_RESULT)
    await user.click(screen.getByRole('button', { name: /change log/i }))
    expect(screen.getByText('ET Section 1.100.001')).toBeInTheDocument()
  })

  it('Parsed RFP tab shows JSON', async () => {
    const user = userEvent.setup()
    renderResults()
    await user.click(screen.getByRole('button', { name: /parsed rfp/i }))
    expect(screen.getByText(/annual financial audit/i)).toBeInTheDocument()
  })

  it('switching back to letter tab shows letter', async () => {
    const user = userEvent.setup()
    renderResults()
    await user.click(screen.getByRole('button', { name: /change log/i }))
    await user.click(screen.getByRole('button', { name: /proposal letter/i }))
    expect(screen.getByText(/dear selection committee/i)).toBeInTheDocument()
  })
})
