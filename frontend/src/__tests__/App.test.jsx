import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import App from '../App'
import * as apiModule from '../services/api'

vi.mock('react-google-recaptcha-v3', () => ({
  GoogleReCaptchaProvider: ({ children }) => children,
  useGoogleReCaptcha: () => ({
    executeRecaptcha: vi.fn().mockResolvedValue('test-recaptcha-token'),
  }),
}))

vi.mock('../services/api', () => ({
  submitRfp: vi.fn(),
  getJobStatus: vi.fn(),
  exportDocx: vi.fn(),
}))

const MOCK_RESULT = {
  status: 'ready_for_review',
  final_letter: 'Dear Selection Committee,\n\nWe are pleased to submit this proposal.',
  change_log: [],
  parsed_rfp: { summary: 'Annual financial audit' },
  iterations: 1,
}

async function fillAndSubmitForm() {
  const user = userEvent.setup({ delay: null })
  await user.type(screen.getByLabelText(/^name$/i), 'Jane Smith')
  await user.type(screen.getByLabelText(/email/i), 'jane@firm.com')
  await user.type(screen.getByLabelText(/what are you using/i), 'Testing the tool')
  await user.type(screen.getByPlaceholderText(/example\.gov/i), 'https://example.gov/rfp.pdf')
  await user.click(screen.getByRole('button', { name: /generate proposal letter/i }))
}

describe('App — initial state', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders the intake form', () => {
    render(<App />)
    expect(screen.getByText('Generate Your Proposal Letter')).toBeInTheDocument()
  })

  it('does not show ProgressIndicator, ResultsDisplay, or ErrorDisplay', () => {
    render(<App />)
    expect(screen.queryByText(/extracting rfp content/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/your proposal letter is ready/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /try again/i })).not.toBeInTheDocument()
  })
})

describe('App — processing state', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows ProgressIndicator after submit', async () => {
    apiModule.submitRfp.mockResolvedValue({ job_id: 'job-123' })
    apiModule.getJobStatus.mockResolvedValue({ status: 'pending' })

    render(<App />)
    await fillAndSubmitForm()

    await waitFor(() => {
      expect(screen.getByText(/extracting rfp content/i)).toBeInTheDocument()
    })
  })

  it('calls submitRfp once on submit', async () => {
    apiModule.submitRfp.mockResolvedValue({ job_id: 'job-123' })
    apiModule.getJobStatus.mockResolvedValue({ status: 'pending' })

    render(<App />)
    await fillAndSubmitForm()

    expect(apiModule.submitRfp).toHaveBeenCalledOnce()
  })
})

describe('App — results state', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows ResultsDisplay when poll returns complete', async () => {
    apiModule.submitRfp.mockResolvedValue({ job_id: 'job-123' })
    apiModule.getJobStatus.mockResolvedValue({ status: 'complete', result: MOCK_RESULT })

    render(<App />)
    await fillAndSubmitForm()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4100)
    })

    await waitFor(() => {
      expect(screen.getByText('Your Proposal Letter is Ready')).toBeInTheDocument()
    })
  })

  it('polls getJobStatus every 4 seconds', async () => {
    apiModule.submitRfp.mockResolvedValue({ job_id: 'job-123' })
    apiModule.getJobStatus
      .mockResolvedValueOnce({ status: 'pending' })
      .mockResolvedValueOnce({ status: 'processing' })
      .mockResolvedValue({ status: 'complete', result: MOCK_RESULT })

    render(<App />)
    await fillAndSubmitForm()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4100)
    })
    expect(apiModule.getJobStatus).toHaveBeenCalledTimes(1)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000)
    })
    expect(apiModule.getJobStatus).toHaveBeenCalledTimes(2)
  })

  it('stops polling after result is received', async () => {
    apiModule.submitRfp.mockResolvedValue({ job_id: 'job-123' })
    apiModule.getJobStatus.mockResolvedValue({ status: 'complete', result: MOCK_RESULT })

    render(<App />)
    await fillAndSubmitForm()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4100)
    })

    const callCount = apiModule.getJobStatus.mock.calls.length

    await act(async () => {
      await vi.advanceTimersByTimeAsync(8000)
    })

    expect(apiModule.getJobStatus.mock.calls.length).toBe(callCount)
  })
})

describe('App — error state', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows ErrorDisplay when poll returns error status', async () => {
    apiModule.submitRfp.mockResolvedValue({ job_id: 'job-123' })
    apiModule.getJobStatus.mockResolvedValue({ status: 'error', error: 'Pipeline failed.' })

    render(<App />)
    await fillAndSubmitForm()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4100)
    })

    await waitFor(() => {
      expect(screen.getByText('Pipeline failed.')).toBeInTheDocument()
    })
  })

  it('shows error message when submitRfp throws', async () => {
    apiModule.submitRfp.mockRejectedValue({ message: 'Network error' })

    render(<App />)
    await fillAndSubmitForm()

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument()
    })
  })

  it('shows error when poll network request fails', async () => {
    apiModule.submitRfp.mockResolvedValue({ job_id: 'job-123' })
    apiModule.getJobStatus.mockRejectedValue(new Error('Connection lost'))

    render(<App />)
    await fillAndSubmitForm()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4100)
    })

    await waitFor(() => {
      expect(screen.getByText(/lost connection/i)).toBeInTheDocument()
    })
  })
})

describe('App — retry / regenerate', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('Try Again button returns user to the form', async () => {
    apiModule.submitRfp.mockRejectedValue({ message: 'Server error' })

    render(<App />)
    await fillAndSubmitForm()

    await waitFor(() => screen.getByRole('button', { name: /try again/i }))

    const user = userEvent.setup({ delay: null })
    await user.click(screen.getByRole('button', { name: /try again/i }))

    expect(screen.getByText('Generate Your Proposal Letter')).toBeInTheDocument()
  })

  it('Regenerate triggers a new submission with a fresh recaptcha token', async () => {
    apiModule.submitRfp.mockResolvedValue({ job_id: 'job-123' })
    apiModule.getJobStatus.mockResolvedValue({ status: 'complete', result: MOCK_RESULT })

    render(<App />)
    await fillAndSubmitForm()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4100)
    })

    await waitFor(() => screen.getByRole('button', { name: /regenerate/i }))

    const user = userEvent.setup({ delay: null })
    await user.click(screen.getByRole('button', { name: /regenerate/i }))

    // submitRfp should have been called twice total
    expect(apiModule.submitRfp).toHaveBeenCalledTimes(2)
  })
})
