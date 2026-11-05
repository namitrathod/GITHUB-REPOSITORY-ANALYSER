import React, { useEffect, useRef, useState } from 'react'
import mermaid from 'mermaid'
import {
  Code,
  Copy,
  Check,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Maximize2,
  Minimize2,
  ArrowLeftRight,
} from 'lucide-react'

mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  securityLevel: 'loose',
  fontFamily: 'ui-sans-serif, system-ui, sans-serif',
  flowchart: {
    useMaxWidth: false,
    htmlLabels: true,
    nodeSpacing: 35,
    rankSpacing: 55,
    curve: 'basis',
  },
  themeVariables: {
    fontSize: '15px',
    primaryColor: '#1e1b4b',
    primaryTextColor: '#f8fafc',
    primaryBorderColor: '#6366f1',
    lineColor: '#818cf8',
    secondaryColor: '#0f172a',
    tertiaryColor: '#1e293b',
  },
})

/**
 * Build a clean, grouped, readable Mermaid flowchart from the analyzed file_summaries,
 * organizing files into folder subgraphs (e.g. root, src/, scripts/, notebooks/) so it never
 * stretches into an unreadable 4000px-wide single row.
 */
function buildGroupedMermaidFromFiles(files = [], repoName = 'Repository', direction = 'LR') {
  if (!files || files.length === 0) {
    return `flowchart ${direction}\n  Root["${repoName}"]`
  }

  // Cap diagram nodes to top 16 most important files so the chart stays crisp and readable
  const topFiles = files.slice(0, 16)
  const lines = [`flowchart ${direction}`]
  const safeId = (idx) => `F${idx}`
  const cleanText = (str) =>
    String(str || '')
      .replace(/["[\](){}]/g, '')
      .replace(/<|>/g, '')
      .trim()

  // Group files by top-level directory
  const groups = new Map()
  topFiles.forEach((f, i) => {
    const parts = String(f.path || `File_${i}`).split('/')
    const folder = parts.length > 1 ? parts[0] : 'Root'
    if (!groups.has(folder)) groups.set(folder, [])
    groups.get(folder).push({ file: f, idx: i, shortName: parts.slice(1).join('/') || parts[0] })
  })

  // Emit subgraphs per folder
  let sgIdx = 0
  groups.forEach((items, folderName) => {
    sgIdx++
    const sgId = `SG_${sgIdx}`
    const sgTitle = folderName === 'Root' ? 'Root Entrypoints & Config' : `${folderName}/`
    lines.push(`  subgraph ${sgId}["${cleanText(sgTitle)}"]`)
    items.forEach(({ file, idx, shortName }) => {
      const comps = (file.key_components || [])
        .slice(0, 2)
        .map(cleanText)
        .filter(Boolean)
        .join(', ')
      const label = comps
        ? `<b>${cleanText(shortName)}</b><br/><small>${comps}</small>`
        : `<b>${cleanText(shortName)}</b>`
      lines.push(`    ${safeId(idx)}["${label}"]`)
    })
    lines.push('  end')
  })

  // Connect files based on dependencies_and_connections
  const addedEdges = new Set()
  topFiles.forEach((f, i) => {
    const deps = f.dependencies_and_connections || []
    deps.forEach((dep) => {
      const depClean = cleanText(dep).toLowerCase()
      if (!depClean || depClean === 'none') return

      topFiles.forEach((other, j) => {
        if (i === j) return
        const otherPath = String(other.path || '').toLowerCase()
        const otherStem = otherPath.split('/').pop()?.replace(/\..*$/, '') || ''
        if (
          (otherStem.length > 2 && depClean.includes(otherStem)) ||
          otherPath.includes(depClean)
        ) {
          const edgeKey = `${i}->${j}`
          if (!addedEdges.has(edgeKey)) {
            addedEdges.add(edgeKey)
            lines.push(`  ${safeId(i)} --> ${safeId(j)}`)
          }
        }
      })
    })
  })

  // Connect main entrypoint (F0) to main folder groups if few explicit edges were found
  if (addedEdges.size < 2 && topFiles.length > 1) {
    let prevFolderFirstIdx = 0
    groups.forEach((items, folderName) => {
      if (folderName !== 'Root' && items.length > 0) {
        const targetIdx = items[0].idx
        if (targetIdx !== 0) {
          lines.push(`  F0 --> ${safeId(targetIdx)}`)
        }
        for (let k = 0; k < items.length - 1; k++) {
          lines.push(`  ${safeId(items[k].idx)} --> ${safeId(items[k + 1].idx)}`)
        }
        prevFolderFirstIdx = targetIdx
      }
    })
  }

  return lines.join('\n')
}

export default function MermaidDiagram({ chart, files = [], repoName = 'Repository' }) {
  const scrollContainerRef = useRef(null)
  const [svgContent, setSvgContent] = useState('')
  const [effectiveChart, setEffectiveChart] = useState('')
  const [showRaw, setShowRaw] = useState(false)
  const [copied, setCopied] = useState(false)
  const [zoom, setZoom] = useState(1.25)
  const [direction, setDirection] = useState('LR')
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0, scrollLeft: 0, scrollTop: 0 })

  useEffect(() => {
    let isMounted = true
    async function renderMermaid() {
      // Always build the structured folder-grouped diagram when files are available
      // so all subfolders (src/, scripts/, notebooks/, etc.) are clearly organized and readable!
      const groupedDiagram =
        files && files.length > 0
          ? buildGroupedMermaidFromFiles(files, repoName, direction)
          : chart || `flowchart ${direction}\n  Root["${repoName}"]`

      try {
        const uniqueId = `mermaid-svg-${Math.random().toString(36).substring(2, 9)}`
        const { svg } = await mermaid.render(uniqueId, groupedDiagram)
        // Strip inline max-width so the SVG renders at true native pixel dimensions and scales crisply
        const crispSvg = svg.replace(/max-width:\s*[^;"]+;?/gi, '')
        if (isMounted) {
          setSvgContent(crispSvg)
          setEffectiveChart(groupedDiagram)
        }
      } catch {
        if (isMounted) {
          setEffectiveChart(groupedDiagram)
          setShowRaw(true)
        }
      }
    }
    renderMermaid()
    return () => {
      isMounted = false
    }
  }, [chart, files, repoName, direction])

  const handleCopy = () => {
    navigator.clipboard.writeText(effectiveChart || chart || '')
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleMouseDown = (e) => {
    if (!scrollContainerRef.current) return
    setIsDragging(true)
    setDragStart({
      x: e.pageX - scrollContainerRef.current.offsetLeft,
      y: e.pageY - scrollContainerRef.current.offsetTop,
      scrollLeft: scrollContainerRef.current.scrollLeft,
      scrollTop: scrollContainerRef.current.scrollTop,
    })
  }

  const handleMouseMove = (e) => {
    if (!isDragging || !scrollContainerRef.current) return
    e.preventDefault()
    const x = e.pageX - scrollContainerRef.current.offsetLeft
    const y = e.pageY - scrollContainerRef.current.offsetTop
    scrollContainerRef.current.scrollLeft = dragStart.scrollLeft - (x - dragStart.x)
    scrollContainerRef.current.scrollTop = dragStart.scrollTop - (y - dragStart.y)
  }

  const handleMouseUp = () => setIsDragging(false)

  return (
    <div
      className={
        isFullscreen
          ? 'fixed inset-0 z-50 bg-slate-950 flex flex-col p-4'
          : 'bg-slate-900/90 border border-slate-800 rounded-xl overflow-hidden shadow-lg'
      }
    >
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 bg-slate-900 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-200">
            Architecture Flowchart (Grouped by Folder)
          </span>
          <span className="text-xs text-slate-400 hidden sm:inline">
            • Drag to pan
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {!showRaw && (
            <>
              <button
                onClick={() => setDirection((d) => (d === 'LR' ? 'TD' : 'LR'))}
                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 transition mr-1"
                title="Switch Layout Direction (Left-to-Right vs Top-Down)"
              >
                <ArrowLeftRight className="w-3.5 h-3.5 text-indigo-400" />
                <span>{direction === 'LR' ? 'Layout: Left → Right' : 'Layout: Top ↓ Down'}</span>
              </button>

              <button
                onClick={() => setZoom((z) => Math.max(0.5, +(z - 0.25).toFixed(2)))}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                title="Zoom Out"
              >
                <ZoomOut className="w-4 h-4" />
              </button>
              <span className="text-xs font-mono text-slate-300 min-w-[3.2rem] text-center">
                {Math.round(zoom * 100)}%
              </span>
              <button
                onClick={() => setZoom((z) => Math.min(4.0, +(z + 0.25).toFixed(2)))}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                title="Zoom In (up to 400%)"
              >
                <ZoomIn className="w-4 h-4" />
              </button>
              <button
                onClick={() => setZoom(1.25)}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                title="Reset Zoom"
              >
                <RotateCcw className="w-4 h-4" />
              </button>

              <button
                onClick={() => setIsFullscreen((f) => !f)}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-indigo-300 transition mr-1"
                title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen Diagram'}
              >
                {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
              </button>
            </>
          )}

          <button
            onClick={() => setShowRaw((prev) => !prev)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              showRaw
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-800 hover:bg-slate-700 text-slate-300'
            }`}
          >
            <Code className="w-3.5 h-3.5" />
            {showRaw ? 'View Diagram' : 'View Mermaid Code'}
          </button>

          <button
            onClick={handleCopy}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-emerald-400">Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Diagram or Raw View */}
      {showRaw ? (
        <div className="p-4 bg-slate-950 overflow-auto flex-1">
          <pre className="text-xs font-mono text-indigo-200 leading-relaxed whitespace-pre-wrap">
            {effectiveChart}
          </pre>
        </div>
      ) : (
        <div
          ref={scrollContainerRef}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          className={`p-6 bg-slate-950/80 overflow-auto select-none ${
            isDragging ? 'cursor-grabbing' : 'cursor-grab'
          } ${isFullscreen ? 'flex-1' : 'min-h-[480px] max-h-[760px]'}`}
        >
          <div
            style={{
              zoom: zoom,
            }}
            className="inline-block min-w-max"
            dangerouslySetInnerHTML={{ __html: svgContent }}
          />
        </div>
      )}
    </div>
  )
}
