import React, { useState } from 'react'
import { FileCode, ExternalLink, Search, Layers, Link2 } from 'lucide-react'

export default function FileSummariesList({ files = [], owner, repo, branch = 'main' }) {
  const [searchQuery, setSearchQuery] = useState('')

  const filteredFiles = files.filter((file) => {
    const q = searchQuery.toLowerCase()
    return (
      file.path?.toLowerCase().includes(q) ||
      file.purpose?.toLowerCase().includes(q) ||
      (file.key_components || []).some((c) => c.toLowerCase().includes(q))
    )
  })

  return (
    <div className="space-y-4">
      {/* Search bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-900/90 border border-slate-800 rounded-xl p-4">
        <div>
          <h3 className="text-base font-semibold text-slate-100">
            All Repository Files — Ranked by Importance ({files.length} Files Analyzed)
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Ordered from core entrypoints & subdirectory source modules down to notebooks, configs, and docs.
          </p>
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter files or components..."
            className="w-full pl-9 pr-3 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>
      </div>

      {/* File Cards */}
      <div className="grid grid-cols-1 gap-4">
        {filteredFiles.map((file, idx) => {
          const githubFileUrl = `https://github.com/${owner}/${repo}/blob/${branch}/${file.path}`
          return (
            <div
              key={file.path || idx}
              className="bg-slate-900/80 border border-slate-800 hover:border-slate-700 rounded-xl p-5 transition shadow-sm"
            >
              <div className="flex flex-wrap items-start justify-between gap-2 mb-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                    <FileCode className="w-4 h-4" />
                  </div>
                  <span className="font-mono text-sm font-semibold text-indigo-300 break-all">
                    {file.path}
                  </span>
                </div>

                <a
                  href={githubFileUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs font-medium text-slate-400 hover:text-indigo-400 bg-slate-800/80 px-2.5 py-1 rounded-md transition"
                >
                  <span>View on GitHub</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>

              <p className="text-sm text-slate-200 leading-relaxed mb-4">
                {file.purpose}
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-3 border-t border-slate-800/80">
                {/* Key Components */}
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                    <Layers className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Key Components / Exports</span>
                  </div>
                  {file.key_components && file.key_components.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {file.key_components.map((comp, i) => (
                        <span
                          key={i}
                          className="px-2.5 py-1 rounded-md text-xs font-mono bg-slate-950 text-slate-300 border border-slate-800"
                        >
                          {comp}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-xs text-slate-500 italic">None specified</span>
                  )}
                </div>

                {/* Connections & Dependencies */}
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                    <Link2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Dependencies & Connections</span>
                  </div>
                  {file.dependencies_and_connections && file.dependencies_and_connections.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {file.dependencies_and_connections.map((dep, i) => (
                        <span
                          key={i}
                          className="px-2.5 py-1 rounded-md text-xs font-mono bg-emerald-950/30 text-emerald-300 border border-emerald-800/40"
                        >
                          {dep}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-xs text-slate-500 italic">None specified</span>
                  )}
                </div>
              </div>
            </div>
          )
        })}

        {filteredFiles.length === 0 && (
          <div className="text-center py-10 bg-slate-900/50 border border-slate-800 rounded-xl text-slate-400 text-sm">
            No analyzed files match "{searchQuery}".
          </div>
        )}
      </div>
    </div>
  )
}

