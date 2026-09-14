import { ChevronDown, ChevronRight, MapPinned } from 'lucide-react'
import { ZONE_COLORS } from '../lib/api'
import type { District, VillageRow } from '../lib/api'

interface Props {
  districts: District[]
  selected: District | null
  onSelect: (d: District) => void
  villageRows: VillageRow[]
  selectedVillageId: string
  onVillageSelect: (id: string) => void
}

const ZONE_ORDER = ['RED', 'ORANGE', 'YELLOW', 'GREEN'] as const

function displayDistrict(key: string) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export default function StateList({ districts, selected, onSelect, villageRows, selectedVillageId, onVillageSelect }: Props) {
  const groups = districts.reduce<Record<string, District[]>>((result, district) => {
    ;(result[district.state] ??= []).push(district)
    return result
  }, {})

  if (districts.length === 0) return <p className="text-xs text-slate-500 px-1">No districts found. Run the Hazard Intelligence pipeline first.</p>

  return <div className="flex flex-col gap-2">
    {Object.entries(groups).sort(([a], [b]) => a.localeCompare(b)).map(([state, stateDistricts]) => {
      const active = stateDistricts.some((district) => district.key === selected?.key)
      const total = stateDistricts.reduce((sum, district) => sum + district.village_count, 0)
      const counts = stateDistricts.reduce<Record<string, number>>((sum, district) => {
        Object.entries(district.red_zone_counts || {}).forEach(([zone, count]) => { sum[zone] = (sum[zone] || 0) + count })
        return sum
      }, {})
      return <div key={state} className={`rounded-xl border transition ${active ? 'bg-accent-500/10 border-accent-500/40 shadow-[0_0_20px_rgba(99,102,241,0.15)]' : 'bg-surface-800/60 border-surface-600/60 hover:border-surface-500'}`}>
        <button type="button" onClick={() => onSelect(selected && stateDistricts.some((district) => district.key === selected.key) ? selected : stateDistricts[0])} className="w-full text-left px-4 py-3 rounded-xl">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2.5 min-w-0"><div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-500/30 to-cyan-500/30 flex items-center justify-center shrink-0"><MapPinned className="w-4 h-4 text-accent-400" /></div><div className="min-w-0"><div className="text-sm font-semibold text-white truncate">{state}</div><div className="text-xs text-slate-400">{stateDistricts.length} district{stateDistricts.length === 1 ? '' : 's'} · {total.toLocaleString()} mapped units</div></div></div>
            {active ? <ChevronDown className="w-4 h-4 text-accent-400 shrink-0" /> : <ChevronRight className="w-4 h-4 text-slate-500 shrink-0" />}
          </div>
          <div className="flex items-center gap-1.5 mt-2.5">{ZONE_ORDER.filter((zone) => counts[zone]).map((zone) => <div key={zone} className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold text-white" style={{ backgroundColor: ZONE_COLORS[zone] }}>{zone} {counts[zone]}</div>)}<div className="ml-auto text-[10px] text-slate-400">{total} total</div></div>
        </button>
        {active && <div className="px-4 pb-3 -mt-1 space-y-2">
          <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Districts</div>
          {stateDistricts.sort((a, b) => a.key.localeCompare(b.key)).map((district) => {
            const selectedDistrict = district.key === selected?.key
            return <div key={district.key} className={`rounded-lg border ${selectedDistrict ? 'border-accent-500/40 bg-surface-800/80' : 'border-surface-600/60 bg-surface-800/40'}`}>
              <button type="button" onClick={() => onSelect(district)} className="w-full px-3 py-2 text-left flex items-center justify-between"><span className="text-xs font-medium text-white">{displayDistrict(district.key)}</span><span className="text-[10px] text-slate-400">{district.village_count} units</span></button>
              {selectedDistrict && <div className="px-3 pb-3">
                {villageRows.length > 0 ? <select value={selectedVillageId} onChange={(event) => onVillageSelect(event.target.value)} className="w-full appearance-none px-3 py-2 rounded-lg bg-surface-800 border border-surface-600 text-sm text-white focus:border-accent-500 focus:outline-none transition cursor-pointer"><option value="">All units — whole district</option>{villageRows.map((row) => <option key={row.village_id} value={String(row.village_id)}>{row.name} ({String(row.village_id)})</option>)}</select> : <p className="text-[11px] text-slate-500">Loading mapped units…</p>}
              </div>}
            </div>
          })}
        </div>}
      </div>
    })}
  </div>
}
