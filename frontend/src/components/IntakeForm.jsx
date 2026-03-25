import React, { useState, useCallback } from 'react';
import { useGoogleReCaptcha } from 'react-google-recaptcha-v3';

const ALLOWED_DOMAINS = ['.gov', '.edu', '.org', '.us'];
const MAX_FILE_SIZE_MB = 10;

function validateUrl(url) {
  if (!url) return null;

  try {
    const parsed = new URL(url);

    if (!['http:', 'https:'].includes(parsed.protocol)) {
      return 'Only http and https URLs are allowed.';
    }

    const hostname = parsed.hostname.toLowerCase();
    const isAllowed = ALLOWED_DOMAINS.some(domain => hostname.endsWith(domain));
    if (!isAllowed) {
      return `Only URLs from approved domains are accepted (${ALLOWED_DOMAINS.join(', ')}).`;
    }

    return null;
  } catch {
    return 'Please enter a valid URL.';
  }
}

function validateFile(file) {
  if (!file) return null;

  if (file.type !== 'application/pdf') {
    return 'Only PDF files are accepted.';
  }

  const sizeMB = file.size / (1024 * 1024);
  if (sizeMB > MAX_FILE_SIZE_MB) {
    return `File size (${sizeMB.toFixed(1)} MB) exceeds the ${MAX_FILE_SIZE_MB} MB limit.`;
  }

  return null;
}

