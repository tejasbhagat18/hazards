import { useEffect, useRef, useState } from 'react'
import { Search } from 'lucide-react'
import { api, ZONE_COLORS } from '../lib/api'
import type { SearchResult } from '../lib/api'

interface Props {
  onSelect: (result: SearchResult) => void
}

export default function SearchBox({ onSelect }: Props) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [open, setOpen] = useState(false)
  const boxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  useEffect(() => {
    if (!q.trim()) {
      setResults([])
      return
    }
    const t = setTimeout(async () => {
      try {
        const res = await api.search(q.trim())
        setResults(res.results)
      } catch {
        setResults([])
      }
    }, 300)
    return () => clearTimeout(t)
  }, [q])

  return (
    <div ref={boxRef} className="relative">
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-800 border border-surface-600 focus-within:border-accent-500 transition">
        <Search className="w-4 h-4 text-slate-400 shrink-0" />
        <input
          value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          placeholder="Search for a village…"
          className="bg-transparent outline-none text-sm text-white w-full placeholder:text-slate-500"
        />
      </div>

      {open && results.length > 0 && (
        <div className="absolute z-30 mt-2 w-full glass rounded-lg border border-surface-600 overflow-hidden max-h-72 overflow-y-auto">
          {results.map((r, i) => (
            <button
              key={`${r.district}-${r.village_id}-${i}`}
              onClick={() => { onSelect(r); setOpen(false); setQ(r.name) }}
              className="w-full text-left px-3 py-2.5 hover:bg-surface-700/60 transition border-b border-surface-600/50 last:border-0"
            >
              <div className="flex items-center justify-between">
                <div className="min-w-0">
                  <div className="text-sm font-medium text-white truncate">{r.name}</div>
                  <div className="text-xs text-slate-400">
                    {r.state} · {r.district}
                  </div>
                </div>
                <span
                  className="shrink-0 ml-2 text-[11px] font-bold px-2 py-0.5 rounded-full text-white"
                  style={{ backgroundColor: ZONE_COLORS[r.red_zone_status] || '#888' }}
                >
                  {r.red_zone_status}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}

      {open && q.trim() && results.length === 0 && (
        <div className="absolute z-30 mt-2 w-full glass rounded-lg border border-surface-600 px-3 py-2.5 text-xs text-slate-400">
          No villages found for "{q}"
        </div>
      )}
    </div>
  )
}