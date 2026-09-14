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

export default function StateList({
  districts,
  selected,
  onSelect,
  villageRows,
  selectedVillageId,
  onVillageSelect,
}: Props) {
  return (
    <div className="flex flex-col gap-2">
      {districts.length === 0 && (
        <p className="text-xs text-slate-500 px-1">
          No districts found. Run the Module 1 pipeline first.
        </p>
      )}

      {districts.map((d) => {
        const active = selected?.key === d.key
        const total = Object.values(d.red_zone_counts || {}).reduce((a, b) => a + b, 0)
        return (
          <div
            key={d.key}
            className={`rounded-xl border transition ${
              active
                ? 'bg-accent-500/10 border-accent-500/40 shadow-[0_0_20px_rgba(99,102,241,0.15)]'
                : 'bg-surface-800/60 border-surface-600/60 hover:border-surface-500'
            }`}
          >
            <button
              type="button"
              onClick={() => onSelect(d)}
              className="w-full text-left px-4 py-3 rounded-xl"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-500/30 to-cyan-500/30 flex items-center justify-center shrink-0">
                    <MapPinned className="w-4 h-4 text-accent-400" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-white truncate">{d.state}</div>
                    <div className="text-xs text-slate-400">
                      {d.village_count.toLocaleString()} villages
                    </div>
                  </div>
                </div>
                {active ? (
                  <ChevronDown className="w-4 h-4 text-accent-400 shrink-0" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-slate-500 shrink-0" />
                )}
              </div>

              {Object.keys(d.red_zone_counts || {}).length > 0 && (
                <div className="flex items-center gap-1.5 mt-2.5">
                  {ZONE_ORDER.filter((z) => d.red_zone_counts?.[z]).map((z) => (
                    <div
                      key={z}
                      className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold text-white"
                      style={{ backgroundColor: ZONE_COLORS[z] }}
                    >
                      {z} {d.red_zone_counts[z]}
                    </div>
                  ))}
                  <div className="ml-auto text-[10px] text-slate-400">{total} total</div>
                </div>
              )}
            </button>

            {active && (
              <div className="px-4 pb-3 -mt-1">
                {villageRows.length > 0 ? (
                  <div>
                    <label className="block text-[10px] font-bold text-slate-400 mb-1 uppercase tracking-wider">
                      {d.state} Villages
                    </label>
                    <div className="relative">
                      <select
                        value={selectedVillageId}
                        onChange={(e) => onVillageSelect(e.target.value)}
                        className="w-full appearance-none px-3 py-2 pr-8 rounded-lg bg-surface-800 border border-surface-600 text-sm text-white focus:border-accent-500 focus:outline-none transition cursor-pointer"
                      >
                        <option value="">All villages — whole state</option>
                        {villageRows.map((r) => (
                          <option key={r.village_id} value={String(r.village_id)}>
                            {r.name} ({String(r.village_id)})
                          </option>
                        ))}
                      </select>
                      <ChevronDown className="w-4 h-4 text-slate-500 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                    </div>
                  </div>
                ) : (
                  <p className="text-[11px] text-slate-500">Loading villages…</p>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}