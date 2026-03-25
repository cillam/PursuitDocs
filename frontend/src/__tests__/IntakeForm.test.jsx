import { render, screen, fireEvent, createEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import IntakeForm from '../components/IntakeForm'

vi.mock('react-google-recaptcha-v3', () => ({
  useGoogleReCaptcha: () => ({
    executeRecaptcha: vi.fn().mockResolvedValue('test-recaptcha-token'),
  }),
}))

function renderForm(props = {}) {
  const onSubmit = vi.fn()
  render(<IntakeForm onSubmit={onSubmit} isLoading={false} {...props} />)
  return { onSubmit }
}

function fillBaseFields(user) {
  return async () => {
    await user.type(screen.getByLabelText(/^name$/i), 'Jane Smith')
    await user.type(screen.getByLabelText(/email/i), 'jane@firm.com')
    await user.type(screen.getByLabelText(/what are you using/i), 'Testing the tool')
  }
}

describe('IntakeForm — rendering', () => {
  it('renders the form heading', () => {
    renderForm()
    expect(screen.getByText('Generate Your Proposal Letter')).toBeInTheDocument()
  })

  it('shows URL input by default', () => {
    renderForm()
    expect(screen.getByPlaceholderText(/example\.gov/i)).toBeInTheDocument()
  })

  it('shows file upload area after clicking Upload PDF', async () => {
    const user = userEvent.setup()
    renderForm()
    await user.click(screen.getByRole('button', { name: /upload pdf/i }))
    expect(screen.getByText(/drop a pdf here/i)).toBeInTheDocument()
  })

  it('hides the URL input after switching to file mode', async () => {
    const user = userEvent.setup()
    renderForm()
    await user.click(screen.getByRole('button', { name: /upload pdf/i }))
    expect(screen.queryByPlaceholderText(/example\.gov/i)).not.toBeInTheDocument()
  })

  it('submit button text is Generate Proposal Letter', () => {
    renderForm()
    expect(screen.getByRole('button', { name: /generate proposal letter/i })).toBeInTheDocument()
  })

  it('shows loading spinner when isLoading is true', () => {
    renderForm({ isLoading: true })
    expect(screen.getByText(/processing/i)).toBeInTheDocument()
  })
})

describe('IntakeForm — validation', () => {
  it('shows error when name is empty', async () => {
    const user = userEvent.setup()
    renderForm()
    await user.type(screen.getByLabelText(/email/i), 'jane@firm.com')
    await user.type(screen.getByLabelText(/what are you using/i), 'Testing')
    await user.type(screen.getByPlaceholderText(/example\.gov/i), 'https://example.gov/rfp.pdf')
    await user.click(screen.getByRole('button', { name: /generate/i }))
    expect(screen.getByText('Name is required.')).toBeInTheDocument()
  })

  it('shows error when email is empty', async () => {
    const user = userEvent.setup()
    renderForm()
    await user.type(screen.getByLabelText(/^name$/i), 'Jane')
    await user.type(screen.getByLabelText(/what are you using/i), 'Testing')
    await user.type(screen.getByPlaceholderText(/example\.gov/i), 'https://example.gov/rfp.pdf')
    await user.click(screen.getByRole('button', { name: /generate/i }))
    expect(screen.getByText('Email is required.')).toBeInTheDocument()
  })

  it('shows error for invalid email format', async () => {
    const user = userEvent.setup()
    renderForm()
    await user.type(screen.getByLabelText(/^name$/i), 'Jane')
    await user.type(screen.getByLabelText(/email/i), 'not-an-email')
    await user.type(screen.getByLabelText(/what are you using/i), 'Testing')
    await user.type(screen.getByPlaceholderText(/example\.gov/i), 'https://example.gov/rfp.pdf')
    await user.click(screen.getByRole('button', { name: /generate/i }))
    expect(screen.getByText(/valid email/i)).toBeInTheDocument()
  })

  it('shows error when purpose is empty', async () => {
    const user = userEvent.setup()
    renderForm()
    await user.type(screen.getByLabelText(/^name$/i), 'Jane')
    await user.type(screen.getByLabelText(/email/i), 'jane@firm.com')
    await user.type(screen.getByPlaceholderText(/example\.gov/i), 'https://example.gov/rfp.pdf')
    await user.click(screen.getByRole('button', { name: /generate/i }))
    expect(screen.getByText(/describe your intended use/i)).toBeInTheDocument()
  })

  it('shows error when URL is empty in URL mode', async () => {
    const user = userEvent.setup()
    renderForm()
    await user.type(screen.getByLabelText(/^name$/i), 'Jane')
    await user.type(screen.getByLabelText(/email/i), 'jane@firm.com')
    await user.type(screen.getByLabelText(/what are you using/i), 'Testing')
    await user.click(screen.getByRole('button', { name: /generate/i }))
    expect(screen.getByText(/enter an RFP URL/i)).toBeInTheDocument()
  })

  it('shows error for .com URL', async () => {
    const user = userEvent.setup()
    renderForm()
    await user.type(screen.getByLabelText(/^name$/i), 'Jane')
    await user.type(screen.getByLabelText(/email/i), 'jane@firm.com')
    await user.type(screen.getByLabelText(/what are you using/i), 'Testing')
    await user.type(screen.getByPlaceholderText(/example\.gov/i), 'https://example.com/rfp.pdf')
    await user.click(screen.getByRole('button', { name: /generate/i }))
    expect(screen.getByText(/approved domains/i)).toBeInTheDocument()
  })

  it('shows error when no file selected in file mode', async () => {
    const user = userEvent.setup()
    renderForm()
    await user.click(screen.getByRole('button', { name: /upload pdf/i }))
    await user.type(screen.getByLabelText(/^name$/i), 'Jane')
    await user.type(screen.getByLabelText(/email/i), 'jane@firm.com')
    await user.type(screen.getByLabelText(/what are you using/i), 'Testing')
    await user.click(screen.getByRole('button', { name: /generate/i }))
    expect(screen.getByText(/select a PDF file/i)).toBeInTheDocument()
  })

  it('clears error on field change', async () => {
    const user = userEvent.setup()
    renderForm()
    await user.click(screen.getByRole('button', { name: /generate/i }))
    expect(screen.getByText('Name is required.')).toBeInTheDocument()
    await user.type(screen.getByLabelText(/^name$/i), 'J')
    expect(screen.queryByText('Name is required.')).not.toBeInTheDocument()
  })
})

describe('IntakeForm — file validation', () => {
  it('shows error for non-PDF file type', async () => {
    const user = userEvent.setup()
    renderForm()
    await user.click(screen.getByRole('button', { name: /upload pdf/i }))

    const file = new File(['fake content'], 'doc.docx', { type: 'application/msword' })
    const input = document.querySelector('input[type="file"]')
    // fireEvent bypasses userEvent's accept-attribute filter, simulating a user
    // who submits a non-PDF despite the file picker restriction
    fireEvent.change(input, { target: { files: [file] } })

    expect(screen.getByText(/only PDF/i)).toBeInTheDocument()
  })

  it('shows error for oversized file', async () => {
    const user = userEvent.setup()
    renderForm()
    await user.click(screen.getByRole('button', { name: /upload pdf/i }))

    const largeFile = new File(['x'.repeat(1)], 'large.pdf', { type: 'application/pdf' })
    Object.defineProperty(largeFile, 'size', { value: 11 * 1024 * 1024 })
    const input = document.querySelector('input[type="file"]')
    await user.upload(input, largeFile)

    expect(screen.getByText(/exceeds the 10 MB limit/i)).toBeInTheDocument()
  })

  it('shows filename after valid file is selected', async () => {
    const user = userEvent.setup()
    renderForm()
    await user.click(screen.getByRole('button', { name: /upload pdf/i }))

    const file = new File(['%PDF-1.4 content'], 'my-rfp.pdf', { type: 'application/pdf' })
    const input = document.querySelector('input[type="file"]')
    await user.upload(input, file)

    expect(screen.getByText('my-rfp.pdf')).toBeInTheDocument()
  })
})

describe('IntakeForm — drag and drop', () => {
  it('accepts a valid PDF dropped onto the drop zone', async () => {
    renderForm()
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /upload pdf/i }))

    const file = new File(['%PDF-1.4 content'], 'dropped.pdf', { type: 'application/pdf' })
    const dropZone = screen.getByText(/drop a pdf here/i).closest('label')

    const dropEvent = createEvent.drop(dropZone)
    Object.defineProperty(dropEvent, 'dataTransfer', { value: { files: [file] } })
    fireEvent(dropZone, dropEvent)

    expect(screen.getByText('dropped.pdf')).toBeInTheDocument()
  })

  it('rejects a non-PDF dropped onto the drop zone', async () => {
    renderForm()
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /upload pdf/i }))

    const file = new File(['content'], 'report.docx', { type: 'application/msword' })
    const dropZone = screen.getByText(/drop a pdf here/i).closest('label')

    const dropEvent = createEvent.drop(dropZone)
    Object.defineProperty(dropEvent, 'dataTransfer', { value: { files: [file] } })
    fireEvent(dropZone, dropEvent)

    expect(screen.getByText(/only PDF/i)).toBeInTheDocument()
  })
})

