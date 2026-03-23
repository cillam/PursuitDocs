import React, { useState, useCallback, useRef } from 'react';
import { GoogleReCaptchaProvider } from 'react-google-recaptcha-v3';
import Header from './components/Header';
import IntakeForm from './components/IntakeForm';
import ProgressIndicator from './components/ProgressIndicator';
import ResultsDisplay from './components/ResultsDisplay';
import ErrorDisplay from './components/ErrorDisplay';
import Footer from './components/Footer';
import { submitRfp, getJobStatus } from './services/api';

const RECAPTCHA_SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY || '';

// App states: 'form' | 'processing' | 'results' | 'error'

function AppContent() {
  const [appState, setAppState] = useState('form');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [currentStage, setCurrentStage] = useState('parsing');
  const [canRegenerate, setCanRegenerate] = useState(true);
  const [lastSubmission, setLastSubmission] = useState(null);
  const stageTimers = useRef([]);
  const pollTimer = useRef(null);

  const clearStageTimers = () => {
    stageTimers.current.forEach(clearTimeout);
    stageTimers.current = [];
  };

  const clearPollTimer = () => {
    if (pollTimer.current) {
      clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  };

  const handleSubmit = useCallback(async (formData) => {
    setAppState('processing');
    setCurrentStage('parsing');
    setLastSubmission(formData);
    clearStageTimers();
    clearPollTimer();

    // Simulate progress stages while waiting for results.
    // Timings are approximate — the poll result determines when we finish.
    stageTimers.current = [
      setTimeout(() => setCurrentStage('drafting'), 8000),
      setTimeout(() => setCurrentStage('reviewing'), 20000),
      setTimeout(() => setCurrentStage('revising'), 40000),
      setTimeout(() => setCurrentStage('finalizing'), 60000),
    ];

    try {
      const { job_id } = await submitRfp(formData);

      pollTimer.current = setInterval(async () => {
        try {
          const { status, result, error } = await getJobStatus(job_id);
          if (status === 'complete') {
            clearPollTimer();
            clearStageTimers();
            setResult(result);
            setAppState('results');
          } else if (status === 'error') {
            clearPollTimer();
            clearStageTimers();
            setError(error || 'Pipeline failed. Please try again.');
            setAppState('error');
          }
          // pending | processing — keep polling
        } catch (pollErr) {
          clearPollTimer();
          clearStageTimers();
          setError('Lost connection while waiting for results. Please try again.');
          setAppState('error');
        }
      }, 4000);
    } catch (err) {
      console.error('Submit error:', err);
      clearStageTimers();
      const message = err.response?.data?.detail
        || err.response?.data?.error
        || err.message
        || 'An unexpected error occurred. Please try again.';
      setError(message);
      setAppState('error');
    }
  }, []);

  const handleRegenerate = useCallback(async () => {
    if (!lastSubmission || !canRegenerate) return;
    setCanRegenerate(false);
    await handleSubmit(lastSubmission);
  }, [lastSubmission, canRegenerate, handleSubmit]);

  const handleRetry = useCallback(() => {
    clearPollTimer();
    setAppState('form');
    setError('');
    setResult(null);
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      <main className="flex-1 flex items-start justify-center px-4 sm:px-8 py-8 sm:py-16">
        <div className="w-full max-w-4xl">
          {appState === 'form' && (
            <IntakeForm onSubmit={handleSubmit} isLoading={false} />
          )}

          {appState === 'processing' && (
            <ProgressIndicator
              currentStage={currentStage}
            />
          )}

          {appState === 'results' && result && (
            <ResultsDisplay
              result={result}
              onRegenerate={handleRegenerate}
              canRegenerate={canRegenerate}
            />
          )}

          {appState === 'error' && (
            <ErrorDisplay message={error} onRetry={handleRetry} />
          )}
        </div>
      </main>

      <Footer />
    </div>
  );
}

export default function App() {
  return (
    <GoogleReCaptchaProvider reCaptchaKey={RECAPTCHA_SITE_KEY}>
      <AppContent />
    </GoogleReCaptchaProvider>
  );
}
