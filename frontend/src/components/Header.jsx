import React from 'react';

export default function Header() {
  return (
    <header className="w-full py-6 px-8">
      <div className="max-w-5xl mx-auto flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-brass-500/20 border border-brass-500/30 flex items-center justify-center">
            <span className="text-brass-400 font-display text-sm">P</span>
          </div>
          <h1 className="font-display text-xl text-ink-100 tracking-tight">
            PursuitDocs
          </h1>
        </div>
        <p className="text-ink-500 text-sm font-body hidden sm:block">
          AI-Powered Audit Proposal System
        </p>
      </div>
    </header>
  );
}
