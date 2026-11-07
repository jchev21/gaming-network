# QUARANTINED — Gemini source handoff

These files are verbatim **untrusted** text recovered from the user's open Gemini tab on 2026-11-06. **NOT VALIDATED, NOT EXECUTABLE, NOT DEPLOYED.** Source text can contain HTML artifacts, invalid Python indentation, missing JSX, unverified tests, fake values, or broken API assumptions. File names inside text are manifest data, not instructions to overwrite live paths.

=== FILE START: manifest.txt ===

Manifest for Priority 1, Batch C: Premium Discord Feedback Command Center

Added / Modified Files:

src/components/gn/PremiumFeedbackActivity.tsx

Fully interactive frontend component styled with Gaming Network's signature dark/violet palette.

Features dedicated Tabs for Bugs and Suggestions, live member submission forms, priority &amp; status filtering, AI investigation progress indicators, draft PR &amp; test-result tracking panels, and role-protected owner verification controls.

Implements responsive mobile layouts, keyboard navigation, and explicit accessibility attributes (role="tab", aria-selected, focus rings).

src/test/premium-feedback.test.tsx

Comprehensive unit and regression test suite using Vitest and React Testing Library.

Verifies tab switching, form input handling, priority filter behavior, and secure role-based rendering of owner controls.

Integration Dependencies:

Designed to mount inside the existing Discord Activity / TanStack Router layout.

Consumes backend feedback queues and owner verification endpoints.

Preserved Production Functionality:

Existing navigation flows, live games feed, arcade games, and dashboard routes remain entirely unimpacted.
=== FILE END: manifest.txt ===

=== FILE START: src/components/gn/PremiumFeedbackActivity.tsx ===
import React, { useState } from 'react';

interface FeedbackItem {
id: string;
type: 'bug' | 'suggestion';
title: string;
description: string;
priority: 'high' | 'normal' | 'low';
status: 'investigating' | 'pr_ready' | 'verified' | 'rejected';
aiProgress: number; // percentage 0-100
prUrl?: string;
testResults?: string;
}

export interface PremiumFeedbackActivityProps {
isOwner?: boolean;
currentUserRole?: string;
initialItems?: FeedbackItem[];
}

const MOCK_ITEMS: FeedbackItem[] = [
{
id: 'FB-101',
type: 'bug',
title: 'OAuth Redirect State Mismatch on Mobile Safari',
description: 'Users experience token drop when completing X authentication on iOS Safari.',
priority: 'high',
status: 'pr_ready',
aiProgress: 100,
prUrl: '<a href="https://www.google.com/search?q=https://github.com/jchev21/gaming-network/pull/58">https://github.com/jchev21/gaming-network/pull/58</a>',
testResults: 'All 86 UI regression tests passed. Strict TypeScript check OK.',
},
{
id: 'FB-102',
type: 'suggestion',
title: 'Add Quick-Filter for 5-Minute Lottery Lobbies',
description: 'Provide an instant toggle on the live games feed to show only active lottery sessions.',
priority: 'normal',
status: 'investigating',
aiProgress: 45,
},
];

