import '@fontsource/geist/latin-400.css'
import '@fontsource/geist/latin-500.css'
import '@fontsource/geist/latin-600.css'
import '@fontsource/geist/latin-ext-400.css'
import '@fontsource/geist/latin-ext-500.css'
import '@fontsource/geist/latin-ext-600.css'
import { StrictMode, useEffect, useMemo } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { BrowserRouter, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { create } from 'zustand'
import { request } from './api'
import type { AppState } from './api'
import { demoStepsFor } from './demo/script'
import type { ItemRow } from './api'
import { CampaignsView, Collection, Compare, CriteriaView, Home, Material, NewMaterial } from './views'
import './style.css'

type UiState = { theme: 'system' | 'light' | 'dark'; demo: boolean; step: number; setTheme: (theme: UiState['theme']) => void; setDemo: (demo: boolean) => void; setStep: (step: number) => void }
const useUi = create<UiState>(set => ({ theme: 'system', demo: false, step: 0, setTheme: theme => set({ theme }), setDemo: demo => set({ demo }), setStep: step => set({ step }) }))
const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 10_000 } } })
const nav = [
  ['/', 'Przegląd'], ['/collection', 'Zbiór'], ['/items', 'Materiał'], ['/compare', 'Porównanie'], ['/criteria', 'Kryteria'], ['/campaigns', 'Kampanie'], ['/new', 'Nowy materiał'],
] as const

function App() {
  const { theme, demo, step, setTheme, setDemo, setStep } = useUi()
  const location = useLocation()
  const navigate = useNavigate()
  const state = useQuery({ queryKey: ['state'], queryFn: () => request<AppState>('/state') })
  const itemRows = useQuery({ queryKey: ['items'], queryFn: () => request<ItemRow[]>('/items') })
  const demoSteps = useMemo(() => demoStepsFor((itemRows.data || []).map(row => row.id)), [itemRows.data])
  useEffect(() => { document.documentElement.dataset.theme = theme }, [theme])
  const go = (index: number) => {
    const bounded = Math.max(0, Math.min(demoSteps.length - 1, index))
    setStep(bounded)
    const target = demoSteps[bounded]
    const path = target.view === '/items' && target.item ? `/items/${encodeURIComponent(target.item)}` : target.view
    const hash = target.hash ? `#${target.hash}` : ''
    const params = target.view === '/compare' ? `?a=${encodeURIComponent(target.item || '')}&b=${encodeURIComponent(target.other || '')}` : target.analyze ? `?demo_item=${encodeURIComponent(target.analyze)}` : target.sample ? `?demo_sample=${target.sample}` : ''
    navigate(path + params + hash)
  }
  useEffect(() => {
    if (!demo) return
    const key = (event: KeyboardEvent) => {
      const active = document.activeElement
      if (active && ['INPUT', 'TEXTAREA', 'SELECT'].includes(active.tagName)) return
      if (event.key === 'ArrowRight' || event.key === ' ') { event.preventDefault(); go(step + 1) }
      if (event.key === 'ArrowLeft') { event.preventDefault(); go(step - 1) }
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [demo, step])
  const startDemo = () => { setDemo(true); go(0) }
  const logo = theme === 'dark' || (theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches) ? '/logo-dark.svg' : '/logo.svg'
  return <div className="appShell">
    <header className="topbar"><div className="topbarInner"><NavLink to="/" className="brand" aria-label="mimic, strona główna"><img src={logo} alt="mimic" /></NavLink><nav className="mainNav" aria-label="Główna nawigacja">{nav.map(([to, label]) => <NavLink key={to} to={to} className={({ isActive }) => isActive || (to === '/items' && location.pathname.startsWith('/items/')) ? 'active' : ''} end={to === '/'}>{label}</NavLink>)}</nav><div className="headerActions"><button className="showButton" onClick={demo ? () => setDemo(false) : startDemo}>{demo ? 'Zakończ pokaz' : 'Tryb pokazu'}</button><label className="themeSelect"><span className="srOnly">Motyw</span><select value={theme} onChange={event => setTheme(event.target.value as UiState['theme'])} aria-label="Motyw"><option value="system">Systemowy</option><option value="light">Jasny</option><option value="dark">Ciemny</option></select></label></div></div></header>
    {demo && <div className="demoBar"><div className="demoProgress">{demoSteps.map((item, index) => <button key={index} className={index === step ? 'activeStep' : ''} onClick={() => go(index)} aria-label={`Krok ${index + 1}: ${item.title}`} title={item.title}>{index + 1}</button>)}</div><div className="demoCaption"><strong>{demoSteps[step].title}</strong><span>{demoSteps[step].description}</span></div><div className="demoActions"><button disabled={step === 0} onClick={() => go(step - 1)}>Wstecz</button><button className="primaryButton" disabled={step === demoSteps.length - 1} onClick={() => go(step + 1)}>Dalej</button></div></div>}
    <main className={demo ? 'demoMain' : ''}>{state.isError ? <div className="apiError card"><h1>Nie można połączyć się z API</h1><p>Uruchom serwer poleceniem <code>make api</code>, a potem odśwież stronę.</p><button onClick={() => state.refetch()}>Spróbuj ponownie</button></div> : <Routes><Route path="/" element={<Home theme={theme} />} /><Route path="/collection" element={<Collection />} /><Route path="/map" element={<Navigate to="/#mapa" replace />} /><Route path="/items/*" element={<Material demo={demo} />} /><Route path="/compare" element={<Compare />} /><Route path="/criteria" element={<CriteriaView />} /><Route path="/campaigns" element={<CampaignsView />} /><Route path="/new" element={<NewMaterial />} /></Routes>}</main>
    <footer>mimic · Szymon Pytel · Wojciech Palczewski</footer>
  </div>
}

createRoot(document.getElementById('root')!).render(<StrictMode><QueryClientProvider client={queryClient}><BrowserRouter><App /></BrowserRouter></QueryClientProvider></StrictMode>)