export default function IntakeForm({ onSubmit, isLoading }) {
  const { executeRecaptcha } = useGoogleReCaptcha();

  const [inputMode, setInputMode] = useState('url'); // 'url' or 'file'
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    purpose: '',
    rfpUrl: '',
    rfpFile: null,
    // Honeypot
    company_website: '',
  });
  const [errors, setErrors] = useState({});
  const [fileName, setFileName] = useState('');
  const [isDragging, setIsDragging] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    // Clear error on change
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: null }));
    }
  };

  const applyFile = (file) => {
    const error = validateFile(file);
    if (error) {
      setErrors(prev => ({ ...prev, rfpFile: error }));
      setFormData(prev => ({ ...prev, rfpFile: null }));
      setFileName('');
      return;
    }
    setFormData(prev => ({ ...prev, rfpFile: file }));
    setFileName(file.name);
    setErrors(prev => ({ ...prev, rfpFile: null }));
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) applyFile(file);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    if (!isLoading) setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (isLoading) return;
    const file = e.dataTransfer.files[0];
    if (file) applyFile(file);
  };

  const handleSubmit = useCallback(async (e) => {
    e.preventDefault();

    // Honeypot check — if filled, silently reject
    if (formData.company_website) {
      // Pretend to submit
      return;
    }

    // Validate
    const newErrors = {};

    if (!formData.name.trim()) newErrors.name = 'Name is required.';
    if (!formData.email.trim()) newErrors.email = 'Email is required.';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Please enter a valid email address.';
    }
    if (!formData.purpose.trim()) newErrors.purpose = 'Please describe your intended use.';

    if (inputMode === 'url') {
      if (!formData.rfpUrl.trim()) {
        newErrors.rfpUrl = 'Please enter an RFP URL.';
      } else {
        const urlError = validateUrl(formData.rfpUrl);
        if (urlError) newErrors.rfpUrl = urlError;
      }
    } else {
      if (!formData.rfpFile) {
        newErrors.rfpFile = 'Please select a PDF file.';
      }
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    // Get reCAPTCHA token (skip in dev if no site key)
    let token = 'dev-bypass';
    if (executeRecaptcha) {
      try {
        token = await executeRecaptcha('submit_rfp');
      } catch (err) {
        setErrors({ submit: 'reCAPTCHA verification failed. Please try again.' });
        return;
      }
    }

    onSubmit({
      name: formData.name,
      email: formData.email,
      purpose: formData.purpose,
      rfpUrl: inputMode === 'url' ? formData.rfpUrl : null,
      rfpFile: inputMode === 'file' ? formData.rfpFile : null,
      recaptchaToken: token,
    });
  }, [formData, inputMode, executeRecaptcha, onSubmit]);

  return (
    <div className="animate-fade-up">
      {/* Intro */}
      <div className="text-center mb-10">
        <h2 className="font-display text-3xl sm:text-4xl text-ink-50 mb-4">
          Generate Your Proposal Letter
        </h2>
        <p className="text-ink-400 max-w-xl mx-auto leading-relaxed">
          Upload an RFP for financial statement audit services and PursuitDocs will
          draft a compliant proposal transmittal letter, review it for independence
          concerns, and iteratively revise until it's ready for your review.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="card p-8 max-w-2xl mx-auto space-y-6" noValidate>
        {/* Honeypot — hidden from humans */}
        <div className="absolute opacity-0 pointer-events-none" aria-hidden="true" tabIndex={-1}>
          <label htmlFor="company_website">Company Website</label>
          <input
            type="text"
            id="company_website"
            name="company_website"
            value={formData.company_website}
            onChange={handleChange}
            autoComplete="off"
            tabIndex={-1}
          />
        </div>

        {/* Name & Email */}
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="name" className="block text-sm text-ink-400 mb-1.5 font-medium">
              Name
            </label>
            <input
              type="text"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleChange}
              className="input-field"
              placeholder="Your name"
              disabled={isLoading}
            />
            {errors.name && <p className="text-red-400 text-xs mt-1">{errors.name}</p>}
          </div>
          <div>
            <label htmlFor="email" className="block text-sm text-ink-400 mb-1.5 font-medium">
              Email
            </label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              className="input-field"
              placeholder="you@firm.com"
              disabled={isLoading}
            />
            {errors.email && <p className="text-red-400 text-xs mt-1">{errors.email}</p>}
          </div>
        </div>

        {/* Purpose */}
        <div>
          <label htmlFor="purpose" className="block text-sm text-ink-400 mb-1.5 font-medium">
            What are you using this tool for?
          </label>
          <textarea
            id="purpose"
            name="purpose"
            value={formData.purpose}
            onChange={handleChange}
            className="input-field resize-none h-20"
            placeholder="e.g., Evaluating PursuitDocs for our firm's proposal workflow"
            disabled={isLoading}
          />
          {errors.purpose && <p className="text-red-400 text-xs mt-1">{errors.purpose}</p>}
        </div>

        {/* RFP Input Mode Toggle */}
        <div>
          <label className="block text-sm text-ink-400 mb-2 font-medium">
            RFP Source
          </label>
          <div className="flex gap-2 mb-3">
            <button
              type="button"
              onClick={() => setInputMode('url')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                inputMode === 'url'
                  ? 'bg-ink-700 text-ink-100 border border-ink-600'
                  : 'bg-ink-900/40 text-ink-500 border border-ink-800 hover:text-ink-300'
              }`}
              disabled={isLoading}
            >
              URL
            </button>
            <button
              type="button"
              onClick={() => setInputMode('file')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                inputMode === 'file'
                  ? 'bg-ink-700 text-ink-100 border border-ink-600'
                  : 'bg-ink-900/40 text-ink-500 border border-ink-800 hover:text-ink-300'
              }`}
              disabled={isLoading}
            >
              Upload PDF
            </button>
          </div>

          {inputMode === 'url' ? (
            <div>
              <input
                type="url"
                name="rfpUrl"
                value={formData.rfpUrl}
                onChange={handleChange}
                className="input-field"
                placeholder="https://example.gov/rfp-audit-services.pdf"
                disabled={isLoading}
              />
              <p className="text-ink-600 text-xs mt-1.5">
                Financial statement audit RFPs only · Accepted domains: {ALLOWED_DOMAINS.join(', ')}
              </p>
              {errors.rfpUrl && <p className="text-red-400 text-xs mt-1">{errors.rfpUrl}</p>}
            </div>
          ) : (
            <div>
              <label
                htmlFor="rfpFile"
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`flex items-center justify-center gap-3 w-full py-8 border-2 border-dashed rounded-xl cursor-pointer transition-all ${
                  isDragging
                    ? 'border-brass-400 bg-brass-500/10'
                    : fileName
                      ? 'border-brass-500/40 bg-brass-500/5'
                      : 'border-ink-700/50 hover:border-ink-600 bg-ink-900/30'
                } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <input
                  type="file"
                  id="rfpFile"
                  accept=".pdf"
                  onChange={handleFileChange}
                  className="hidden"
                  disabled={isLoading}
                />
                {fileName ? (
                  <div className="text-center">
                    <p className="text-brass-400 font-medium text-sm">{fileName}</p>
                    <p className="text-ink-500 text-xs mt-1">Click to change file</p>
                  </div>
                ) : (
                  <div className="text-center">
                    <p className="text-ink-400 text-sm">Drop a PDF here or click to browse</p>
                    <p className="text-ink-600 text-xs mt-1">Financial statement audit RFPs only · PDF, max {MAX_FILE_SIZE_MB} MB</p>
                  </div>
                )}
              </label>
              {errors.rfpFile && <p className="text-red-400 text-xs mt-1">{errors.rfpFile}</p>}
            </div>
          )}
        </div>

        {/* Submit */}
        {errors.submit && (
          <p className="text-red-400 text-sm text-center">{errors.submit}</p>
        )}

        <button type="submit" className="btn-primary w-full" disabled={isLoading}>
          {isLoading ? (
            <>
              <span className="w-4 h-4 border-2 border-ink-950/30 border-t-ink-950 rounded-full animate-spin" />
              Processing...
            </>
          ) : (
            'Generate Proposal Letter'
          )}
        </button>

        <p className="text-ink-600 text-xs text-center">
          Protected by reCAPTCHA. Your RFP content is processed securely and not stored.
        </p>
      </form>
    </div>
  );
}
