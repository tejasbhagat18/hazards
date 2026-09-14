import { useEffect, useRef, useState } from 'react'
import { LogOut, Loader2, ShieldAlert } from 'lucide-react'
import { motion } from 'framer-motion'
import { api, clearToken, villageKey } from '../lib/api'
import type { District, SearchResult, VillageRow } from '../lib/api'
import StateList from './StateList'
import SearchBox from './SearchBox'
import MapView from './MapView'

interface Props {
  onLogout: () => void
}

export default function Dashboard({ onLogout }: Props) {
  const [districts, setDistricts] = useState<District[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<District | null>(null)
  const [geojson, setGeojson] = useState<GeoJSON.FeatureCollection | null>(null)
  const [rows, setRows] = useState<VillageRow[]>([])
  const [districtLoading, setDistrictLoading] = useState(false)
  const [highlightId, setHighlightId] = useState<string | null>(null)
  const [flyTo, setFlyTo] = useState<{ lon: number; lat: number; id: string } | null>(null)
  const [fitSignal, setFitSignal] = useState(0)
  const [summary, setSummary] = useState<{ total: number; hazard: string } | null>(null)
  const [selectedVillage, setSelectedVillage] = useState('')
  const pendingRef = useRef<string | null>(null)

  useEffect(() => {
    api
      .districts()
      .then((res) => {
        setDistricts(res.districts)
        if (res.districts.length > 0) setSelected(res.districts[0])
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!selected) return
    setDistrictLoading(true)
    setGeojson(null)
    setRows([])
    setHighlightId(null)
    setFlyTo(null)
    setSelectedVillage('')
    setSummary(null)
    setFitSignal(0)

    Promise.all([api.villages(selected.key), api.table(selected.key, 3000)])
      .then(([gj, tbl]) => {
        setGeojson(gj)
        setRows(tbl.rows)
        const zones = selected.red_zone_counts || {}
        const top = tbl.rows[0]
        setSummary({
          total: selected.village_count,
          hazard: top
            ? `Top risk: ${top.name} (${(top.multi_hazard * 100).toFixed(1)}%)`
            : `Zones: ${Object.entries(zones).map(([k, v]) => `${k} ${v}`).join(', ')}`,
        })

        const pid = pendingRef.current
        if (pid) {
          pendingRef.current = null
          const c = centroidOf(gj, pid)
          setHighlightId(pid)
          setSelectedVillage(pid)
          if (c) setFlyTo({ lon: c[0], lat: c[1], id: pid })
        }
      })
      .finally(() => setDistrictLoading(false))
  }, [selected])

  const focusVillage = (id: string) => {
    setHighlightId(id)
    setSelectedVillage(id)
    const fc = geojson
    if (fc) {
      const c = centroidOf(fc, id)
      if (c) setFlyTo({ lon: c[0], lat: c[1], id })
    }
  }

  const clearVillage = () => {
    setSelectedVillage('')
    setHighlightId(null)
    setFlyTo(null)
    setFitSignal((s) => s + 1)
  }

  const handleVillagePick = (id: string) => {
    if (id) focusVillage(id)
    else clearVillage()
  }

  const handleSearchSelect = (result: SearchResult) => {
    const d = districts.find((x) => x.key === result.district)
    if (d && d.key !== selected?.key) {
      pendingRef.current = result.village_id
      setSelected(d)
      return
    }
    focusVillage(result.village_id)
  }

  return (
    <div className="h-screen flex flex-col bg-surface-900 overflow-hidden">
      {/* Top bar */}
      <header className="h-14 px-5 flex items-center justify-between border-b border-surface-700/60 bg-surface-800/50 backdrop-blur">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-500 to-cyan-500 flex items-center justify-center">
            <ShieldAlert className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white leading-tight">Red Zone Intelligence Platform</h1>
            <p className="text-[10px] text-slate-400">SIH 2026 · Module 1 — Hazard Intelligence</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[11px] font-medium text-emerald-400">Live Data</span>
          </div>
          <button
            onClick={() => { clearToken(); onLogout() }}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition px-2 py-1.5 rounded-lg hover:bg-surface-700"
          >
            <LogOut className="w-3.5 h-3.5" /> Logout
          </button>
        </div>
      </header>

      {/* Body: 30% sidebar / 70% map */}
      <div className="flex flex-1 min-h-0">
        {/* LEFT PANEL - 30% */}
        <aside className="w-[30%] min-w-[260px] max-w-[360px] flex flex-col border-r border-surface-700/60 bg-surface-800/30">
          <div className="p-4 border-b border-surface-700/60">
            <SearchBox onSelect={handleSearchSelect} />
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {loading ? (
              <div className="flex items-center justify-center py-10">
                <Loader2 className="w-5 h-5 text-accent-400 animate-spin" />
              </div>
            ) : (
              <StateList
                districts={districts}
                selected={selected}
                onSelect={setSelected}
                villageRows={rows}
                selectedVillageId={selectedVillage}
                onVillageSelect={handleVillagePick}
              />
            )}
          </div>

          {summary && (
            <div className="px-4 py-3 border-t border-surface-700/60">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Selected: <span className="text-white font-semibold">{summary.total.toLocaleString()}</span> villages</span>
                <span className="text-slate-300 truncate max-w-[180px]">{summary.hazard}</span>
              </div>
            </div>
          )}
        </aside>

        {/* RIGHT PANEL - 70% map */}
        <main className="flex-1 min-w-0 relative">
          {districtLoading && (
            <div className="absolute top-3 right-4 z-[400] glass rounded-lg px-3 py-1.5 text-xs text-slate-300 flex items-center gap-2">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-accent-400" />
              Loading {selected?.state}…
            </div>
          )}

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6 }}
            className="h-full w-full"
          >
            {geojson && selected ? (
              <MapView
                district={selected}
                geojson={geojson}
                villageRows={rows}
                highlightId={highlightId}
                flyTo={flyTo}
                fitSignal={fitSignal}
              />
            ) : (
              <div className="h-full w-full flex items-center justify-center bg-surface-900">
                <p className="text-sm text-slate-500">
                  {loading ? 'Loading districts…' : 'Select a state to view its Red Zone map'}
                </p>
              </div>
            )}
          </motion.div>
        </main>
      </div>
    </div>
  )
}

function centroidOf(fc: GeoJSON.FeatureCollection, id: string): [number, number] | null {
  try {
    const feat = fc.features.find((f) => villageKey(f.properties?.village_id) === villageKey(id))
    if (!feat) return null
    const g = feat.geometry
    const ring = g.type === 'Polygon' ? g.coordinates[0] : g.type === 'MultiPolygon' ? g.coordinates[0][0] : null
    if (ring) {
      const lon = ring.reduce((a: number, p: number[]) => a + p[0], 0) / ring.length
      const lat = ring.reduce((a: number, p: number[]) => a + p[1], 0) / ring.length
      return [lon, lat]
    }
  } catch {
    /* ignore */
  }
  return null
}