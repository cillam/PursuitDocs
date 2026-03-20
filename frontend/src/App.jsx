import React, { useState, useCallback } from 'react';
import { GoogleReCaptchaProvider } from 'react-google-recaptcha-v3';
import Header from './components/Header';
import IntakeForm from './components/IntakeForm';
import ProgressIndicator from './components/ProgressIndicator';
import ResultsDisplay from './components/ResultsDisplay';
import ErrorDisplay from './components/ErrorDisplay';
import Footer from './components/Footer';
import { submitRfp } from './services/api';

const RECAPTCHA_SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY || '';

// App states: 'form' | 'processing' | 'results' | 'error'

function AppContent() {
  const [appState, setAppState] = useState('form');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [currentStage, setCurrentStage] = useState('parsing');
  const [iteration, setIteration] = useState(0);
  const [canRegenerate, setCanRegenerate] = useState(true);
  const [lastSubmission, setLastSubmission] = useState(null);

  const handleSubmit = useCallback(async (formData) => {
    setAppState('processing');
    setCurrentStage('parsing');
    setIteration(0);
    setLastSubmission(formData);

    try {
      // Simulate stage progression
      // In a real implementation with WebSocket or polling,
      // these would update based on actual backend progress
      const stageTimer = (stage, delay) =>
        new Promise(resolve => {
          setTimeout(() => {
            setCurrentStage(stage);
            resolve();
          }, delay);
        });

      // Start the actual API call
      const apiPromise = submitRfp(formData);

      // Simulate progress stages while waiting
      // These timings are approximate — the real call determines when we finish
      stageTimer('drafting', 8000);
      stageTimer('reviewing', 20000);
      stageTimer('revising', 40000);
      stageTimer('finalizing', 60000);

      const data = await apiPromise;

      setResult(data);
      setAppState('results');
    } catch (err) {
      console.error('Pipeline error:', err);
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
              iteration={iteration}
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
