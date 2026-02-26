import { useState, useEffect, useRef, useCallback } from 'react'

const CONNECTOR_META = {
  gmail: { emoji: '\ud83d\udce7', label: 'Gmail', color: '#ea4335' },
  work_email: { emoji: '\ud83d\udcbc', label: 'Work Email', color: '#4285f4' },
  telegram: { emoji: '\ud83d\udcac', label: 'Telegram', color: '#26a5e4' },
  github: { emoji: '\ud83d\udc19', label: 'GitHub', color: '#8b5cf6' },
  supabase: { emoji: '\u26a1', label: 'Supabase', color: '#3ecf8e' },
  firebase: { emoji: '\ud83d\udd25', label: 'Firebase', color: '#ffca28' },
  yahoo_finance: { emoji: '\ud83d\udcc8', label: 'Yahoo Finance', color: '#7b61ff' },
  whatsapp: { emoji: '\ud83d\udcac', label: 'WhatsApp', color: '#25d366' },
}

const PRIORITY_STYLES = {
  high: { bg: 'bg-red-500/15', text: 'text-red-400', border: 'border-red-500/20', label: 'High' },
  medium: { bg: 'bg-yellow-500/15', text: 'text-yellow-400', border: 'border-yellow-500/20', label: 'Med' },
  low: { bg: 'bg-green-500/15', text: 'text-green-400', border: 'border-green-500/20', label: 'Low' },
}

const TIMEFRAME_OPTIONS = [
  { value: '1h', label: 'Last hour' },
  { value: '2h', label: 'Last 2 hours' },
  { value: '5h', label: 'Last 5 hours' },
  { value: '12h', label: 'Last 12 hours' },
  { value: '24h', label: 'Last 24 hours' },
  { value: '48h', label: 'Last 2 days' },
  { value: '7d', label: 'Last 7 days' },
]

const DEFAULT_CONNECTOR_CONFIG = { enabled: true, timeframe: '24h', max_results: 10 }

const CONNECTOR_SPECIFIC_SETTINGS = {
  yahoo_finance: {
    key: 'symbols',
    label: 'Watchlist',
    placeholder: 'AAPL, TSLA, MSFT, BTC-USD',
    help: 'Comma-separated tickers',
  },
  github: {
    key: 'repos',
    label: 'Repos',
    placeholder: 'owner/repo1, owner/repo2',
    help: 'Comma-separated repos for PRs',
    fetchable: true,
  },
}

