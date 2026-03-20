import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 600000, // 10 minutes — pipeline can take a while
});

/**
 * Submit an RFP for processing.
 *
 * @param {Object} params
 * @param {string} params.name - User's name
 * @param {string} params.email - User's email
 * @param {string} params.purpose - What they're using the tool for
 * @param {string} [params.rfpUrl] - URL to an RFP (if not uploading a file)
 * @param {File} [params.rfpFile] - Uploaded PDF file
 * @param {string} params.recaptchaToken - reCAPTCHA v3 token
 * @returns {Promise<Object>} Pipeline result
 */
export async function submitRfp({ name, email, purpose, rfpUrl, rfpFile, recaptchaToken }) {
  const formData = new FormData();
  formData.append('name', name);
  formData.append('email', email);
  formData.append('purpose', purpose);
  formData.append('recaptcha_token', recaptchaToken);

  if (rfpFile) {
    formData.append('rfp_file', rfpFile);
  } else if (rfpUrl) {
    formData.append('rfp_url', rfpUrl);
  }

  const response = await api.post('/submit', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

  return response.data;
}

/**
 * Check the status of a running pipeline.
 *
 * @param {string} jobId - The job ID returned from submitRfp
 * @returns {Promise<Object>} Current status and results if complete
 */
export async function checkStatus(jobId) {
  const response = await api.get(`/status/${jobId}`);
  return response.data;
}

/**
 * Export the letter as a Word document.
 *
 * @param {string} letterText - The letter content
 * @returns {Promise<Blob>} The .docx file as a Blob
 */
export async function exportDocx(letterText) {
  const formData = new FormData();
  formData.append('letter_text', letterText);

  const response = await api.post('/export-docx', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    responseType: 'blob',
  });

  return response.data;
}
