import React, { useEffect, useState } from 'react'
import {
  Github,
  Sparkles,
  Cpu,
  BookOpen,
  FileCode2,
  GitFork,
  Compass,
  ExternalLink,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Loader2,
} from 'lucide-react'
import MermaidDiagram from './components/MermaidDiagram.jsx'
import FileSummariesList from './components/FileSummariesList.jsx'
import OnboardingGuide from './components/OnboardingGuide.jsx'
import HistoryList from './components/HistoryList.jsx'

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

const SAMPLE_REPOS = [
  { label: 'pallets/click', url: 'https://github.com/pallets/click' },
  { label: 'psf/requests', url: 'https://github.com/psf/requests' },
  { label: 'tiangolo/fastapi', url: 'https://github.com/tiangolo/fastapi' },
]

export default function App() {
  const [repoUrl, setRepoUrl] = useState('')
  const [maxFiles, setMaxFiles] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const [history, setHistory] = useState([])
  const [activeTab, setActiveTab] = useState('overview')
  const [health, setHealth] = useState(null)

  const fetchHealthAndHistory = async () => {
    try {
      const [hResp, histResp] = await Promise.all([
        fetch(`${API_BASE}/api/health`),
        fetch(`${API_BASE}/api/analyses`),
      ])
      if (hResp.ok) {
        setHealth(await hResp.json())
      }
      if (histResp.ok) {
        const list = await histResp.json()
        setHistory(list)
        if (!analysis && list.length > 0) {
          loadAnalysisById(list[0].id)
        }
      }
    } catch {
      // Backend may not be running yet
    }
  }

  useEffect(() => {
    fetchHealthAndHistory()
  }, [])

  const loadAnalysisById = async (id) => {
    setError(null)
    try {
      const resp = await fetch(`${API_BASE}/api/analyses/${id}`)
      if (!resp.ok) throw new Error('Failed to load saved analysis')
      const data = await resp.json()
      setAnalysis(data)
      setRepoUrl(data.repo_url || '')
    } catch (err) {
      setError(err.message)
    }
  }

  const handleAnalyze = async (e, forceReanalyze = false) => {
    if (e) e.preventDefault()
    if (!repoUrl.trim()) return

    setLoading(true)
    setError(null)
    try {
      const resp = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          repo_url: repoUrl.trim(),
          max_files: Number(maxFiles),
          force_reanalyze: forceReanalyze,
        }),
      })
      const data = await resp.json()
      if (!resp.ok) {
        throw new Error(data.detail || 'Repository analysis failed.')
      }
      setAnalysis(data)
      setActiveTab('overview')
      // Refresh history list
      const histResp = await fetch(`${API_BASE}/api/analyses`)
      if (histResp.ok) {
        setHistory(await histResp.json())
      }
    } catch (err) {
      setError(err.message || 'Could not reach Backend API.')
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteHistory = async (id) => {
    try {
      const resp = await fetch(`${API_BASE}/api/analyses/${id}`, {
        method: 'DELETE',
      })
      if (resp.ok) {
        const updated = history.filter((item) => item.id !== id)
        setHistory(updated)
        if (analysis?.id === id) {
          setAnalysis(null)
        }
      }
    } catch {
      // ignore
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Navbar */}
      <header className="border-b border-slate-800/80 bg-slate-900/70 backdrop-blur sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3.5 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-indigo-600/20 border border-indigo-500/30 text-indigo-400">
              <Github className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                <span>GitHub Repository Explainer</span>
                <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  Local Hybrid AI
                </span>
              </h1>
              <p className="text-xs text-slate-400">
                Map-Reduce Codebase Architecture, Mermaid Diagrams & Contributor Onboarding
              </p>
            </div>
          </div>

          {/* Local Ollama Status Pill */}
          <div className="flex items-center gap-2 text-xs">
            {health?.ollama_online ? (
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-950/60 border border-emerald-700/50 text-emerald-300">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                <span>
                  Ollama Online: <strong>{health.fast_model}</strong> + <strong>{health.smart_model}</strong>
                </span>
              </div>
            ) : (
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900 border border-slate-800 text-slate-400">
                <Cpu className="w-3.5 h-3.5 text-indigo-400" />
                <span>Local Hybrid LLM (gemma3:4b + gemma3:12b)</span>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6">
        {/* URL Input Card */}
        <section className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 sm:p-6 mb-6 shadow-xl">
          <form onSubmit={(e) => handleAnalyze(e, false)} className="space-y-4">
            <div className="flex flex-col md:flex-row gap-3">
              <div className="flex-1 relative">
                <Github className="w-5 h-5 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="url"
                  required
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  placeholder="Paste any public GitHub repository URL (e.g., https://github.com/pallets/click)"
                  className="w-full pl-11 pr-4 py-3 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
                />
              </div>

              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2">
                  <label htmlFor="maxFiles" className="text-xs text-slate-400 whitespace-nowrap">
                    Files Scope:
                  </label>
                  <select
                    id="maxFiles"
                    value={maxFiles}
                    onChange={(e) => setMaxFiles(Number(e.target.value))}
                    className="bg-transparent text-sm font-semibold text-indigo-300 focus:outline-none"
                  >
                    <option value={0} className="bg-slate-900 text-white">
                      All Files (Ranked)
                    </option>
                    {[10, 15, 25, 40].map((num) => (
                      <option key={num} value={num} className="bg-slate-900 text-white">
                        Top {num} Files
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-sm font-semibold text-white shadow-lg shadow-indigo-600/20 transition cursor-pointer whitespace-nowrap"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Analyzing Repo...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      <span>Explain Repository</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Quick Sample Repo Pills */}
            <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                <span>Try a sample repo:</span>
                {SAMPLE_REPOS.map((sample) => (
                  <button
                    key={sample.url}
                    type="button"
                    onClick={() => setRepoUrl(sample.url)}
                    className="px-2.5 py-1 rounded-md bg-slate-950 hover:bg-slate-800 text-slate-300 border border-slate-800 transition font-mono"
                  >
                    {sample.label}
                  </button>
                ))}
              </div>

              {analysis && (
                <button
                  type="button"
                  disabled={loading}
                  onClick={(e) => handleAnalyze(e, true)}
                  className="inline-flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 transition"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Force Re-run Local LLM</span>
                </button>
              )}
            </div>
          </form>

          {/* Progress Banner while running local Map-Reduce */}
          {loading && (
            <div className="mt-5 p-4 rounded-xl bg-indigo-950/40 border border-indigo-500/30 flex items-start gap-3">
              <Loader2 className="w-5 h-5 text-indigo-400 animate-spin flex-shrink-0 mt-0.5" />
              <div className="text-xs text-indigo-200 space-y-1">
                <p className="font-semibold text-sm text-white">
                  Running 4-Step Hybrid Map-Reduce Pipeline on Local Ollama...
                </p>
                <p>
                  1. Fetching GitHub tree & applying heuristic filter → 2. Selecting top {maxFiles} key files with{' '}
                  <code className="text-indigo-300">gemma3:4b</code> (GPU) → 3. Summarizing each fetched file grounded in real code → 4. Synthesizing Architecture, Mermaid diagram & Onboarding guide with{' '}
                  <code className="text-indigo-300">gemma3:12b</code> (GPU+RAM).
                </p>
              </div>
            </div>
          )}

          {/* Error Banner */}
          {error && (
            <div className="mt-4 p-4 rounded-xl bg-rose-950/50 border border-rose-500/40 flex items-start gap-3 text-rose-200 text-sm">
              <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-rose-300">Analysis Error</p>
                <p className="text-xs mt-0.5">{error}</p>
              </div>
            </div>
          )}
        </section>

        {/* Main Grid: Sidebar History + Analysis Dashboard */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Sidebar: History */}
          <aside className="lg:col-span-3">
            <HistoryList
              history={history}
              activeId={analysis?.id}
              onSelect={loadAnalysisById}
              onDelete={handleDeleteHistory}
            />
          </aside>

          {/* Right Area: Analysis Results */}
          <section className="lg:col-span-9">
            {!analysis ? (
              <div className="bg-slate-900/50 border border-slate-800/80 rounded-2xl p-12 text-center">
                <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center mx-auto mb-4">
                  <Sparkles className="w-6 h-6" />
                </div>
                <h2 className="text-lg font-semibold text-white mb-2">
                  Ready to Explain Any Public GitHub Repository
                </h2>
                <p className="text-sm text-slate-400 max-w-xl mx-auto">
                  Paste a repository URL above to run the local Map-Reduce pipeline. You will get a grounded architecture summary, an interactive Mermaid.js diagram, per-file explanations, and a contributor onboarding guide.
                </p>
              </div>
            ) : (
              <div className="space-y-5">
                {/* Repo Header Card */}
                <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2.5">
                      <h2 className="text-xl font-bold text-white">
                        {analysis.owner} / {analysis.repo}
                      </h2>
                      <span className="text-xs font-mono px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                        branch: {analysis.default_branch}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-1">
                      Analyzed with <span className="text-indigo-300 font-medium">{analysis.model}</span> •{' '}
                      {(analysis.file_summaries || []).length} key files summarized
                    </p>
                  </div>

                  <a
                    href={analysis.repo_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 transition"
                  >
                    <span>Open on GitHub</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>

                {/* Navigation Tabs */}
                <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-3">
                  {[
                    { id: 'overview', label: 'Architecture Overview', icon: BookOpen },
                    { id: 'diagram', label: 'Mermaid Diagram', icon: GitFork },
                    {
                      id: 'files',
                      label: `File Explanations (${(analysis.file_summaries || []).length})`,
                      icon: FileCode2,
                    },
                    { id: 'onboarding', label: 'Start Here Guide', icon: Compass },
                  ].map((tab) => {
                    const Icon = tab.icon
                    const active = activeTab === tab.id
                    return (
                      <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-medium transition cursor-pointer ${
                          active
                            ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                            : 'bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-800'
                        }`}
                      >
                        <Icon className="w-4 h-4" />
                        <span>{tab.label}</span>
                      </button>
                    )
                  })}
                </div>

                {/* Tab Content */}
                {activeTab === 'overview' && (
                  <div className="space-y-6">
                    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6 shadow-md">
                      <h3 className="text-base font-bold text-white mb-3">
                        Plain-English Architecture Summary
                      </h3>
                      <div className="text-sm text-slate-200 leading-relaxed whitespace-pre-line space-y-3">
                        {analysis.architecture_summary}
                      </div>

                      {analysis.selected_files_reasoning && (
                        <div className="mt-6 pt-4 border-t border-slate-800/80">
                          <h4 className="text-xs font-semibold uppercase tracking-wider text-indigo-400 mb-1.5">
                            Why These Key Files Were Selected (Step 1 Reasoning)
                          </h4>
                          <p className="text-xs text-slate-400 leading-relaxed">
                            {analysis.selected_files_reasoning}
                          </p>
                        </div>
                      )}
                    </div>

                    {/* Preview Mermaid Diagram right below Overview too */}
                    <MermaidDiagram
                      chart={analysis.mermaid_diagram}
                      files={analysis.file_summaries || []}
                      repoName={`${analysis.owner}/${analysis.repo}`}
                    />
                  </div>
                )}

                {activeTab === 'diagram' && (
                  <MermaidDiagram
                    chart={analysis.mermaid_diagram}
                    files={analysis.file_summaries || []}
                    repoName={`${analysis.owner}/${analysis.repo}`}
                  />
                )}

                {activeTab === 'files' && (
                  <FileSummariesList
                    files={analysis.file_summaries || []}
                    owner={analysis.owner}
                    repo={analysis.repo}
                    branch={analysis.default_branch}
                  />
                )}

                {activeTab === 'onboarding' && (
                  <OnboardingGuide guide={analysis.onboarding_guide || {}} />
                )}
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  )
}

