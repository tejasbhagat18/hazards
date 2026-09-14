import { useEffect, useState } from 'react'
import { AlertTriangle, Database, X } from 'lucide-react'
import { api, ZONE_COLORS, ZONE_DESC } from '../lib/api'
import type { RiskProfile, VillageRow } from '../lib/api'

interface Props {
  village: VillageRow
  district: string
  onClose: () => void
}

function ScoreBar({ label, value, level, color }: { label: string; value: number | null; level: string; color: string }) {
  const pct = Math.round((value ?? 0) * 100)
  return <div>
    <div className="flex items-center justify-between gap-2 text-xs mb-1"><span className="text-slate-300 truncate">{label}</span><span className="font-mono text-slate-200 shrink-0">{value === null ? 'N/A' : `${pct}/100`} · {level}</span></div>
    <div className="h-1.5 rounded-full bg-surface-700 overflow-hidden"><div className="h-full rounded-full transition-all" style={{ width: `${Math.min(100, pct)}%`, backgroundColor: color }} /></div>
  </div>
}

function riskColor(level: string) {
  return ZONE_COLORS[level === 'Very High' ? 'RED' : level === 'High' ? 'ORANGE' : level === 'Moderate' ? 'YELLOW' : 'GREEN']
}

export default function VillageInfoPanel({ village, district, onClose }: Props) {
  const [profile, setProfile] = useState<RiskProfile | null>(null)
  const [error, setError] = useState('')
  const zone = village.red_zone_status
  const color = ZONE_COLORS[zone] || '#888'

  useEffect(() => {
    let active = true
    setProfile(null)
    setError('')
    api.riskProfile(district, String(village.village_id))
      .then((result) => { if (active) setProfile(result) })
      .catch(() => { if (active) setError('Risk explanation is unavailable.') })
    return () => { active = false }
  }, [district, village.village_id])

  return <div className="absolute top-3 left-3 z-[400] w-80 max-h-[calc(100%-24px)] overflow-y-auto glass rounded-xl border border-surface-600 shadow-2xl">
    <div className="px-4 py-3 flex items-start justify-between border-b border-surface-600/60" style={{ borderLeft: `3px solid ${color}` }}>
      <div className="min-w-0"><h3 className="text-sm font-bold text-white truncate">{village.name}</h3><p className="text-[11px] text-slate-400">{village.state} · {village.district}</p></div>
      <button onClick={onClose} aria-label="Close risk profile" className="text-slate-500 hover:text-white transition"><X className="w-4 h-4" /></button>
    </div>
    <div className="px-4 py-3 space-y-4">
      <div className="flex items-center gap-2"><span className="text-[11px] font-bold px-2.5 py-1 rounded-full text-white" style={{ backgroundColor: color }}>{zone} — {ZONE_DESC[zone]}</span><span className="text-[10px] text-slate-400">Static / historical assessment</span></div>
      {profile ? <>
        <div className="rounded-lg bg-surface-800/70 px-3 py-2.5"><div className="text-[10px] uppercase tracking-wider text-slate-400">Multi-Hazard Risk</div><div className="flex items-end justify-between mt-1"><span className="text-lg font-bold text-white">{profile.overall_risk_level}</span><span className="font-mono text-sm text-slate-200">{Math.round((profile.overall_risk_score ?? 0) * 100)}/100</span></div></div>
        <div className="space-y-2.5"><div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Hazard indicators</div>{profile.hazards.map((hazard) => <ScoreBar key={hazard.hazard_type} label={hazard.display_name} value={hazard.hazard_score} level={hazard.risk_level} color={riskColor(hazard.risk_level)} />)}</div>
        <div className="border-t border-surface-600/60 pt-3 space-y-2"><div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Key contributors</div>{profile.top_contributors.map((item) => <div key={item.hazard_type} className="text-xs text-slate-300">• {item.label} — {item.level}</div>)}</div>
        <div className="rounded-lg bg-surface-800/70 px-3 py-2 flex items-center gap-2"><Database className="w-3.5 h-3.5 text-cyan-400" /><div className="text-xs"><span className="text-slate-400">Confidence: </span><span className="text-white font-semibold">{profile.risk_confidence_level} — {Math.round(profile.risk_confidence * 100)}%</span></div></div>
        {profile.missing_data.length > 0 && <div className="flex gap-2 text-xs text-amber-400"><AlertTriangle className="w-3.5 h-3.5 shrink-0" />Missing: {profile.missing_data.join(', ')}</div>}
        <p className="text-[10px] text-slate-500">{profile.method} · {profile.model_version}</p>
      </> : <p className={`text-xs ${error ? 'text-rose-400' : 'text-slate-400'}`}>{error || 'Loading explainable risk profile…'}</p>}
    </div>
  </div>
}
