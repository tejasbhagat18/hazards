import { X } from 'lucide-react'
import { ZONE_COLORS, ZONE_DESC } from '../lib/api'
import type { VillageRow } from '../lib/api'

interface Props {
  village: VillageRow
  onClose: () => void
}

function ScoreBar({ label, value, color }: { label: string; value: number; color: string }) {
  const pct = Math.round(((value || 0) / 1) * 100)
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="text-slate-400">{label}</span>
        <span className="font-mono text-slate-200">{(value || 0).toFixed(2)}</span>
      </div>
      <div className="h-1.5 rounded-full bg-surface-700 overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${Math.min(100, pct)}%`, backgroundColor: color }}
        />
      </div>
    </div>
  )
}

export default function VillageInfoPanel({ village, onClose }: Props) {
  const zone = village.red_zone_status
  const color = ZONE_COLORS[zone] || '#888'

  return (
    <div className="absolute top-3 left-3 z-[400] w-72 glass rounded-xl border border-surface-600 overflow-hidden shadow-2xl">
      <div className="px-4 py-3 flex items-start justify-between border-b border-surface-600/60" style={{ borderLeft: `3px solid ${color}` }}>
        <div className="min-w-0">
          <h3 className="text-sm font-bold text-white truncate">{village.name}</h3>
          <p className="text-[11px] text-slate-400">{village.state} · {village.district}</p>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-white transition">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="px-4 py-3 space-y-4">
        <div className="flex items-center gap-2">
          <span
            className="text-[11px] font-bold px-2.5 py-1 rounded-full text-white"
            style={{ backgroundColor: color }}
          >
            {zone} — {ZONE_DESC[zone]}
          </span>
        </div>

        <div className="space-y-2.5">
          <ScoreBar label="Multi-Hazard Score" value={village.multi_hazard} color={color} />
          <ScoreBar label="Risk Category" value={0} color="#888" />
          <ScoreBar label="Flood" value={village.flood_score} color="#3b82f6" />
          <ScoreBar label="Landslide" value={village.landslide_score} color="#a855f7" />
          <ScoreBar label="Coastal Erosion" value={village.coastal_erosion_score} color="#06b6d4" />
          <ScoreBar label="Cloudburst" value={village.cloudburst_score} color="#f59e0b" />
        </div>

        <div className="grid grid-cols-2 gap-2 pt-1 border-t border-surface-600/60">
          <div className="rounded-lg bg-surface-800/70 px-3 py-2">
            <div className="text-[10px] text-slate-400">Relocation Priority</div>
            <div className="text-sm font-mono text-white">
              {(village.relocation_priority ?? 0).toFixed(3)}
            </div>
          </div>
          <div className="rounded-lg bg-surface-800/70 px-3 py-2">
            <div className="text-[10px] text-slate-400">Village ID</div>
            <div className="text-sm font-mono text-white truncate">{village.village_id}</div>
          </div>
        </div>
      </div>
    </div>
  )
}