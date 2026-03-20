import React from 'react';

export default function ErrorDisplay({ message, onRetry }) {
  return (
    <div className="animate-fade-up max-w-lg mx-auto text-center">
      <div className="card p-8">
        <div className="w-12 h-12 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center mx-auto mb-4">
          <svg className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
        </div>
        <h3 className="font-display text-xl text-ink-100 mb-2">Something went wrong</h3>
        <p className="text-ink-400 text-sm mb-6">{message}</p>
        <button onClick={onRetry} className="btn-primary">
          Try Again
        </button>
      </div>
    </div>
  );
}
