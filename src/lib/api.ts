const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export function getToken(): string | null {
  return localStorage.getItem('sih_token')
}

export function setToken(token: string) {
  localStorage.setItem('sih_token', token)
}

export function clearToken() {
  localStorage.removeItem('sih_token')
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (res.status === 401) {
    clearToken()
    window.location.href = '/'
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail || `Request failed (${res.status})`)
  }
  return res.json() as Promise<T>
}

export const api = {
  login: (username: string, password: string) =>
    request<{ token: string; username: string }>('/api/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  districts: () => request<{ districts: District[] }>('/api/districts'),

  villages: (key: string) =>
    request<GeoJSON.FeatureCollection>(`/api/districts/${key}/villages`),

  table: (key: string, limit = 1000) =>
    request<{ district: string; rows: VillageRow[] }>(`/api/districts/${key}/table?limit=${limit}`),

  search: (q: string) =>
    request<{ results: SearchResult[] }>(`/api/search?q=${encodeURIComponent(q)}`),

  health: () => request<{ status: string; districts: string[] }>('/api/health'),
}

export interface District {
  key: string
  state: string
  village_count: number
  red_zone_counts: Record<string, number>
}

export interface VillageRow {
  village_id: string | number
  name: string
  district: string
  state: string
  flood_score: number
  landslide_score: number
  cloudburst_score: number
  coastal_erosion_score: number
  dem?: number
  slope?: number
  multi_hazard: number
  risk_category: string
  red_zone_status: string
  relocation_priority?: number
}

export interface SearchResult {
  village_id: string
  name: string
  district: string
  state: string
  red_zone_status: string
  multi_hazard: number
}

export const ZONE_COLORS: Record<string, string> = {
  RED: '#ef4444',
  ORANGE: '#f97316',
  YELLOW: '#eab308',
  GREEN: '#22c55e',
}

export const ZONE_DESC: Record<string, string> = {
  RED: 'Very High Risk',
  ORANGE: 'High Risk',
  YELLOW: 'Moderate Risk',
  GREEN: 'Low Risk',
}

export function villageKey(id: string | number | undefined | null): string {
  const s = String(id ?? '')
  return s.replace(/^0+/, '') || s
}