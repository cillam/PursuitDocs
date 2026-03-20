import React, { useState, useEffect } from 'react';

const STAGES = [
  { key: 'parsing', label: 'Extracting RFP content', detail: 'Reading and parsing the document...' },
  { key: 'drafting', label: 'Drafting proposal letter', detail: 'Writing the transmittal letter...' },
  { key: 'reviewing', label: 'Reviewing for independence issues', detail: 'Scanning for PCAOB compliance concerns...' },
  { key: 'revising', label: 'Revising draft', detail: 'Addressing reviewer findings...' },
  { key: 'finalizing', label: 'Finalizing output', detail: 'Preparing your results...' },
];

export default function ProgressIndicator({ currentStage, iteration }) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setElapsedSeconds(prev => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };

  const currentIndex = STAGES.findIndex(s => s.key === currentStage);

  return (
    <div className="animate-fade-up max-w-lg mx-auto">
      <div className="text-center mb-10">
        <h2 className="font-display text-2xl text-ink-50 mb-2">
          Processing Your RFP
        </h2>
        <p className="text-ink-500 text-sm">
          Elapsed: {formatTime(elapsedSeconds)}
          {iteration > 0 && ` · Revision pass ${iteration} of 3`}
        </p>
      </div>

      <div className="card p-8">
        <div className="space-y-4">
          {STAGES.map((stage, index) => {
            const isActive = index === currentIndex;
            const isComplete = index < currentIndex;
            const isPending = index > currentIndex;

            // Don't show revising stage if we haven't hit it
            if (stage.key === 'revising' && currentIndex < 3 && iteration === 0) {
              return null;
            }

            return (
              <div key={stage.key} className="flex items-start gap-4">
                {/* Status indicator */}
                <div className="flex-shrink-0 mt-0.5">
                  {isComplete ? (
                    <div className="w-6 h-6 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center">
                      <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                  ) : isActive ? (
                    <div className="w-6 h-6 rounded-full bg-brass-500/20 border border-brass-500/40 flex items-center justify-center">
                      <div className="w-2 h-2 rounded-full bg-brass-400 progress-dot" />
                    </div>
                  ) : (
                    <div className="w-6 h-6 rounded-full bg-ink-800 border border-ink-700/50" />
                  )}
                </div>

                {/* Label */}
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-medium ${
                    isActive ? 'text-brass-300' : isComplete ? 'text-ink-300' : 'text-ink-600'
                  }`}>
                    {stage.label}
                  </p>
                  {isActive && (
                    <p className="text-ink-500 text-xs mt-0.5">{stage.detail}</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <p className="text-ink-600 text-xs text-center mt-6">
        This typically takes 1–3 minutes depending on RFP length and revision passes.
      </p>
    </div>
  );
}
