import React, { useState } from 'react';
import { exportDocx } from '../services/api';

export default function ResultsDisplay({ result, onRegenerate, canRegenerate }) {
  const [activeTab, setActiveTab] = useState('letter');
  const [changeLogExpanded, setChangeLogExpanded] = useState(false);
  const [exportingDocx, setExportingDocx] = useState(false);

  const { status, iterations, final_letter, change_log, parsed_rfp } = result;
  const isReady = status === 'ready_for_review';

  const handleCopyLetter = async () => {
    try {
      await navigator.clipboard.writeText(final_letter);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement('textarea');
      textarea.value = final_letter;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
    }
  };

  const handleDownloadTxt = () => {
    const blob = new Blob([final_letter], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'proposal_letter.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadJson = () => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'pursuitdocs_output.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="animate-fade-up max-w-3xl mx-auto">
      {/* Status header */}
      <div className="text-center mb-8">
        <h2 className="font-display text-2xl sm:text-3xl text-ink-50 mb-3">
          {isReady ? 'Your Proposal Letter is Ready' : 'Review Required'}
        </h2>
        <div className="flex items-center justify-center gap-3">
          <span className={isReady ? 'status-ready' : 'status-needs-revision'}>
            <span className={`w-1.5 h-1.5 rounded-full ${isReady ? 'bg-emerald-400' : 'bg-amber-400'}`} />
            {isReady ? 'Ready for Review' : 'Needs Revision'}
          </span>
          <span className="text-ink-500 text-sm">
            {iterations} revision {iterations === 1 ? 'pass' : 'passes'}
            {change_log.length > 0 && ` · ${change_log.length} issue${change_log.length === 1 ? '' : 's'} addressed`}
          </span>
        </div>
      </div>

      {/* Tab navigation */}
      <div className="flex gap-1 mb-4 border-b border-ink-800">
        <button
          onClick={() => setActiveTab('letter')}
          className={`px-5 py-2.5 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'letter'
              ? 'border-brass-500 text-brass-300'
              : 'border-transparent text-ink-500 hover:text-ink-300'
          }`}
        >
          Proposal Letter
        </button>
        <button
          onClick={() => setActiveTab('changelog')}
          className={`px-5 py-2.5 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'changelog'
              ? 'border-brass-500 text-brass-300'
              : 'border-transparent text-ink-500 hover:text-ink-300'
          }`}
        >
          Change Log
          {change_log.length > 0 && (
            <span className="ml-1.5 px-1.5 py-0.5 rounded text-xs bg-ink-800 text-ink-400">
              {change_log.length}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveTab('parsed')}
          className={`px-5 py-2.5 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'parsed'
              ? 'border-brass-500 text-brass-300'
              : 'border-transparent text-ink-500 hover:text-ink-300'
          }`}
        >
          Parsed RFP
        </button>
      </div>

      {/* Tab content */}
      <div className="card p-6 sm:p-8">
        {activeTab === 'letter' && (
          <div>
            <pre className="whitespace-pre-wrap font-body text-ink-200 text-sm leading-relaxed">
              {final_letter}
            </pre>
          </div>
        )}

        {activeTab === 'changelog' && (
          <div>
            {change_log.length === 0 ? (
              <p className="text-ink-500 text-sm">
                No independence issues were found. The letter passed review on the first attempt.
              </p>
            ) : (
              <div className="space-y-6">
                {change_log.map((entry, index) => (
                  <div key={index} className="border-l-2 border-ink-700 pl-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-xs font-mono text-ink-500 bg-ink-800 px-2 py-0.5 rounded">
                        Pass {entry.iteration + 1}
                      </span>
                    </div>
                    <div className="space-y-2 text-sm">
                      <div>
                        <span className="text-ink-500 font-medium">Flagged: </span>
                        <span className="text-red-400/80 italic">"{entry.flagged_text}"</span>
                      </div>
                      <div>
                        <span className="text-ink-500 font-medium">Reason: </span>
                        <span className="text-ink-300">{entry.reason}</span>
                      </div>
                      <div>
                        <span className="text-ink-500 font-medium">Citation: </span>
                        <span className="text-ink-400 font-mono text-xs">{entry.pcaob_citation}</span>
                      </div>
                      <div>
                        <span className="text-ink-500 font-medium">Suggested: </span>
                        <span className="text-emerald-400/80 italic">"{entry.suggested_alternative}"</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'parsed' && (
          <div>
            <pre className="whitespace-pre-wrap font-mono text-xs text-ink-400 leading-relaxed">
              {JSON.stringify(parsed_rfp, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-center justify-between gap-3 mt-6">
        <div className="flex gap-2">
          <button onClick={handleCopyLetter} className="btn-secondary text-sm">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
            </svg>
            Copy Letter
          </button>
          <button onClick={handleDownloadTxt} className="btn-secondary text-sm">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
            Download .txt
          </button>
          <button
            onClick={async () => {
              setExportingDocx(true);
              try {
                const blob = await exportDocx(final_letter);
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'proposal_letter.docx';
                a.click();
                URL.revokeObjectURL(url);
              } catch (err) {
                console.error('Export failed:', err);
              } finally {
                setExportingDocx(false);
              }
            }}
            className="btn-secondary text-sm"
            disabled={exportingDocx}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
            {exportingDocx ? 'Exporting...' : 'Download .docx'}
          </button>
          <button onClick={handleDownloadJson} className="btn-secondary text-sm">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
            Download JSON
          </button>
        </div>

        <div>
          {canRegenerate ? (
            <button onClick={onRegenerate} className="btn-primary text-sm">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
              </svg>
              Regenerate
            </button>
          ) : (
            <p className="text-ink-600 text-xs">
              Need changes? Download the letter and edit directly.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
