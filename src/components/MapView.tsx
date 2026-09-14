import { useEffect, useMemo, useRef, useState } from 'react'
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { ZONE_COLORS, ZONE_DESC, villageKey } from '../lib/api'
import type { District, VillageRow } from '../lib/api'
import VillageInfoPanel from './VillageInfoPanel'

interface Props {
  district: District
  geojson: GeoJSON.FeatureCollection
  villageRows: VillageRow[]
  highlightId?: string | null
  flyTo?: { lon: number; lat: number; id: string } | null
  fitSignal?: number
}

const ZONE_ORDER = ['RED', 'ORANGE', 'YELLOW', 'GREEN'] as const

function Legend() {
  return (
    <div className="absolute bottom-6 right-4 z-[400] glass rounded-lg border border-surface-600 px-3 py-2 shadow-lg">
      <div className="text-[10px] font-bold text-slate-300 mb-1.5 uppercase tracking-wider">Red Zone</div>
      <div className="space-y-1">
        {ZONE_ORDER.map((z) => (
          <div key={z} className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: ZONE_COLORS[z] }} />
            <span className="text-[11px] text-slate-300">{z} — {ZONE_DESC[z]}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function MapController({
  geojson,
  flyTo,
  fitSignal,
  mapRef,
}: {
  geojson: GeoJSON.FeatureCollection
  flyTo: { lon: number; lat: number; id: string } | null
  fitSignal?: number
  mapRef?: React.MutableRefObject<L.Map | null>
}) {
  const map = useMap()
  const pastSource = useRef<GeoJSON.FeatureCollection | null>(null)

  useEffect(() => {
    if (mapRef) mapRef.current = map
  }, [map, mapRef])

  useEffect(() => {
    if (geojson && geojson !== pastSource.current) {
      pastSource.current = geojson
      map.fitBounds(L.geoJSON(geojson).getBounds(), { padding: [28, 28] })
    }
  }, [geojson, map])

  useEffect(() => {
    if (flyTo) {
      map.flyTo([flyTo.lat, flyTo.lon], Math.max(map.getZoom(), 14), { duration: 1.1 })
    }
  }, [flyTo, map])

  useEffect(() => {
    if (geojson && (fitSignal ?? 0) > 0) {
      map.fitBounds(L.geoJSON(geojson).getBounds(), { padding: [28, 28] })
    }
  }, [fitSignal, geojson, map])

  return null
}

function centroidOfFeature(feature: GeoJSON.Feature | undefined): { lon: number; lat: number } | null {
  try {
    const g = feature?.geometry
    if (!g) return null
    const ring = g.type === 'Polygon' ? g.coordinates[0] : g.type === 'MultiPolygon' ? g.coordinates?.[0]?.[0] : null
    if (ring && ring.length) {
      const lon = ring.reduce((a: number, p: number[]) => a + p[0], 0) / ring.length
      const lat = ring.reduce((a: number, p: number[]) => a + p[1], 0) / ring.length
      return { lon, lat }
    }
  } catch {
    /* ignore */
  }
  return null
}

export default function MapView({ district, geojson, villageRows, highlightId, flyTo, fitSignal }: Props) {
  const [selected, setSelected] = useState<VillageRow | null>(null)
  const [clickedId, setClickedId] = useState<string | null>(null)
  const mapRef = useRef<L.Map | null>(null)

  const rowsById = useMemo(() => {
    const m = new Map<string, VillageRow>()
    villageRows.forEach((r) => m.set(villageKey(r.village_id), r))
    return m
  }, [villageRows])

  useEffect(() => {
    setSelected(null)
    setClickedId(null)
  }, [district])

  useEffect(() => {
    if (highlightId) {
      const row = rowsById.get(villageKey(highlightId))
      if (row) setSelected(row)
    }
  }, [highlightId, rowsById])

  const styleFn = useMemo(
    () => ((feature: GeoJSON.Feature | undefined) => {
      const zone = feature?.properties?.red_zone_status as string
      const color = ZONE_COLORS[zone] || '#555'
      const selKey = highlightId && villageKey(highlightId)
      const isSel = !!selKey && (villageKey(feature?.properties?.village_id) === selKey || villageKey(feature?.properties?.village_id) === villageKey(clickedId))
      return {
        fillColor: color,
        color: isSel ? '#ffffff' : 'rgba(255,255,255,0.25)',
        weight: isSel ? 2 : 0.6,
        fillOpacity: isSel ? 0.85 : 0.5,
      }
    }),
    [highlightId, clickedId],
  )

  const onEach = (feature: GeoJSON.Feature, layer: L.Layer) => {
    const id = String(feature?.properties?.village_id ?? '')
    const name = String(feature?.properties?.name ?? '')
    layer.on({
      click: () => {
        const row = rowsById.get(villageKey(id))
        setClickedId(villageKey(id))
        if (row) {
          setSelected(row)
          const c = centroidOfFeature(feature)
          if (c && mapRef.current) {
            mapRef.current.flyTo([c.lat, c.lon], Math.max(mapRef.current.getZoom(), 14), {
              duration: 1,
              animate: true,
            })
          }
        }
        ;(layer as L.Path).bringToFront()
      },
      mouseover: (e) => {
        const l = e.target as L.Path
        l.setStyle({ weight: 1.5, fillOpacity: 0.7, color: '#fff' })
        l.bindTooltip(name, { sticky: true, direction: 'top' }).openTooltip()
      },
      mouseout: (e) => {
        const l = e.target as L.Path
        l.setStyle({
          weight: 0.6,
          fillOpacity: 0.5,
          color: 'rgba(255,255,255,0.25)',
        })
        l.closeTooltip()
      },
    })
  }

  return (
    <div className="relative h-full w-full">
      <MapContainer
        center={[22.5, 79.5]}
        zoom={5}
        className="h-full w-full"
        style={{ background: '#0a0a0f' }}
        zoomControl={false}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; OpenStreetMap contributors'
        />
        <GeoJSON data={geojson} style={styleFn} onEachFeature={onEach} />
        <MapController geojson={geojson} flyTo={flyTo ?? null} fitSignal={fitSignal} mapRef={mapRef} />
      </MapContainer>

      <Legend />
      {selected && <VillageInfoPanel village={selected} district={district.key} onClose={() => setSelected(null)} />}

      {!district && (
        <div className="absolute inset-0 flex items-center justify-center bg-surface-900/50 z-[300]">
          <p className="text-sm text-slate-400">Select a state to view its villages</p>
        </div>
      )}
    </div>
  )
}
