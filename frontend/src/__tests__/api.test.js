import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from 'axios'
import { submitRfp, getJobStatus, exportDocx } from '../services/api'

// Mock axios.create to return a controllable instance
vi.mock('axios', () => {
  const instance = {
    get: vi.fn(),
    post: vi.fn(),
  }
  return {
    default: {
      create: vi.fn().mockReturnValue(instance),
    },
  }
})

function getInstance() {
  return axios.create()
}

describe('submitRfp', () => {
  beforeEach(() => vi.clearAllMocks())

  it('posts to /submit and returns response data', async () => {
    getInstance().post.mockResolvedValue({ data: { job_id: 'abc-123', status: 'pending' } })

    const result = await submitRfp({
      name: 'Jane Smith',
      email: 'jane@firm.com',
      purpose: 'Testing',
      rfpUrl: 'https://example.gov/rfp.pdf',
      rfpFile: null,
      recaptchaToken: 'test-token',
    })

    expect(getInstance().post).toHaveBeenCalledWith('/submit', expect.any(FormData))
    expect(result).toEqual({ job_id: 'abc-123', status: 'pending' })
  })

  it('includes rfp_url in FormData when provided', async () => {
    getInstance().post.mockResolvedValue({ data: { job_id: 'abc-123' } })

    await submitRfp({
      name: 'Jane',
      email: 'jane@firm.com',
      purpose: 'Testing',
      rfpUrl: 'https://example.gov/rfp.pdf',
      rfpFile: null,
      recaptchaToken: 'token',
    })

    const formData = getInstance().post.mock.calls[0][1]
    expect(formData.get('rfp_url')).toBe('https://example.gov/rfp.pdf')
  })

  it('includes rfp_file in FormData when provided', async () => {
    getInstance().post.mockResolvedValue({ data: { job_id: 'abc-123' } })
    const file = new File(['%PDF-'], 'test.pdf', { type: 'application/pdf' })

    await submitRfp({
      name: 'Jane',
      email: 'jane@firm.com',
      purpose: 'Testing',
      rfpUrl: null,
      rfpFile: file,
      recaptchaToken: 'token',
    })

    const formData = getInstance().post.mock.calls[0][1]
    expect(formData.get('rfp_file')).toBe(file)
  })

  it('does not include rfp_url when null', async () => {
    getInstance().post.mockResolvedValue({ data: { job_id: 'abc-123' } })

    await submitRfp({
      name: 'Jane',
      email: 'jane@firm.com',
      purpose: 'Testing',
      rfpUrl: null,
      rfpFile: new File(['%PDF-'], 'test.pdf'),
      recaptchaToken: 'token',
    })

    const formData = getInstance().post.mock.calls[0][1]
    expect(formData.get('rfp_url')).toBeNull()
  })

  it('includes recaptcha_token in FormData', async () => {
    getInstance().post.mockResolvedValue({ data: { job_id: 'abc-123' } })

    await submitRfp({
      name: 'Jane',
      email: 'jane@firm.com',
      purpose: 'Testing',
      rfpUrl: 'https://example.gov/rfp.pdf',
      rfpFile: null,
      recaptchaToken: 'my-recaptcha-token',
    })

    const formData = getInstance().post.mock.calls[0][1]
    expect(formData.get('recaptcha_token')).toBe('my-recaptcha-token')
  })

  it('propagates errors', async () => {
    getInstance().post.mockRejectedValue(new Error('Network error'))
    await expect(
      submitRfp({ name: 'Jane', email: 'j@j.com', purpose: 'Test', rfpUrl: 'https://example.gov/r.pdf', rfpFile: null, recaptchaToken: 'x' })
    ).rejects.toThrow('Network error')
  })
})

describe('getJobStatus', () => {
  beforeEach(() => vi.clearAllMocks())

  it('calls GET /status/{jobId}', async () => {
    getInstance().get.mockResolvedValue({ data: { status: 'complete', result: {} } })

    const result = await getJobStatus('test-job-id')

    expect(getInstance().get).toHaveBeenCalledWith('/status/test-job-id')
    expect(result).toEqual({ status: 'complete', result: {} })
  })

  it('propagates errors', async () => {
    getInstance().get.mockRejectedValue(new Error('Not found'))
    await expect(getJobStatus('bad-id')).rejects.toThrow('Not found')
  })
})

describe('exportDocx', () => {
  beforeEach(() => vi.clearAllMocks())

  it('posts to /export-docx with letter_text in FormData', async () => {
    const mockBlob = new Blob(['fake docx'], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })
    getInstance().post.mockResolvedValue({ data: mockBlob })

    const result = await exportDocx('Dear Committee,\n\nTest letter.')

    expect(getInstance().post).toHaveBeenCalledWith(
      '/export-docx',
      expect.any(FormData),
      expect.objectContaining({ responseType: 'blob' })
    )
    expect(result).toBe(mockBlob)
  })

  it('passes letter_text in the FormData body', async () => {
    const mockBlob = new Blob(['x'])
    getInstance().post.mockResolvedValue({ data: mockBlob })

    await exportDocx('My letter text')

    const formData = getInstance().post.mock.calls[0][1]
    expect(formData.get('letter_text')).toBe('My letter text')
  })
})
