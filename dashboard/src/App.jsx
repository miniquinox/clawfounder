import { useState, useEffect, useCallback, useRef } from 'react'
import ChatView from './ChatView'

const CONNECTOR_META = {
  gmail: { emoji: '📧', label: 'Gmail', color: '#ea4335' },
  work_email: { emoji: '💼', label: 'Work Email', color: '#4285f4' },
  telegram: { emoji: '💬', label: 'Telegram', color: '#26a5e4' },
  github: { emoji: '🐙', label: 'GitHub', color: '#8b5cf6' },
  supabase: { emoji: '⚡', label: 'Supabase', color: '#3ecf8e' },
  firebase: { emoji: '🔥', label: 'Firebase', color: '#ffca28' },
  yahoo_finance: { emoji: '📈', label: 'Yahoo Finance', color: '#7b61ff' },
}

const PROVIDER_KEYS = [
  { key: 'GEMINI_API_KEY', label: 'Google Gemini', emoji: '✨' },
  { key: 'OPENAI_API_KEY', label: 'OpenAI', emoji: '🤖' },
  { key: 'ANTHROPIC_API_KEY', label: 'Anthropic Claude', emoji: '🧠' },
]

function FirebaseCard({ connector, onRefresh }) {
  const [status, setStatus] = useState(null)
  const [projects, setProjects] = useState([])
  const [loadingLogin, setLoadingLogin] = useState(false)
  const [loadingProjects, setLoadingProjects] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [toast, setToast] = useState(null)

  const meta = CONNECTOR_META.firebase

  const fetchStatus = useCallback(async () => {
    const res = await fetch('/api/firebase/status')
    const data = await res.json()
    setStatus(data)
    return data
  }, [])

  useEffect(() => { fetchStatus() }, [fetchStatus])

  const handleLogin = async () => {
    setLoadingLogin(true)
    try {
      await fetch('/api/firebase/login', { method: 'POST' })
      // Poll for login completion
      const pollInterval = setInterval(async () => {
        const s = await fetchStatus()
        if (s.loggedIn && !s.loginInProgress) {
          clearInterval(pollInterval)
          setLoadingLogin(false)
          // Auto-load projects
          handleLoadProjects()
        }
      }, 2000)
      // Stop polling after 2 minutes
      setTimeout(() => { clearInterval(pollInterval); setLoadingLogin(false) }, 120000)
    } catch {
      setLoadingLogin(false)
    }
  }

  const handleLoadProjects = async () => {
    setLoadingProjects(true)
    try {
      const res = await fetch('/api/firebase/projects')
      const data = await res.json()
      setProjects(data.projects || [])
    } catch {
      setProjects([])
    }
    setLoadingProjects(false)
  }

  const handleSelectProject = async (projectId) => {
    try {
      await fetch('/api/firebase/select-project', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ projectId }),
      })
      await fetchStatus()
      onRefresh()
      setToast('Firebase connected!')
      setTimeout(() => setToast(null), 3000)
    } catch {
      setToast('Failed to save project')
      setTimeout(() => setToast(null), 3000)
    }
  }

  const isConnected = status?.loggedIn && status?.projectId

  const handleDisconnect = async () => {
    if (!confirm('Disconnect Firebase? This will clear the project ID.')) return
    try {
      await fetch('/api/connector/firebase/disconnect', { method: 'POST' })
      await fetchStatus()
      onRefresh()
      setToast('Firebase disconnected')
      setTimeout(() => setToast(null), 3000)
    } catch {
      setToast('Failed to disconnect')
      setTimeout(() => setToast(null), 3000)
    }
  }

  return (
    <div className={`rounded-2xl border backdrop-blur-xl transition-all duration-300 overflow-hidden
      ${isConnected
        ? 'border-success/20 bg-success/[0.03]'
        : 'border-white/5 bg-white/[0.03] hover:border-white/10'
      } ${expanded ? 'ring-1 ring-accent/20' : ''}`}
    >
      {toast && (
        <div className="mx-5 mt-3 px-4 py-2 rounded-lg bg-success/15 border border-success/30 text-green-400 text-xs font-medium">
          {toast}
        </div>
      )}

      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-5 text-left cursor-pointer"
      >
        <div className="flex items-center gap-4">
          <div className="w-11 h-11 rounded-xl flex items-center justify-center text-xl"
            style={{ background: meta.color + '18' }}>
            {meta.emoji}
          </div>
          <div>
            <div className="font-medium text-white">{meta.label}</div>
            <div className="text-xs text-claw-400 mt-0.5">
              {status?.email ? `Logged in as ${status.email}` : 'Login with Google'}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-xs font-medium px-3 py-1 rounded-full
            ${isConnected ? 'bg-success/15 text-green-400' : 'bg-claw-600/50 text-claw-400'}`}>
            {isConnected ? 'Connected' : 'Not connected'}
          </span>
          <svg className={`w-4 h-4 text-claw-400 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-5 pb-5 space-y-4 border-t border-white/5 pt-4">
          {/* Step 1: Google Login */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className={`w-6 h-6 rounded-full text-[11px] font-bold flex items-center justify-center
                ${status?.loggedIn ? 'bg-success/20 text-green-400' : 'bg-accent/20 text-accent-light'}`}>
                {status?.loggedIn ? '✓' : '1'}
              </span>
              <span className="text-sm font-medium text-white">Sign in with Google</span>
            </div>

            {status?.loggedIn ? (
              <div className="flex items-center gap-2 ml-8 text-xs text-claw-300">
                <span className="w-2 h-2 rounded-full bg-success" />
                {status.email}
              </div>
            ) : (
              <button
                onClick={handleLogin}
                disabled={loadingLogin}
                className="ml-8 flex items-center gap-3 px-5 py-2.5 rounded-xl text-sm font-medium transition-all
                  bg-white/[0.08] hover:bg-white/[0.12] border border-white/10 hover:border-white/20
                  text-white disabled:opacity-50"
              >
                {loadingLogin ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Complete login in browser...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" viewBox="0 0 24 24">
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                    </svg>
                    Login with Google
                  </>
                )}
              </button>
            )}
          </div>

          {/* Step 2: Select Project */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className={`w-6 h-6 rounded-full text-[11px] font-bold flex items-center justify-center
                ${status?.projectId ? 'bg-success/20 text-green-400' : 'bg-accent/20 text-accent-light'}`}>
                {status?.projectId ? '✓' : '2'}
              </span>
              <span className="text-sm font-medium text-white">Select project</span>
            </div>

            {status?.projectId ? (
              <div className="flex items-center gap-2 ml-8">
                <span className="text-xs text-claw-300">
                  <code className="text-accent-light bg-accent/10 px-1.5 py-0.5 rounded">{status.projectId}</code>
                </span>
                <button
                  onClick={() => { handleLoadProjects(); }}
                  className="text-xs text-claw-500 hover:text-claw-300 transition-colors underline ml-2"
                >
                  Change
                </button>
              </div>
            ) : !status?.loggedIn ? (
              <p className="ml-8 text-xs text-claw-500">Login first to see your projects</p>
            ) : (
              <div className="ml-8">
                {projects.length === 0 ? (
                  <button
                    onClick={handleLoadProjects}
                    disabled={loadingProjects}
                    className="px-4 py-2 rounded-lg text-sm font-medium transition-all
                      bg-accent/20 text-accent-light hover:bg-accent/30 
                      disabled:opacity-50"
                  >
                    {loadingProjects ? (
                      <span className="flex items-center gap-2">
                        <span className="w-3 h-3 border-2 border-accent-light/30 border-t-accent-light rounded-full animate-spin" />
                        Loading projects...
                      </span>
                    ) : 'Load Projects'}
                  </button>
                ) : (
                  <div className="space-y-2">
                    <div className="grid grid-cols-1 gap-1.5 max-h-48 overflow-y-auto pr-1">
                      {projects.map(p => (
                        <button
                          key={p.id}
                          onClick={() => handleSelectProject(p.id)}
                          className="flex items-center justify-between px-3 py-2 rounded-lg text-left text-sm
                            bg-claw-900/60 border border-white/5 hover:border-accent/30 hover:bg-accent/5
                            transition-all group"
                        >
                          <div>
                            <div className="text-claw-100 text-xs font-medium">{p.name}</div>
                            <div className="text-claw-500 text-[10px]">{p.id}</div>
                          </div>
                          <span className="text-[10px] text-accent-light opacity-0 group-hover:opacity-100 transition-opacity">
                            Select →
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Disconnect */}
          {isConnected && (
            <button onClick={handleDisconnect}
              className="w-full mt-3 py-2 rounded-xl text-xs font-medium transition-all
                bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20">
              Disconnect Firebase
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function GmailClientSetup({ onSaved }) {
  const [clientId, setClientId] = useState('')
  const [clientSecret, setClientSecret] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)

  const handleSave = async () => {
    if (!clientId.trim() || !clientSecret.trim()) {
      setError('Both Client ID and Client Secret are required.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const res = await fetch('/api/gmail/client-secret', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client_id: clientId.trim(), client_secret: clientSecret.trim() }),
      })
      const data = await res.json()
      if (data.error) throw new Error(data.error)
      setDone(true)
      onSaved?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  if (done) {
    return (
      <div className="bg-success/10 border border-success/20 rounded-xl px-4 py-3 text-xs text-green-400 flex items-center gap-2">
        <span className="w-5 h-5 rounded-full bg-success/20 text-green-400 flex items-center justify-center text-[10px] font-bold">✓</span>
        OAuth credentials saved. Click "Sign in with Google" below.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="w-6 h-6 rounded-full text-[11px] font-bold flex items-center justify-center bg-accent/20 text-accent-light">1</span>
        <span className="text-sm font-medium text-white">Set up OAuth credentials</span>
        <span className="text-[10px] text-claw-500 font-medium">(one-time)</span>
      </div>

      <div className="ml-8 space-y-3">
        <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl px-4 py-3 text-xs text-blue-300 space-y-1.5">
          <div className="font-semibold text-blue-200">Create a Google OAuth App (~2 min)</div>
          <ol className="list-decimal ml-4 space-y-1">
            <li>Go to <a href="https://console.cloud.google.com/apis/credentials/consent" target="_blank" rel="noopener"
              className="underline hover:text-blue-100">console.cloud.google.com → OAuth consent screen</a></li>
            <li>Choose <strong>External</strong> → Create → Fill in app name (e.g. "ClawFounder") and your email</li>
            <li>Add scopes: <code className="bg-white/10 px-1 rounded">gmail.readonly</code> and <code className="bg-white/10 px-1 rounded">gmail.send</code></li>
            <li>Under "Test users", add <strong>your personal Gmail address</strong></li>
            <li>Go to <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener"
              className="underline hover:text-blue-100">Credentials</a> → Create → <strong>OAuth 2.0 Client ID</strong> → <strong>Desktop app</strong></li>
            <li>Copy the <strong>Client ID</strong> and <strong>Client Secret</strong> below</li>
          </ol>
        </div>

        <div className="space-y-2">
          <input
            type="text"
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            placeholder="Client ID (e.g. 12345...apps.googleusercontent.com)"
            className="w-full px-3 py-2 rounded-lg bg-white/[0.06] border border-white/10 text-xs text-white
              placeholder-claw-500 focus:outline-none focus:border-accent/50"
          />
          <input
            type="password"
            value={clientSecret}
            onChange={(e) => setClientSecret(e.target.value)}
            placeholder="Client Secret"
            className="w-full px-3 py-2 rounded-lg bg-white/[0.06] border border-white/10 text-xs text-white
              placeholder-claw-500 focus:outline-none focus:border-accent/50"
          />
          {error && <p className="text-xs text-red-400">{error}</p>}
          <button onClick={handleSave} disabled={saving}
            className="px-4 py-2 rounded-lg text-xs font-medium transition-all
              bg-accent/20 text-accent-light hover:bg-accent/30 disabled:opacity-50">
            {saving ? 'Saving...' : 'Save Credentials'}
          </button>
        </div>
      </div>
    </div>
  )
}

function EmailCard({ connector, onRefresh, connectorName = 'gmail' }) {
  const [status, setStatus] = useState(null)
  const [loadingLogin, setLoadingLogin] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [toast, setToast] = useState(null)
  const pollRef = useRef(null)
  const timeoutRef = useRef(null)

  const meta = CONNECTOR_META[connectorName]
  const apiPath = connectorName.replace('_', '-') // gmail or work-email
  const label = connectorName === 'gmail' ? 'Gmail' : 'Work Email'
  const isWorkEmail = connectorName === 'work_email'

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null }
  }, [])

  // Clean up polling on unmount
  useEffect(() => () => stopPolling(), [stopPolling])

  const fetchStatus = useCallback(async () => {
    const res = await fetch(`/api/${apiPath}/status`)
    const data = await res.json()
    setStatus(data)
    return data
  }, [apiPath])

  useEffect(() => { fetchStatus() }, [fetchStatus])

  const handleLogin = async () => {
    setLoadingLogin(true)
    try {
      await fetch(`/api/${apiPath}/login`, { method: 'POST' })

      // Poll for login completion (gcloud opens browser itself)
      stopPolling()
      pollRef.current = setInterval(async () => {
        const s = await fetchStatus()
        if (s.loggedIn) {
          stopPolling()
          setLoadingLogin(false)
          onRefresh()
          setToast(`${label} connected!`)
          setTimeout(() => setToast(null), 3000)
        }
      }, 2000)
      // Stop polling after 2 minutes
      timeoutRef.current = setTimeout(() => { stopPolling(); setLoadingLogin(false) }, 120000)
    } catch {
      setLoadingLogin(false)
    }
  }

  const isConnected = status?.loggedIn

  const handleDisconnect = async () => {
    if (!confirm(`Disconnect ${label}? This will remove the token.`)) return
    try {
      await fetch(`/api/connector/${connectorName}/disconnect`, { method: 'POST' })
      await fetchStatus()
      onRefresh()
      setToast(`${label} disconnected`)
      setTimeout(() => setToast(null), 3000)
    } catch {
      setToast('Failed to disconnect')
      setTimeout(() => setToast(null), 3000)
    }
  }

  return (
    <div className={`rounded-2xl border backdrop-blur-xl transition-all duration-300 overflow-hidden
      ${isConnected
        ? 'border-success/20 bg-success/[0.03]'
        : 'border-white/5 bg-white/[0.03] hover:border-white/10'
      } ${expanded ? 'ring-1 ring-accent/20' : ''}`}
    >
      {toast && (
        <div className={`mx-5 mt-3 px-4 py-2 rounded-lg text-xs font-medium
          ${toast.includes('connected!')
            ? 'bg-success/15 border border-success/30 text-green-400'
            : 'bg-danger/15 border border-danger/30 text-red-400'}`}>
          {toast}
        </div>
      )}

      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-5 text-left cursor-pointer"
      >
        <div className="flex items-center gap-4">
          <div className="w-11 h-11 rounded-xl flex items-center justify-center text-xl"
            style={{ background: meta.color + '18' }}>
            {meta.emoji}
          </div>
          <div>
            <div className="font-medium text-white">{meta.label}</div>
            <div className="text-xs text-claw-400 mt-0.5">
              {status?.email ? `Signed in as ${status.email}` : 'Sign in with Google'}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-xs font-medium px-3 py-1 rounded-full
            ${isConnected ? 'bg-success/15 text-green-400' : 'bg-claw-600/50 text-claw-400'}`}>
            {isConnected ? 'Connected' : 'Not connected'}
          </span>
          <svg className={`w-4 h-4 text-claw-400 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-5 pb-5 space-y-4 border-t border-white/5 pt-4">

          {/* Workspace admin notice (work email only) */}
          {isWorkEmail && !isConnected && (
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl px-4 py-3 text-xs text-amber-300 space-y-1.5">
              <div className="font-semibold text-amber-200">⚠ Google Workspace Admin Required (one-time)</div>
              <ol className="list-decimal ml-4 space-y-0.5">
                <li>Go to <a href="https://admin.google.com/ac/owl/list?tab=configuredApps" target="_blank" rel="noopener"
                  className="underline hover:text-amber-100">admin.google.com → API Controls</a></li>
                <li>Click <strong>"Configure New App"</strong></li>
                <li>Search <strong>"Google Auth Library"</strong></li>
                <li>Allow for <strong>all company users</strong> → Choose <strong>Trusted</strong></li>
              </ol>
            </div>
          )}

          {/* Personal Gmail: OAuth client setup (Step 1) */}
          {!isWorkEmail && !isConnected && !status?.hasClientSecret && (
            <GmailClientSetup onSaved={() => fetchStatus()} />
          )}

          {/* Step 2: Sign in button */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className={`w-6 h-6 rounded-full text-[11px] font-bold flex items-center justify-center
                ${isConnected ? 'bg-success/20 text-green-400' : 'bg-accent/20 text-accent-light'}`}>
                {isConnected ? '\u2713' : (!isWorkEmail && !status?.hasClientSecret ? '2' : '1')}
              </span>
              <span className="text-sm font-medium text-white">Sign in with Google</span>
            </div>

            {isConnected ? (
              <div className="ml-8 space-y-2">
                <div className="flex items-center gap-2 text-xs text-claw-300">
                  <span className="w-2 h-2 rounded-full bg-success" />
                  {status.email || 'Authenticated'}
                </div>
                <p className="text-[11px] text-claw-500">
                  {isWorkEmail
                    ? 'Access your work email. Credentials saved locally.'
                    : 'Read, search, and send emails. Token saved locally.'
                  }
                </p>
              </div>
            ) : (
              <button
                onClick={handleLogin}
                disabled={loadingLogin || (!isWorkEmail && !status?.hasClientSecret)}
                className="ml-8 flex items-center gap-3 px-5 py-2.5 rounded-xl text-sm font-medium transition-all
                  bg-white/[0.08] hover:bg-white/[0.12] border border-white/10 hover:border-white/20
                  text-white disabled:opacity-50"
              >
                {loadingLogin ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Complete login in browser...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" viewBox="0 0 24 24">
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                    </svg>
                    Sign in with Google
                  </>
                )}
              </button>
            )}
          </div>

          {/* Disconnect */}
          {isConnected && (
            <button onClick={handleDisconnect}
              className="w-full mt-3 py-2 rounded-xl text-xs font-medium transition-all
                bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20">
              Disconnect {label}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [tab, setTab] = useState('connect')
  const [connectors, setConnectors] = useState([])
  const [config, setConfig] = useState({})
  const [isSetConfig, setIsSetConfig] = useState({})
  const [editValues, setEditValues] = useState({})
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState(null)
  const [expandedConnector, setExpandedConnector] = useState(null)

  const fetchAll = useCallback(async () => {
    const [cRes, cfgRes] = await Promise.all([
      fetch('/api/connectors'),
      fetch('/api/config'),
    ])
    const [cData, cfgData] = await Promise.all([cRes.json(), cfgRes.json()])
    setConnectors(cData.connectors)
    setConfig(cfgData.config)
    setIsSetConfig(cfgData.isSet || {})
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const handleSave = async (key, value) => {
    setSaving(true)
    try {
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates: { [key]: value } }),
      })
      await fetchAll()
      setEditValues(prev => ({ ...prev, [key]: undefined }))
      showToast(`${key} saved!`)
    } catch {
      showToast('Failed to save', 'error')
    }
    setSaving(false)
  }

  const handleSaveAll = async (keys) => {
    setSaving(true)
    const updates = {}
    for (const k of keys) {
      if (editValues[k] !== undefined) updates[k] = editValues[k]
    }
    if (Object.keys(updates).length === 0) {
      showToast('Nothing to save', 'info')
      setSaving(false)
      return
    }
    try {
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates }),
      })
      await fetchAll()
      setEditValues({})
      showToast('All keys saved!')
    } catch {
      showToast('Failed to save', 'error')
    }
    setSaving(false)
  }

  const hasValue = (key) => !!isSetConfig[key]
  const isEditing = (key) => editValues[key] !== undefined

  return (
    <div className="h-screen flex flex-col relative overflow-hidden">
      {/* Background */}
      <div className="fixed inset-0 bg-gradient-to-br from-claw-900 via-claw-800 to-claw-900 -z-20" />
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-accent/5 rounded-full blur-[120px] -z-10" />
      <div className="fixed bottom-0 right-0 w-[400px] h-[400px] bg-purple-600/5 rounded-full blur-[100px] -z-10" />

      {/* Toast */}
      {toast && (
        <div className={`fixed top-6 right-6 z-50 px-5 py-3 rounded-xl text-sm font-medium shadow-lg backdrop-blur-xl transition-all
          ${toast.type === 'error' ? 'bg-danger/20 border border-danger/30 text-red-300' :
            toast.type === 'info' ? 'bg-accent/20 border border-accent/30 text-accent-light' :
              'bg-success/20 border border-success/30 text-green-300'}`}>
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <header className="border-b border-white/5 backdrop-blur-xl bg-claw-900/50 flex-shrink-0">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center gap-4">
          <span className="text-3xl">🦀</span>
          <div className="flex-1">
            <h1 className="text-xl font-bold tracking-tight text-white">ClawFounder</h1>
          </div>

          {/* Tabs */}
          <div className="flex bg-white/[0.04] rounded-xl p-1 border border-white/5">
            <button
              onClick={() => setTab('connect')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all
                ${tab === 'connect'
                  ? 'bg-accent/20 text-accent-light shadow-sm'
                  : 'text-claw-400 hover:text-claw-200'}`}
            >
              <span>⚙️</span> Connect
            </button>
            <button
              onClick={() => setTab('chat')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all
                ${tab === 'chat'
                  ? 'bg-accent/20 text-accent-light shadow-sm'
                  : 'text-claw-400 hover:text-claw-200'}`}
            >
              <span>💬</span> Chat
            </button>
          </div>
        </div>
      </header>

      {/* Chat Tab */}
      {tab === 'chat' && <ChatView />}

      {/* Connect Tab */}
      {tab === 'connect' && (
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-5xl mx-auto px-6 py-10 space-y-10">
            {/* LLM Providers */}
            <section>
              <div className="flex items-center gap-3 mb-5">
                <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center text-sm">🧠</div>
                <h2 className="text-lg font-semibold text-white">LLM Providers</h2>
                <span className="text-xs text-claw-400 ml-1">Pick at least one</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {PROVIDER_KEYS.map(p => (
                  <div key={p.key} className="group rounded-2xl border border-white/5 bg-white/[0.03] backdrop-blur-xl p-5
                hover:border-accent/20 hover:bg-white/[0.05] transition-all duration-300">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <span className="text-xl">{p.emoji}</span>
                        <span className="font-medium text-white text-sm">{p.label}</span>
                      </div>
                      {hasValue(p.key) && (
                        <span className="w-2.5 h-2.5 rounded-full bg-success shadow-[0_0_8px_rgba(34,197,94,0.5)]" />
                      )}
                    </div>
                    <div className="flex gap-2">
                      <input
                        type="password"
                        placeholder={hasValue(p.key) ? config[p.key] : 'Enter API key...'}
                        value={editValues[p.key] ?? ''}
                        onChange={e => setEditValues(prev => ({ ...prev, [p.key]: e.target.value }))}
                        className="flex-1 bg-claw-900/60 border border-white/10 rounded-lg px-3 py-2 text-sm text-claw-100
                      placeholder:text-claw-500 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all"
                      />
                      <button
                        onClick={() => handleSave(p.key, editValues[p.key] || '')}
                        disabled={saving || !isEditing(p.key)}
                        className="px-4 py-2 rounded-lg text-sm font-medium transition-all
                      bg-accent/20 text-accent-light hover:bg-accent/30 
                      disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        Save
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* Connectors */}
            <section>
              <div className="flex items-center gap-3 mb-5">
                <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center text-sm">🔌</div>
                <h2 className="text-lg font-semibold text-white">Connectors</h2>
                <span className="text-xs text-claw-400 ml-1">{connectors.filter(c => c.connected).length}/{connectors.length} connected</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {connectors.map(connector => {
                  // Firebase gets its own special card
                  if (connector.name === 'firebase') {
                    return <FirebaseCard key="firebase" connector={connector} onRefresh={fetchAll} />
                  }

                  // Gmail and Work Email get the shared EmailCard
                  if (connector.name === 'gmail' || connector.name === 'work_email') {
                    return <EmailCard key={connector.name} connector={connector} onRefresh={fetchAll} connectorName={connector.name} />
                  }

                  const meta = CONNECTOR_META[connector.name] || { emoji: '🔗', label: connector.name, color: '#7f56d9' }
                  const isExpanded = expandedConnector === connector.name

                  return (
                    <div key={connector.name}
                      className={`rounded-2xl border backdrop-blur-xl transition-all duration-300 overflow-hidden
                    ${connector.connected
                          ? 'border-success/20 bg-success/[0.03]'
                          : 'border-white/5 bg-white/[0.03] hover:border-white/10'
                        } ${isExpanded ? 'ring-1 ring-accent/20' : ''}`}>

                      <button onClick={() => setExpandedConnector(isExpanded ? null : connector.name)}
                        className="w-full flex items-center justify-between p-5 text-left cursor-pointer">
                        <div className="flex items-center gap-4">
                          <div className="w-11 h-11 rounded-xl flex items-center justify-center text-xl"
                            style={{ background: meta.color + '18' }}>
                            {meta.emoji}
                          </div>
                          <div>
                            <div className="font-medium text-white">{meta.label}</div>
                            <div className="text-xs text-claw-400 mt-0.5">
                              {connector.envVars.length} env var{connector.envVars.length !== 1 ? 's' : ''}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className={`text-xs font-medium px-3 py-1 rounded-full
                        ${connector.connected ? 'bg-success/15 text-green-400' : 'bg-claw-600/50 text-claw-400'}`}>
                            {connector.connected ? 'Connected' : 'Not connected'}
                          </span>
                          <svg className={`w-4 h-4 text-claw-400 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
                            fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </div>
                      </button>

                      {isExpanded && (
                        <div className="px-5 pb-5 space-y-3 border-t border-white/5 pt-4">
                          {connector.envVars.length === 0 ? (
                            <p className="text-sm text-claw-400">No configuration needed — just works! 🎉</p>
                          ) : (
                            connector.envVars.map(env => (
                              <div key={env.key}>
                                <label className="flex items-center gap-2 text-xs font-medium text-claw-300 mb-1.5">
                                  <code className="text-accent-light bg-accent/10 px-1.5 py-0.5 rounded">{env.key}</code>
                                  {env.required && <span className="text-warning text-[10px]">REQUIRED</span>}
                                </label>
                                <p className="text-xs text-claw-500 mb-2">{env.description}</p>
                                <div className="flex gap-2">
                                  <input
                                    type="password"
                                    placeholder={hasValue(env.key) ? config[env.key] : 'Enter value...'}
                                    value={editValues[env.key] ?? ''}
                                    onChange={e => setEditValues(prev => ({ ...prev, [env.key]: e.target.value }))}
                                    className="flex-1 bg-claw-900/60 border border-white/10 rounded-lg px-3 py-2 text-sm text-claw-100
                                  placeholder:text-claw-500 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all"
                                  />
                                  <button
                                    onClick={() => handleSave(env.key, editValues[env.key] || '')}
                                    disabled={saving || !isEditing(env.key)}
                                    className="px-4 py-2 rounded-lg text-sm font-medium transition-all
                                  bg-accent/20 text-accent-light hover:bg-accent/30 
                                  disabled:opacity-30 disabled:cursor-not-allowed"
                                  >
                                    Save
                                  </button>
                                </div>
                              </div>
                            ))
                          )}

                          {connector.envVars.length > 1 && (
                            <button
                              onClick={() => handleSaveAll(connector.envVars.map(v => v.key))}
                              disabled={saving}
                              className="w-full mt-2 py-2.5 rounded-xl text-sm font-medium transition-all
                            bg-accent/15 text-accent-light hover:bg-accent/25 border border-accent/20
                            disabled:opacity-30 disabled:cursor-not-allowed"
                            >
                              Save All
                            </button>
                          )}

                          {/* Disconnect */}
                          {connector.connected && (
                            <button
                              onClick={async () => {
                                if (!confirm(`Disconnect ${CONNECTOR_META[connector.name]?.label || connector.name}? This will clear all keys.`)) return
                                try {
                                  await fetch(`/api/connector/${connector.name}/disconnect`, { method: 'POST' })
                                  await fetchAll()
                                  showToast(`${connector.name} disconnected`)
                                } catch {
                                  showToast('Failed to disconnect', 'error')
                                }
                              }}
                              className="w-full mt-1 py-2 rounded-xl text-xs font-medium transition-all
                                bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20"
                            >
                              Disconnect
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </section>

            {/* Footer */}
            <div className="text-center text-xs text-claw-500 pb-8">
              Keys are saved to your local <code className="text-claw-400 bg-claw-700/50 px-1.5 py-0.5 rounded">.env</code> file.
              Nothing leaves your machine.
            </div>
          </div>
        </main>
      )}
    </div>
  )
}
