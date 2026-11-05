import React from 'react'
import { History, Trash2, FolderGit2, Clock } from 'lucide-react'

export default function HistoryList({
  history = [],
  activeId,
  onSelect,
  onDelete,
}) {
  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-indigo-400" />
          <h2 className="text-sm font-semibold text-slate-200">
            Analysis History
          </h2>
        </div>
        <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400">
          {history.length}
        </span>
      </div>

      {history.length === 0 ? (
        <div className="text-center py-8 px-2 text-xs text-slate-500">
          No repositories analyzed yet. Paste a GitHub URL above to begin!
        </div>
      ) : (
        <div className="space-y-2 overflow-y-auto max-h-[540px] pr-1">
          {history.map((item) => {
            const isSelected = item.id === activeId
            return (
              <div
                key={item.id}
                onClick={() => onSelect(item.id)}
                className={`group relative p-3 rounded-lg border cursor-pointer transition ${
                  isSelected
                    ? 'bg-indigo-600/15 border-indigo-500/50 text-white'
                    : 'bg-slate-950/60 border-slate-800/80 hover:border-slate-700 text-slate-300'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <FolderGit2 className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                    <span className="text-xs font-semibold truncate">
                      {item.owner}/{item.repo}
                    </span>
                  </div>

                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onDelete(item.id)
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 transition"
                    title="Delete from history"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="flex items-center justify-between mt-2 text-[11px] text-slate-400">
                  <span>{item.file_count || 0} files analyzed</span>
                  {item.created_at && (
                    <span className="inline-flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {new Date(item.created_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