function BriefingSettings({ connectedNames, config, onChange, onSave, saving, saved }) {
  const connectorConfigs = config.connectors || {}
  const [loadingRepos, setLoadingRepos] = useState(false)
  const [availableRepos, setAvailableRepos] = useState(null)
  const [tickerQuery, setTickerQuery] = useState('')
  const [tickerResults, setTickerResults] = useState(null)
  const [searchingTickers, setSearchingTickers] = useState(false)
  const tickerTimeout = useRef(null)

  const getConfig = (name) => ({
    ...DEFAULT_CONNECTOR_CONFIG,
    ...connectorConfigs[name],
  })

  const updateConnector = (name, patch) => {
    const updated = {
      ...config,
      connectors: {
        ...connectorConfigs,
        [name]: { ...getConfig(name), ...patch },
      },
    }
    onChange(updated)
  }

  const fetchRepos = async () => {
    setLoadingRepos(true)
    try {
      const resp = await fetch('/api/github/repos')
      const data = await resp.json()
      setAvailableRepos(data.repos || [])
    } catch {
      setAvailableRepos([])
    }
    setLoadingRepos(false)
  }

  const toggleRepo = (repoName) => {
    const cfg = getConfig('github')
    const current = (cfg.repos || '').split(',').map(r => r.trim()).filter(Boolean)
    const updated = current.includes(repoName)
      ? current.filter(r => r !== repoName)
      : [...current, repoName]
    updateConnector('github', { repos: updated.join(', ') })
  }

  const searchTickers = (query) => {
    setTickerQuery(query)
    if (tickerTimeout.current) clearTimeout(tickerTimeout.current)
    if (!query.trim()) { setTickerResults(null); return }
    setSearchingTickers(true)
    tickerTimeout.current = setTimeout(async () => {
      try {
        const resp = await fetch(`/api/yahoo/search?q=${encodeURIComponent(query.trim())}`)
        const data = await resp.json()
        setTickerResults(data.results || [])
      } catch {
        setTickerResults([])
      }
      setSearchingTickers(false)
    }, 400)
  }

  const addTicker = (symbol) => {
    const cfg = getConfig('yahoo_finance')
    const current = (cfg.symbols || '').split(',').map(s => s.trim().toUpperCase()).filter(Boolean)
    if (!current.includes(symbol.toUpperCase())) {
      const updated = [...current, symbol.toUpperCase()].join(', ')
      updateConnector('yahoo_finance', { symbols: updated })
    }
    setTickerQuery('')
    setTickerResults(null)
  }

  const removeTicker = (symbol) => {
    const cfg = getConfig('yahoo_finance')
    const current = (cfg.symbols || '').split(',').map(s => s.trim().toUpperCase()).filter(Boolean)
    const updated = current.filter(s => s !== symbol.toUpperCase()).join(', ')
    updateConnector('yahoo_finance', { symbols: updated })
  }

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] overflow-hidden">
      <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between">
        <h3 className="text-sm font-medium text-white">Briefing Settings</h3>
        <div className="flex items-center gap-2">
          {saved && (
            <span className="text-[11px] text-green-400 animate-fade-in">Saved</span>
          )}
          <button
            onClick={onSave}
            disabled={saving}
            className="text-[11px] font-medium px-3 py-1 rounded-lg bg-accent/20 text-accent-light
              hover:bg-accent/30 transition-all disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      <div className="divide-y divide-white/5">
        {connectedNames.map(name => {
          const meta = CONNECTOR_META[name] || { emoji: '\ud83d\udd27', label: name, color: '#7f56d9' }
          const cfg = getConfig(name)

          const spec = CONNECTOR_SPECIFIC_SETTINGS[name]

          return (
            <div key={name} className="px-4 py-3">
              {/* Row 1: Standard controls */}
              <div className="flex items-center gap-3">
                {/* Connector icon + name */}
                <div className="w-7 h-7 rounded-md flex items-center justify-center text-sm shrink-0"
                  style={{ background: meta.color + '18' }}>
                  {meta.emoji}
                </div>
                <span className="text-sm text-claw-200 w-24 shrink-0">{meta.label}</span>

                {/* Enabled toggle */}
                <button
                  onClick={() => updateConnector(name, { enabled: !cfg.enabled })}
                  className={`w-9 h-5 rounded-full transition-colors shrink-0 relative ${
                    cfg.enabled ? 'bg-accent/60' : 'bg-white/10'
                  }`}
                >
                  <div className={`w-3.5 h-3.5 rounded-full bg-white absolute top-[3px] transition-all ${
                    cfg.enabled ? 'left-[19px]' : 'left-[3px]'
                  }`} />
                </button>

                {/* Timeframe dropdown */}
                <select
                  value={cfg.timeframe}
                  onChange={e => updateConnector(name, { timeframe: e.target.value })}
                  disabled={!cfg.enabled}
                  className="bg-white/[0.06] border border-white/10 rounded-lg px-2 py-1 text-[11px] text-claw-200
                    focus:outline-none focus:border-accent/50 disabled:opacity-30 flex-1 min-w-0"
                >
                  {TIMEFRAME_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>

                {/* Max results */}
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className="text-[10px] text-claw-500">Max</span>
                  <input
                    type="number"
                    min={1}
                    max={50}
                    value={cfg.max_results}
                    onChange={e => updateConnector(name, { max_results: Math.max(1, Math.min(50, parseInt(e.target.value) || 10)) })}
                    disabled={!cfg.enabled}
                    className="w-12 bg-white/[0.06] border border-white/10 rounded-lg px-2 py-1 text-[11px] text-claw-200
                      text-center focus:outline-none focus:border-accent/50 disabled:opacity-30"
                  />
                </div>
              </div>

              {/* Row 2: Connector-specific settings */}
              {spec && cfg.enabled && name === 'yahoo_finance' && (
                <div className="mt-2 ml-10">
                  {/* Current watchlist as chips */}
                  {(cfg.symbols || '').split(',').filter(s => s.trim()).length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {(cfg.symbols || '').split(',').filter(s => s.trim()).map(s => (
                        <span key={s.trim()} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px]
                          font-medium bg-accent/15 text-accent-light border border-accent/20">
                          {s.trim().toUpperCase()}
                          <button onClick={() => removeTicker(s.trim())}
                            className="text-claw-500 hover:text-red-400 transition-colors ml-0.5">&times;</button>
                        </span>
                      ))}
                    </div>
                  )}
                  {/* Search input */}
                  <div className="relative">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-claw-500 w-16 shrink-0">Add stock</span>
                      <input
                        type="text"
                        value={tickerQuery}
                        onChange={e => searchTickers(e.target.value)}
                        placeholder="Search by name or ticker (e.g. Apple, TSLA, BTC)..."
                        className="flex-1 bg-white/[0.06] border border-white/10 rounded-lg px-2.5 py-1 text-[11px] text-claw-200
                          placeholder:text-claw-600 focus:outline-none focus:border-accent/50"
                      />
                      {searchingTickers && (
                        <span className="text-[10px] text-claw-500 shrink-0">Searching...</span>
                      )}
                    </div>
                    {/* Search results dropdown */}
                    {tickerResults && tickerResults.length > 0 && (
                      <div className="absolute left-0 right-0 top-full mt-1 z-10 bg-claw-800 border border-white/10
                        rounded-lg shadow-xl max-h-48 overflow-y-auto">
                        {tickerResults.map((r, i) => {
                          const already = (cfg.symbols || '').toUpperCase().split(',').map(s => s.trim()).includes(r.symbol)
                          return (
                            <button
                              key={i}
                              onClick={() => !already && addTicker(r.symbol)}
                              disabled={already}
                              className={`w-full px-3 py-2 flex items-center gap-3 text-left hover:bg-white/[0.06]
                                transition-colors border-b border-white/5 last:border-0
                                ${already ? 'opacity-40 cursor-not-allowed' : ''}`}
                            >
                              <span className="text-[11px] font-bold text-accent-light w-16 shrink-0">{r.symbol}</span>
                              <span className="text-[11px] text-claw-200 flex-1 truncate">{r.name}</span>
                              <span className="text-[10px] text-claw-500 shrink-0">{r.exchange}</span>
                              {already && <span className="text-[9px] text-claw-500">Added</span>}
                            </button>
                          )
                        })}
                      </div>
                    )}
                    {tickerResults && tickerResults.length === 0 && tickerQuery.trim() && (
                      <div className="absolute left-0 right-0 top-full mt-1 z-10 bg-claw-800 border border-white/10
                        rounded-lg shadow-xl px-3 py-2">
                        <span className="text-[11px] text-claw-500">No results found</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {spec && cfg.enabled && name !== 'yahoo_finance' && (
                <div className="mt-2 ml-10">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-claw-500 w-16 shrink-0">{spec.label}</span>
                    <input
                      type="text"
                      value={cfg[spec.key] || ''}
                      onChange={e => updateConnector(name, { [spec.key]: e.target.value })}
                      placeholder={spec.placeholder}
                      className="flex-1 bg-white/[0.06] border border-white/10 rounded-lg px-2.5 py-1 text-[11px] text-claw-200
                        placeholder:text-claw-600 focus:outline-none focus:border-accent/50"
                    />
                    {spec.fetchable && name === 'github' && (
                      <button
                        onClick={fetchRepos}
                        disabled={loadingRepos}
                        className="text-[10px] font-medium px-2 py-1 rounded-md bg-white/[0.06] text-claw-300
                          hover:bg-white/[0.1] hover:text-claw-100 transition-all disabled:opacity-50 shrink-0"
                      >
                        {loadingRepos ? 'Loading...' : 'Browse'}
                      </button>
                    )}
                    {!spec.fetchable && (
                      <span className="text-[10px] text-claw-600 shrink-0">{spec.help}</span>
                    )}
                  </div>

                  {/* GitHub repo picker */}
                  {name === 'github' && availableRepos && (
                    <div className="mt-2">
                      <div className="text-[10px] text-claw-500 mb-1">
                        {availableRepos.length} repo{availableRepos.length !== 1 ? 's' : ''} found
                        {(cfg.repos || '').split(',').filter(r => r.trim()).length > 0 && (
                          <span className="text-accent-light ml-2">
                            {(cfg.repos || '').split(',').filter(r => r.trim()).length} selected
                          </span>
                        )}
                      </div>
                    <div className="rounded-lg border border-white/5 bg-white/[0.02] max-h-56 overflow-y-auto">
                      {availableRepos.length === 0 && (
                        <div className="px-3 py-2 text-[11px] text-claw-500">No repos found — check your GitHub token permissions</div>
                      )}
                      {availableRepos.map(repo => {
                        const selected = (cfg.repos || '').split(',').map(r => r.trim()).includes(repo.name)
                        return (
                          <button
                            key={repo.name}
                            onClick={() => toggleRepo(repo.name)}
                            className={`w-full px-3 py-1.5 flex items-center gap-2 text-left hover:bg-white/[0.04] transition-colors ${
                              selected ? 'bg-accent/10' : ''
                            }`}
                          >
                            <span className={`w-3.5 h-3.5 rounded border flex items-center justify-center text-[9px] shrink-0 ${
                              selected ? 'bg-accent/60 border-accent/60 text-white' : 'border-white/20'
                            }`}>
                              {selected ? '\u2713' : ''}
                            </span>
                            <span className="text-[11px] text-claw-200 truncate">{repo.name}</span>
                            {repo.private && (
                              <span className="text-[9px] text-claw-600 ml-auto shrink-0">private</span>
                            )}
                          </button>
                        )
                      })}
                    </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {connectedNames.length === 0 && (
        <div className="px-4 py-6 text-center text-sm text-claw-500">
          No connectors connected yet. Set up services in the Connect tab first.
        </div>
      )}
    </div>
  )
}

function TaskCard({ task, onExecute }) {
  const meta = CONNECTOR_META[task.source] || { emoji: '\ud83d\udd27', label: task.source, color: '#7f56d9' }
  const priority = PRIORITY_STYLES[task.priority] || PRIORITY_STYLES.medium
  const followUps = task.follow_ups || []

  return (
    <div className={`rounded-xl border ${priority.border} bg-white/[0.02] p-4 hover:bg-white/[0.04] transition-all`}>
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-lg flex items-center justify-center text-base shrink-0"
          style={{ background: meta.color + '18' }}>
          {meta.emoji}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${priority.bg} ${priority.text}`}>
              {priority.label}
            </span>
            <span className="text-[10px] text-claw-500">{meta.label}</span>
          </div>
          <h3 className="text-sm font-medium text-white leading-snug">{task.title}</h3>
          <p className="text-xs text-claw-400 mt-1 leading-relaxed">{task.summary}</p>
          {followUps.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2.5">
              {followUps.map((fu, i) => (
                <button
                  key={i}
                  onClick={() => onExecute({ ...task, suggested_action: fu.prompt })}
                  className="px-2.5 py-1 rounded-lg text-[11px] font-medium
                    bg-white/[0.06] text-claw-200 hover:bg-accent/20 hover:text-accent-light
                    border border-white/[0.06] hover:border-accent/30 transition-all"
                >
                  {fu.label}
                </button>
              ))}
            </div>
          )}
        </div>
        {followUps.length === 0 && (
          <button
            onClick={() => onExecute(task)}
            className="shrink-0 px-3 py-1.5 rounded-lg text-xs font-medium bg-accent/20 text-accent-light
              hover:bg-accent/30 transition-all whitespace-nowrap"
          >
            Do it
          </button>
        )}
      </div>
    </div>
  )
}

function GatherProgress({ steps }) {
  return (
    <div className="space-y-2">
      {steps.map((step, i) => {
        const meta = CONNECTOR_META[step.connector] || { emoji: '\ud83d\udd27', label: step.connector }
        return (
          <div key={i} className="flex items-center gap-3 text-xs text-claw-300">
            <span className="text-base">{meta.emoji}</span>
            <span>{meta.label}</span>
            {step.count !== undefined && (
              <span className="text-claw-500">{step.count} item{step.count !== 1 ? 's' : ''}</span>
            )}
            <span className="text-green-400 ml-auto text-[10px]">\u2713</span>
          </div>
        )
      })}
    </div>
  )
}

export default function BriefingView({ onSwitchToChat }) {
  const [loading, setLoading] = useState(false)
  const [tasks, setTasks] = useState(null)
  const [gatherSteps, setGatherSteps] = useState([])
  const [thinkingText, setThinkingText] = useState('')
  const [error, setError] = useState(null)
  const [providers, setProviders] = useState([])
  const [provider, setProvider] = useState(null)
  const [briefingConfig, setBriefingConfig] = useState({ version: 1, connectors: {} })
  const [connectedNames, setConnectedNames] = useState([])
  const [showSettings, setShowSettings] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const abortRef = useRef(null)

  // Fetch providers, connected connectors, and saved config on mount
  useEffect(() => {
    fetch('/api/providers').then(r => r.json()).then(d => {
      setProviders(d.providers || [])
      if (d.providers?.length > 0) {
        setProvider(d.providers[0].id)
      }
    })

    fetch('/api/connectors').then(r => r.json()).then(d => {
      const names = (d.connectors || [])
        .filter(c => c.connected)
        .map(c => c.name)
      setConnectedNames(names)
    })

    fetch('/api/briefing/config').then(r => r.json()).then(d => {
      setBriefingConfig(d || { version: 1, connectors: {} })
    })
  }, [])

  const saveConfig = async () => {
    setSaving(true)
    setSaved(false)
    try {
      await fetch('/api/briefing/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(briefingConfig),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch {}
    setSaving(false)
  }

  const generateBriefing = useCallback(async () => {
    setLoading(true)
    setTasks(null)
    setGatherSteps([])
    setError(null)
    setThinkingText('Starting briefing...')

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const resp = await fetch('/api/briefing', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: provider || 'gemini',
          briefing_config: briefingConfig,
        }),
        signal: controller.signal,
      })

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))

            if (event.type === 'thinking') {
              setThinkingText(event.text)
            } else if (event.type === 'gather') {
              setGatherSteps(prev => [...prev, event])
            } else if (event.type === 'briefing') {
              setTasks(event.tasks || [])
            } else if (event.type === 'error') {
              setError(event.error)
            } else if (event.type === 'done') {
              setLoading(false)
            }
          } catch {}
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        setError(e.message)
      }
    } finally {
      setLoading(false)
    }
  }, [provider, briefingConfig])

  const handleExecute = (task) => {
    if (onSwitchToChat) {
      onSwitchToChat(task.suggested_action)
    }
  }

  const highCount = tasks?.filter(t => t.priority === 'high').length || 0
  const medCount = tasks?.filter(t => t.priority === 'medium').length || 0
  const lowCount = tasks?.filter(t => t.priority === 'low').length || 0

  return (
    <main className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-10">

        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-xl font-semibold text-white">Daily Briefing</h1>
            <p className="text-sm text-claw-400 mt-1">Your tasks across all connected services</p>
          </div>
          <div className="flex items-center gap-3">
            {/* Settings toggle */}
            <button
              onClick={() => setShowSettings(s => !s)}
              className={`p-2 rounded-lg transition-all border ${
                showSettings
                  ? 'bg-accent/20 border-accent/30 text-accent-light'
                  : 'bg-white/[0.04] border-white/10 text-claw-400 hover:text-claw-200'
              }`}
              title="Briefing settings"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>

            {providers?.length > 1 && (
              <select
                value={provider || ''}
                onChange={e => setProvider(e.target.value)}
                className="bg-white/[0.06] border border-white/10 rounded-lg px-3 py-2 text-xs text-claw-200
                  focus:outline-none focus:border-accent/50"
              >
                {providers.map(p => (
                  <option key={p.id} value={p.id}>{p.emoji} {p.label}</option>
                ))}
              </select>
            )}
            <button
              onClick={generateBriefing}
              disabled={loading}
              className="px-5 py-2.5 rounded-xl text-sm font-medium transition-all
                bg-accent/20 text-accent-light hover:bg-accent/30 border border-accent/20
                disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Generating...' : tasks ? 'Refresh' : 'Generate Briefing'}
            </button>
          </div>
        </div>

        {/* Settings panel */}
        {showSettings && (
          <div className="mb-6">
            <BriefingSettings
              connectedNames={connectedNames}
              config={briefingConfig}
              onChange={setBriefingConfig}
              onSave={saveConfig}
              saving={saving}
              saved={saved}
            />
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 text-sm text-claw-300">
              <div className="w-4 h-4 border-2 border-accent/40 border-t-accent-light rounded-full animate-spin" />
              {thinkingText}
            </div>
            {gatherSteps.length > 0 && (
              <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
                <GatherProgress steps={gatherSteps} />
              </div>
            )}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Empty state */}
        {tasks && tasks.length === 0 && !loading && (
          <div className="text-center py-16">
            <div className="text-4xl mb-3">&#x2728;</div>
            <h3 className="text-lg font-medium text-white mb-1">All clear</h3>
            <p className="text-sm text-claw-400">No pending tasks across your connected services.</p>
          </div>
        )}

        {/* Task list */}
        {tasks && tasks.length > 0 && !loading && (
          <div className="space-y-6">
            {/* Summary bar */}
            <div className="flex items-center gap-4 text-xs">
              <span className="text-claw-400">{tasks.length} task{tasks.length !== 1 ? 's' : ''}</span>
              {highCount > 0 && (
                <span className="text-red-400">{highCount} high priority</span>
              )}
              {medCount > 0 && (
                <span className="text-yellow-400">{medCount} medium</span>
              )}
              {lowCount > 0 && (
                <span className="text-green-400">{lowCount} low</span>
              )}
            </div>

            {/* Task cards */}
            <div className="space-y-3">
              {tasks.map((task, i) => (
                <TaskCard key={task.id || i} task={task} onExecute={handleExecute} />
              ))}
            </div>
          </div>
        )}

        {/* Initial state */}
        {!tasks && !loading && !error && (
          <div className="text-center py-16">
            <div className="text-4xl mb-3">&#x1F980;</div>
            <h3 className="text-lg font-medium text-white mb-2">Ready to brief you</h3>
            <p className="text-sm text-claw-400 mb-6 max-w-md mx-auto">
              Scans your email, GitHub, messages, and more — then builds a prioritized task list you can act on.
            </p>
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={() => setShowSettings(true)}
                className="px-5 py-3 rounded-xl text-sm font-medium transition-all
                  bg-white/[0.04] text-claw-300 hover:bg-white/[0.08] border border-white/10"
              >
                Configure
              </button>
              <button
                onClick={generateBriefing}
                className="px-6 py-3 rounded-xl text-sm font-medium transition-all
                  bg-accent/20 text-accent-light hover:bg-accent/30 border border-accent/20"
              >
                Generate Briefing
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  )
}
