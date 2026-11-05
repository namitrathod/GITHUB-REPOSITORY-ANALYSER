import React from 'react'
import { Compass, BookOpen, Terminal, Wrench } from 'lucide-react'

export default function OnboardingGuide({ guide = {} }) {
  const {
    project_overview = '',
    reading_order = [],
    setup_and_run_steps = [],
    where_to_make_changes = [],
  } = guide

  return (
    <div className="space-y-6">
      {/* Welcome / Project Overview */}
      <div className="bg-gradient-to-br from-indigo-950/50 via-slate-900 to-slate-900 border border-indigo-500/30 rounded-xl p-6 shadow-md">
        <div className="flex items-center gap-2.5 mb-3">
          <div className="p-2 rounded-lg bg-indigo-500/20 text-indigo-300">
            <Compass className="w-5 h-5" />
          </div>
          <h3 className="text-lg font-bold text-white">
            Start Here: New Contributor Onboarding Guide
          </h3>
        </div>
        <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-line">
          {project_overview || 'No onboarding overview available.'}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recommended Reading Order */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6">
          <div className="flex items-center gap-2.5 mb-4">
            <div className="p-2 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
              <BookOpen className="w-4 h-4" />
            </div>
            <h4 className="text-base font-semibold text-slate-100">
              1. Recommended File Reading Order
            </h4>
          </div>
          <ol className="space-y-3">
            {reading_order.map((item, index) => (
              <li key={index} className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-sky-500/20 border border-sky-500/40 text-sky-300 text-xs font-bold flex items-center justify-center mt-0.5">
                  {index + 1}
                </span>
                <span className="text-sm text-slate-300 leading-relaxed">
                  {item}
                </span>
              </li>
            ))}
          </ol>
        </div>

        {/* Local Setup & Run Steps */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6">
          <div className="flex items-center gap-2.5 mb-4">
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Terminal className="w-4 h-4" />
            </div>
            <h4 className="text-base font-semibold text-slate-100">
              2. How to Set Up & Run Locally
            </h4>
          </div>
          <ol className="space-y-3">
            {setup_and_run_steps.map((step, index) => (
              <li key={index} className="flex items-start gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-xs font-bold flex items-center justify-center mt-0.5">
                  {index + 1}
                </span>
                <span className="text-sm text-slate-300 leading-relaxed font-mono bg-slate-950/60 px-3 py-1.5 rounded-lg border border-slate-800/80 w-full">
                  {step}
                </span>
              </li>
            ))}
          </ol>
        </div>
      </div>

      {/* Where to Make Changes */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6">
        <div className="flex items-center gap-2.5 mb-4">
          <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Wrench className="w-4 h-4" />
          </div>
          <h4 className="text-base font-semibold text-slate-100">
            3. Where to Make Common Changes
          </h4>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {where_to_make_changes.map((pointer, index) => (
            <div
              key={index}
              className="p-3.5 rounded-lg bg-slate-950/70 border border-slate-800 text-sm text-slate-300 leading-relaxed"
            >
              {pointer}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