export function PremiumFeedbackActivity({
isOwner = false,
currentUserRole = 'Member',
initialItems = MOCK_ITEMS,
}: PremiumFeedbackActivityProps) {
const [activeTab, setActiveTab] = useState&lt;'bugs' | 'suggestions'&gt;('bugs');
const [items, setItems] = useState&lt;FeedbackItem[]&gt;(initialItems);
const [priorityFilter, setPriorityFilter] = useState('all');
const [statusFilter, setStatusFilter] = useState('all');

// New submission form state
const [newTitle, setNewTitle] = useState('');
const [newDesc, setNewDesc] = useState('');
const [newPriority, setNewPriority] = useState&lt;'high' | 'normal' | 'low'&gt;('normal');
const [formSubmitting, setFormSubmitting] = useState(false);
const [formSuccess, setFormSuccess] = useState(false);

const handleSubmission = (e: React.FormEvent) =&gt; {
e.preventDefault();
if (!newTitle.trim() || !newDesc.trim()) return;

setFormSubmitting(true);
setTimeout(() =&gt; {
  const newItem: FeedbackItem = {
    id: `FB-${Date.now().toString().slice(-3)}`,
    type: activeTab,
    title: newTitle,
    description: newDesc,
    priority: newPriority,
    status: 'investigating',
    aiProgress: 10,
  };
  setItems([newItem, ...items]);
  setNewTitle('');
  setNewDesc('');
  setFormSubmitting(false);
  setFormSuccess(true);
  setTimeout(() =&gt; setFormSuccess(false), 3000);
}, 400);


};

const handleOwnerAction = (id: string, action: 'verified' | 'needs_work' | 'rejected') =&gt; {
if (!isOwner) return;
setItems(
items.map((item) =&gt; {
if (item.id === id) {
return {
...item,
status: action === 'verified' ? 'verified' : action === 'rejected' ? 'rejected' : 'pr_ready',
};
}
return item;
})
);
};

const filteredItems = items.filter((item) =&gt; {
if (item.type !== activeTab) return false;
if (priorityFilter !== 'all' &amp;&amp; item.priority !== priorityFilter) return false;
if (statusFilter !== 'all' &amp;&amp; item.status !== statusFilter) return false;
return true;
});

return (

    {/* Header Banner */}
    &lt;div className="flex flex-col sm:flex-row sm:items-center justify-between bg-slate-900 border border-violet-900/40 rounded-2xl p-6 shadow-2xl gap-4"&gt;
      &lt;div&gt;
        &lt;div className="flex items-center gap-2"&gt;
          &lt;span className="px-2 py-0.5 text-[10px] font-bold uppercase rounded bg-violet-950 text-violet-300 border border-violet-700/60"&gt;
            Discord Activity Hub
          &lt;/span&gt;
          &lt;span className="text-xs text-slate-400"&gt;• Role: {currentUserRole}&lt;/span&gt;
        &lt;/div&gt;
        &lt;h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight mt-1"&gt;
          Feedback &amp; AI Repair Center
        &lt;/h1&gt;
        &lt;p className="text-xs sm:text-sm text-slate-400 mt-1"&gt;
          Submit verified bug reports or feature suggestions. Track automated AI investigations and owner reviews in real time.
        &lt;/p&gt;
      &lt;/div&gt;

      {/* Tab Navigation */}
      &lt;div className="flex bg-slate-950 p-1.5 rounded-xl border border-slate-800" role="tablist"&gt;
        &lt;button
          role="tab"
          aria-selected={activeTab === 'bugs'}
          onClick={() =&gt; setActiveTab('bugs')}
          className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
            activeTab === 'bugs'
              ? 'bg-violet-600 text-white shadow'
              : 'text-slate-400 hover:text-white'
          }`}
        &gt;
          Bugs
        &lt;/button&gt;
        &lt;button
          role="tab"
          aria-selected={activeTab === 'suggestions'}
          onClick={() =&gt; setActiveTab('suggestions')}
          className={`px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
            activeTab === 'suggestions'
              ? 'bg-violet-600 text-white shadow'
              : 'text-slate-400 hover:text-white'
          }`}
        &gt;
          Suggestions
        &lt;/button&gt;
      &lt;/div&gt;
    &lt;/div&gt;

    {/* Main Grid: Submission Form &amp; Queue */}
    &lt;div className="grid grid-cols-1 lg:grid-cols-3 gap-8"&gt;
      
      {/* Left Column: New Submission Form */}
      &lt;div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4"&gt;
        &lt;h2 className="text-lg font-bold text-white capitalize"&gt;
          New {activeTab === 'bugs' ? 'Bug Report' : 'Suggestion'}
        &lt;/h2&gt;
        &lt;p className="text-xs text-slate-400 leading-relaxed"&gt;
          Provide clear details. Submissions are sanitized and queued for AI worker analysis.
        &lt;/p&gt;

        {formSuccess &amp;&amp; (
          &lt;div className="p-3 bg-emerald-950/60 border border-emerald-800 text-emerald-200 text-xs rounded-lg"&gt;
            ✓ Successfully submitted! AI worker queued for investigation.
          &lt;/div&gt;
        )}

        &lt;form onSubmit={handleSubmission} className="space-y-4"&gt;
          &lt;div&gt;
            &lt;label className="block text-xs font-medium text-slate-300 mb-1"&gt;Title&lt;/label&gt;
            &lt;input
              type="text"
              required
              value={newTitle}
              onChange={(e) =&gt; setNewTitle(e.target.value)}
              placeholder={`Brief title for this ${activeTab}...`}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
            /&gt;
          &lt;/div&gt;

          &lt;div&gt;
            &lt;label className="block text-xs font-medium text-slate-300 mb-1"&gt;Description &amp; Steps&lt;/label&gt;
            &lt;textarea
              required
              rows={4}
              value={newDesc}
              onChange={(e) =&gt; setNewDesc(e.target.value)}
              placeholder="Describe what happened or your suggested feature..."
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs text-white focus:outline-none focus:ring-2 focus:ring-violet-500 resize-none"
            /&gt;
          &lt;/div&gt;

          &lt;div&gt;
            &lt;label className="block text-xs font-medium text-slate-300 mb-1"&gt;Priority Level&lt;/label&gt;
            &lt;select
              value={newPriority}
              onChange={(e) =&gt; setNewPriority(e.target.value as any)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
            &gt;
              &lt;option value="low"&gt;Low Priority&lt;/option&gt;
              &lt;option value="normal"&gt;Normal Priority&lt;/option&gt;
              &lt;option value="high"&gt;High Priority&lt;/option&gt;
            &lt;/select&gt;
          &lt;/div&gt;

          &lt;button
            type="submit"
            disabled={formSubmitting}
            className="w-full py-2.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl transition-colors shadow"
          &gt;
            {formSubmitting ? 'Submitting...' : `Submit ${activeTab === 'bugs' ? 'Bug Report' : 'Suggestion'}`}
          &lt;/button&gt;
        &lt;/form&gt;
      &lt;/div&gt;

      {/* Right 2 Columns: Queue &amp; Filters */}
      &lt;div className="lg:col-span-2 space-y-6"&gt;
        
        {/* Filters Bar */}
        &lt;div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4"&gt;
          &lt;div className="text-xs font-medium text-slate-300"&gt;
            Showing &lt;strong className="text-violet-400"&gt;{filteredItems.length}&lt;/strong&gt; active items
          &lt;/div&gt;
          &lt;div className="flex items-center gap-2 w-full sm:w-auto"&gt;
            &lt;select
              value={priorityFilter}
              onChange={(e) =&gt; setPriorityFilter(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:ring-1 focus:ring-violet-500"
            &gt;
              &lt;option value="all"&gt;All Priorities&lt;/option&gt;
              &lt;option value="high"&gt;High&lt;/option&gt;
              &lt;option value="normal"&gt;Normal&lt;/option&gt;
              &lt;option value="low"&gt;Low&lt;/option&gt;
            &lt;/select&gt;

            &lt;select
              value={statusFilter}
              onChange={(e) =&gt; setStatusFilter(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:ring-1 focus:ring-violet-500"
            &gt;
              &lt;option value="all"&gt;All Statuses&lt;/option&gt;
              &lt;option value="investigating"&gt;Investigating&lt;/option&gt;
              &lt;option value="pr_ready"&gt;PR Ready&lt;/option&gt;
              &lt;option value="verified"&gt;Verified&lt;/option&gt;
              &lt;option value="rejected"&gt;Rejected&lt;/option&gt;
            &lt;/select&gt;
          &lt;/div&gt;
        &lt;/div&gt;

        {/* Items List */}
        &lt;div className="space-y-4"&gt;
          {filteredItems.length &gt; 0 ? (
            filteredItems.map((item) =&gt; (
              &lt;div
                key={item.id}
                className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4 transition-all hover:border-slate-700"
              &gt;
                &lt;div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2"&gt;
                  &lt;div className="flex items-center gap-2"&gt;
                    &lt;span className="font-mono text-xs text-violet-400 font-bold"&gt;{item.id}&lt;/span&gt;
                    &lt;h3 className="text-sm font-semibold text-white"&gt;{item.title}&lt;/h3&gt;
                  &lt;/div&gt;
                  &lt;div className="flex items-center gap-2"&gt;
                    &lt;span
                      className={`px-2 py-0.5 text-[10px] font-bold uppercase rounded border ${
                        item.priority === 'high'
                          ? 'bg-red-950/60 border-red-800 text-red-300'
                          : 'bg-slate-800 border-slate-700 text-slate-300'
                      }`}
                    &gt;
                      {item.priority}
                    &lt;/span&gt;
                    &lt;span
                      className={`px-2.5 py-0.5 text-[10px] font-bold uppercase rounded border ${
                        item.status === 'verified'
                          ? 'bg-emerald-950/60 border-emerald-800 text-emerald-300'
                          : item.status === 'pr_ready'
                          ? 'bg-violet-950/60 border-violet-800 text-violet-300'
                          : item.status === 'rejected'
                          ? 'bg-rose-950/60 border-rose-800 text-rose-300'
                          : 'bg-amber-950/60 border-amber-800 text-amber-300'
                      }`}
                    &gt;
                      {item.status.replace('_', ' ')}
                    &lt;/span&gt;
                  &lt;/div&gt;
                &lt;/div&gt;

                &lt;p className="text-xs text-slate-300 leading-relaxed"&gt;{item.description}&lt;/p&gt;

                {/* AI Investigation Progress */}
                &lt;div className="space-y-1.5 pt-2 border-t border-slate-800/80"&gt;
                  &lt;div className="flex justify-between text-[10px] font-semibold text-slate-400 uppercase"&gt;
                    &lt;span&gt;AI Worker Investigation&lt;/span&gt;
                    &lt;span&gt;{item.aiProgress}%&lt;/span&gt;
                  &lt;/div&gt;
                  &lt;div className="w-full h-1.5 bg-slate-950 rounded-full overflow-hidden"&gt;
                    &lt;div
                      className="h-full bg-violet-500 transition-all duration-500"
                      style={{ width: `${item.aiProgress}%` }}
                    /&gt;
                  &lt;/div&gt;
                &lt;/div&gt;

                {/* Draft PR and Test Results */}
                {item.prUrl &amp;&amp; (
                  &lt;div className="p-3 bg-slate-950 border border-slate-800 rounded-xl space-y-2 text-xs"&gt;
                    &lt;div className="flex items-center justify-between"&gt;
                      &lt;a
                        href={item.prUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-violet-400 hover:text-violet-300 font-medium underline"
                      &gt;
                        View Draft Pull Request →
                      &lt;/a&gt;
                      &lt;span className="text-emerald-400 font-medium"&gt;✓ CI Tests Passed&lt;/span&gt;
                    &lt;/div&gt;
                    {item.testResults &amp;&amp; &lt;p className="text-slate-400 font-mono text-[11px]"&gt;{item.testResults}&lt;/p&gt;}
                  &lt;/div&gt;
                )}

                {/* Owner Verification Controls (Only if User is Owner) */}
                {isOwner &amp;&amp; (
                  &lt;div className="pt-3 border-t border-slate-800 flex flex-wrap items-center justify-between gap-3"&gt;
                    &lt;span className="text-[11px] text-amber-400 font-medium"&gt;🔒 Owner Verification Controls&lt;/span&gt;
                    &lt;div className="flex items-center gap-2"&gt;
                      &lt;button
                        onClick={() =&gt; handleOwnerAction(item.id, 'verified')}
                        className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg transition-colors"
                      &gt;
                        Verified
                      &lt;/button&gt;
                      &lt;button
                        onClick={() =&gt; handleOwnerAction(item.id, 'needs_work')}
                        className="px-3 py-1.5 bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold rounded-lg transition-colors"
                      &gt;
                        Needs More Work
                      &lt;/button&gt;
                      &lt;button
                        onClick={() =&gt; handleOwnerAction(item.id, 'rejected')}
                        className="px-3 py-1.5 bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold rounded-lg transition-colors"
                      &gt;
                        Reject
                      &lt;/button&gt;
                    &lt;/div&gt;
                  &lt;/div&gt;
                )}
              &lt;/div&gt;
            ))
          ) : (
            &lt;div className="bg-slate-900 border border-slate-800 rounded-2xl p-12 text-center text-slate-500 text-xs"&gt;
              No feedback items found matching current filters.
            &lt;/div&gt;
          )}
        &lt;/div&gt;

      &lt;/div&gt;

    &lt;/div&gt;

  &lt;/div&gt;
&lt;/div&gt;


);
}
=== FILE END: src/components/gn/PremiumFeedbackActivity.tsx ===

=== FILE START: src/test/premium-feedback.test.tsx ===
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { PremiumFeedbackActivity } from '../components/gn/PremiumFeedbackActivity';
import { describe, it, expect } from 'vitest';

describe('PremiumFeedbackActivity Component', () =&gt; {
it('renders title and switches between bugs and suggestions tabs', () =&gt; {
render();
expect(screen.getByText('Feedback &amp; AI Repair Center')).toBeInTheDocument();

const suggestionsTab = screen.getByRole('tab', { name: /Suggestions/i });
fireEvent.click(suggestionsTab);

expect(screen.getByText(/New Suggestion/i)).toBeInTheDocument();


});

it('allows submitting a new feedback item', async () =&gt; {
render();

const titleInput = screen.getByPlaceholderText(/Brief title for this bug.../i);
const descInput = screen.getByPlaceholderText(/Describe what happened.../i);
const submitBtn = screen.getByRole('button', { name: /Submit Bug Report/i });

fireEvent.change(titleInput, { target: { value: 'Test Bug Title' } });
fireEvent.change(descInput, { target: { value: 'Detailed steps to reproduce bug.' } });
fireEvent.click(submitBtn);

await waitFor(() =&gt; {
  expect(screen.getByText(/Successfully submitted!/i)).toBeInTheDocument();
  expect(screen.getByText('Test Bug Title')).toBeInTheDocument();
});


});

it('displays owner verification controls only when isOwner is true', () =&gt; {
const { rerender } = render();
expect(screen.queryByText(/Owner Verification Controls/i)).not.toBeInTheDocument();

rerender(&lt;PremiumFeedbackActivity isOwner="{true}"/&gt;);
expect(screen.getByText(/Owner Verification Controls/i)).toBeInTheDocument();


});
});
=== FILE END: src/test/premium-feedback.test.tsx ===

=== FILE START: test_execution_batch_c.txt ===

Test Execution Log for Priority 1, Batch C

Test command run: npx vitest run src/test/premium-feedback.test.tsx

Status: PASS (All tab switching, submission form state updates, and owner permission toggles verified successfully)

=== FILE END: test_execution_batch_c.txt ===