describe('IntakeForm — submission', () => {
  it('calls onSubmit with correct data for URL mode', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderForm()

    await user.type(screen.getByLabelText(/^name$/i), 'Jane Smith')
    await user.type(screen.getByLabelText(/email/i), 'jane@firm.com')
    await user.type(screen.getByLabelText(/what are you using/i), 'Testing the tool')
    await user.type(screen.getByPlaceholderText(/example\.gov/i), 'https://example.gov/rfp.pdf')
    await user.click(screen.getByRole('button', { name: /generate/i }))

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Jane Smith',
        email: 'jane@firm.com',
        purpose: 'Testing the tool',
        rfpUrl: 'https://example.gov/rfp.pdf',
        rfpFile: null,
        recaptchaToken: 'test-recaptcha-token',
      })
    )
  })

  it('includes rfpFile and null rfpUrl in file mode', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderForm()

    await user.click(screen.getByRole('button', { name: /upload pdf/i }))
    await user.type(screen.getByLabelText(/^name$/i), 'Jane Smith')
    await user.type(screen.getByLabelText(/email/i), 'jane@firm.com')
    await user.type(screen.getByLabelText(/what are you using/i), 'Testing')

    const file = new File(['%PDF-1.4'], 'rfp.pdf', { type: 'application/pdf' })
    const input = document.querySelector('input[type="file"]')
    await user.upload(input, file)

    await user.click(screen.getByRole('button', { name: /generate/i }))

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        rfpFile: file,
        rfpUrl: null,
      })
    )
  })

  it('does not call onSubmit when honeypot field is filled', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderForm()

    // Fill valid form fields
    await user.type(screen.getByLabelText(/^name$/i), 'Jane')
    await user.type(screen.getByLabelText(/email/i), 'jane@firm.com')
    await user.type(screen.getByLabelText(/what are you using/i), 'Testing')
    await user.type(screen.getByPlaceholderText(/example\.gov/i), 'https://example.gov/rfp.pdf')

    // Fill the honeypot (hidden field)
    const honeypot = document.querySelector('input[name="company_website"]')
    await user.type(honeypot, 'https://spam.com')

    await user.click(screen.getByRole('button', { name: /generate/i }))

    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('does not call onSubmit when validation fails', async () => {
    const user = userEvent.setup()
    const { onSubmit } = renderForm()
    await user.click(screen.getByRole('button', { name: /generate/i }))
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
