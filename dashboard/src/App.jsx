import { useState, useEffect, useCallback, useRef } from 'react'
import ChatView from './ChatView'
import BriefingView from './BriefingView'
import VoiceView from './VoiceView'
import SetupWizard from './SetupWizard'

const CONNECTOR_META = {
  gmail: { emoji: '📧', label: 'Gmail', color: '#ea4335' },
  work_email: { emoji: '💼', label: 'Work Email', color: '#4285f4' },
  slack: { emoji: '💬', label: 'Slack', color: '#4A154B' },
  telegram: { emoji: '💬', label: 'Telegram', color: '#26a5e4' },
  github: { emoji: '🐙', label: 'GitHub', color: '#8b5cf6' },
  supabase: { emoji: '⚡', label: 'Supabase', color: '#3ecf8e' },
  firebase: { emoji: '🔥', label: 'Firebase', color: '#ffca28' },
  yahoo_finance: { emoji: '📈', label: 'Yahoo Finance', color: '#7b61ff' },
  whatsapp: { emoji: '💬', label: 'WhatsApp', color: '#25d366' },
}

const CONNECTOR_SETUP = {
  telegram: {
    title: 'Set up a Telegram Bot',
    time: '~1 min',
    steps: [
      { text: 'Open Telegram and message', link: { label: '@BotFather', url: 'https://t.me/BotFather' } },
      { text: 'Send /newbot and follow the prompts \u2014 copy the Bot Token' },
      { text: 'Message', link: { label: '@userinfobot', url: 'https://t.me/userinfobot' }, suffix: 'to get your Chat ID' },
      { text: 'Start a conversation with your bot (search for it and click "Start")' },
    ],
    tip: 'Bots can only message users who have started a conversation with them first.',
  },
  github: {
    title: 'Create a GitHub Personal Access Token',
    time: '~1 min',
    steps: [
      { text: 'Go to', link: { label: 'GitHub \u2192 Developer settings \u2192 Tokens (classic)', url: 'https://github.com/settings/tokens' } },
      { text: 'Click Generate new token (classic) \u2014 name it (e.g. "ClawFounder")' },
      { text: 'Select scopes: repo (required), notifications, workflow (optional)' },
      { text: 'Click Generate token and copy it immediately' },
    ],
    tip: 'The token is only shown once. If you lose it, generate a new one.',
  },
  slack: {
    title: 'Create a Slack Bot Token',
    time: '~2 min',
    steps: [
      { text: 'Click', link: { label: 'Create Slack App (pre-configured)', url: 'https://api.slack.com/apps?new_app=1&manifest_json=%7B%22display_information%22%3A%7B%22name%22%3A%22ClawFounder%22%2C%22description%22%3A%22AI%20PM%20assistant%22%7D%2C%22features%22%3A%7B%22bot_user%22%3A%7B%22display_name%22%3A%22ClawFounder%22%2C%22always_online%22%3Atrue%7D%7D%2C%22oauth_config%22%3A%7B%22scopes%22%3A%7B%22bot%22%3A%5B%22channels%3Aread%22%2C%22channels%3Ahistory%22%2C%22groups%3Aread%22%2C%22groups%3Ahistory%22%2C%22chat%3Awrite%22%2C%22chat%3Awrite.public%22%2C%22users%3Aread%22%2C%22im%3Aread%22%5D%2C%22user%22%3A%5B%22search%3Aread%22%5D%7D%7D%2C%22settings%22%3A%7B%22org_deploy_enabled%22%3Afalse%2C%22socket_mode_enabled%22%3Afalse%2C%22token_rotation_enabled%22%3Afalse%7D%7D' }, suffix: '\u2192 pick your workspace \u2192 Create' },
      { text: 'Click Install to Workspace and authorize' },
      { text: 'Go to OAuth & Permissions \u2192 copy the Bot User OAuth Token (starts with xoxb-)' },
    ],
    tip: 'The bot can only see channels it has been invited to. Use /invite @YourBot in each channel.',
  },
  whatsapp: {
    title: 'Set up WhatsApp Cloud API',
    time: '~10 min',
    steps: [
      { text: 'Go to', link: { label: 'Meta for Developers', url: 'https://developers.facebook.com/' }, suffix: '\u2192 Create App \u2192 Business type' },
      { text: 'Add the WhatsApp product \u2192 go to API Setup page' },
      { text: 'Copy your Phone Number ID (under "From")' },
      { text: 'For a permanent token: Business Settings \u2192', link: { label: 'System Users', url: 'https://business.facebook.com/settings/system-users' }, suffix: '\u2192 Add \u2192 Generate Token with whatsapp_business_messaging permission' },
      { text: 'Add test recipient numbers under API Setup \u2192 "To" \u2192 Manage phone number list' },
    ],
    tip: 'The test token on API Setup expires in 24h. Use a System User token for permanent access.',
  },
  supabase: {
    title: 'Get your Supabase project credentials',
    time: '~1 min',
    steps: [
      { text: 'Go to', link: { label: 'supabase.com/dashboard', url: 'https://supabase.com/dashboard' }, suffix: 'and open your project' },
      { text: 'Go to Project Settings \u2192 API' },
      { text: 'Copy the Project URL (starts with https://...supabase.co)' },
      { text: 'Copy the service_role key (under "Project API keys" \u2014 not the anon key)' },
    ],
    tip: 'Use the service_role key, not the anon key. The service_role key bypasses Row Level Security.',
  },
}

function ConnectorSetupGuide({ connectorName }) {
  const setup = CONNECTOR_SETUP[connectorName]
  if (!setup) return null

  return (
    <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl px-4 py-3 text-xs text-blue-300 space-y-1.5">
      <div className="font-semibold text-blue-200">{setup.title} ({setup.time})</div>
      <ol className="list-decimal ml-4 space-y-1">
        {setup.steps.map((step, i) => (
          <li key={i}>
            {step.link ? (
              <>{step.text}{' '}<a href={step.link.url} target="_blank" rel="noopener"
                className="underline hover:text-blue-100">{step.link.label}</a>{step.suffix ? ` ${step.suffix}` : ''}</>
            ) : step.text}
          </li>
        ))}
      </ol>
      {setup.tip && (
        <div className="text-[10px] text-blue-400 mt-1.5 italic">{setup.tip}</div>
      )}
    </div>
  )
}

const PROVIDER_KEYS = [
  { key: 'GEMINI_API_KEY', label: 'Google Gemini', emoji: '✨', vertexai: true },
  { key: 'OPENAI_API_KEY', label: 'OpenAI', emoji: '🤖' },
  { key: 'ANTHROPIC_API_KEY', label: 'Anthropic Claude', emoji: '🧠' },
]

const VERTEX_KEYS = [
  { key: 'GOOGLE_CLOUD_PROJECT', placeholder: 'your-project-id' },
  { key: 'GOOGLE_CLOUD_LOCATION', placeholder: 'us-central1' },
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
  const [mode, setMode] = useState('json') // 'json' or 'manual'
  const [jsonText, setJsonText] = useState('')
  const [clientId, setClientId] = useState('')
  const [clientSecret, setClientSecret] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)
  const fileInputRef = useRef(null)

  const handleJsonFile = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => setJsonText(ev.target.result)
    reader.readAsText(file)
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      let body
      if (mode === 'json') {
        if (!jsonText.trim()) {
          setError('Paste or upload the JSON credentials file.')
          setSaving(false)
          return
        }
        body = { json: jsonText.trim() }
      } else {
        if (!clientId.trim() || !clientSecret.trim()) {
          setError('Both Client ID and Client Secret are required.')
          setSaving(false)
          return
        }
        body = { client_id: clientId.trim(), client_secret: clientSecret.trim() }
      }

      const res = await fetch('/api/gmail/client-secret', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
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
            <li>Download the <strong>JSON</strong> file (or copy Client ID & Secret)</li>
          </ol>
        </div>

        {/* Mode toggle */}
        <div className="flex gap-1 p-0.5 rounded-lg bg-white/[0.04] border border-white/5 w-fit">
          <button onClick={() => setMode('json')}
            className={`px-3 py-1 rounded-md text-[11px] font-medium transition-all
              ${mode === 'json' ? 'bg-accent/20 text-accent-light' : 'text-claw-400 hover:text-claw-200'}`}>
            Upload JSON
          </button>
          <button onClick={() => setMode('manual')}
            className={`px-3 py-1 rounded-md text-[11px] font-medium transition-all
              ${mode === 'manual' ? 'bg-accent/20 text-accent-light' : 'text-claw-400 hover:text-claw-200'}`}>
            Enter Manually
          </button>
        </div>

        <div className="space-y-2">
          {mode === 'json' ? (
            <>
              <div className="flex gap-2">
                <button onClick={() => fileInputRef.current?.click()}
                  className="px-3 py-2 rounded-lg text-xs font-medium bg-white/[0.06] border border-white/10
                    text-claw-300 hover:bg-white/[0.10] hover:text-white transition-all">
                  Choose JSON file...
                </button>
                <input ref={fileInputRef} type="file" accept=".json,application/json"
                  onChange={handleJsonFile} className="hidden" />
                {jsonText && <span className="text-[10px] text-green-400 self-center">File loaded</span>}
              </div>
              <div className="text-[10px] text-claw-500">or paste the JSON contents:</div>
              <textarea
                value={jsonText}
                onChange={(e) => setJsonText(e.target.value)}
                placeholder='{"installed":{"client_id":"...","client_secret":"..."}}'
                rows={3}
                className="w-full px-3 py-2 rounded-lg bg-white/[0.06] border border-white/10 text-xs text-white font-mono
                  placeholder-claw-500 focus:outline-none focus:border-accent/50 resize-none"
              />
            </>
          ) : (
            <>
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
            </>
          )}
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

function AccountList({ connectorName, accounts, onRefresh, isEmailConnector = false }) {
  const [editingAcct, setEditingAcct] = useState(null)
  const [editValues, setEditValues] = useState({})
  const [editSaving, setEditSaving] = useState(false)
  const [editSaved, setEditSaved] = useState(false)

  if (!accounts || accounts.length === 0) return null

  const allEnabled = accounts.every(a => a.enabled)
  const someEnabled = accounts.some(a => a.enabled)

  const handleToggle = async (acctId, enabled) => {
    await fetch(`/api/accounts/${connectorName}/${acctId}/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    })
    onRefresh()
  }

  const handleToggleAll = async () => {
    const newEnabled = !allEnabled
    await fetch(`/api/accounts/${connectorName}/toggle-all`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: newEnabled }),
    })
    onRefresh()
  }

  const handleDisconnect = async (acctId) => {
    if (!confirm(`Disconnect account "${acctId}"?`)) return
    await fetch(`/api/accounts/${connectorName}/${acctId}/disconnect`, { method: 'POST' })
    onRefresh()
  }

  const handleRemove = async (acctId) => {
    if (!confirm(`Remove account "${acctId}"? This will delete its credentials permanently.`)) return
    await fetch(`/api/accounts/${connectorName}/${acctId}/remove`, { method: 'POST' })
    onRefresh()
  }

  const handleDisconnectAll = async () => {
    if (!confirm(`Disconnect ALL ${connectorName} accounts?`)) return
    await fetch(`/api/accounts/${connectorName}/disconnect-all`, { method: 'POST' })
    onRefresh()
  }

  const startEditing = (acct) => {
    setEditingAcct(acct.id)
    setEditValues({})
    setEditSaved(false)
  }

  const getEnvKeys = (acct) => {
    if (acct.env_key) return [acct.env_key]
    if (acct.env_keys) return Object.values(acct.env_keys)
    return []
  }

  const getEnvKeyLabels = (acct) => {
    if (acct.env_key) return { [acct.env_key]: acct.env_key }
    if (acct.env_keys) {
      const labels = {}
      for (const [base, actual] of Object.entries(acct.env_keys)) {
        labels[actual] = base
      }
      return labels
    }
    return {}
  }

  const handleEditSave = async (acct) => {
    const keys = getEnvKeys(acct)
    const updates = {}
    const suffix = acct.id ? `_${acct.id.toUpperCase().replace(/-/g, '_')}` : ''
    for (const key of keys) {
      if (editValues[key]) {
        updates[key] = editValues[key]
        // Also update the base env key when this is the only account
        // (e.g., GITHUB_TOKEN_PERSONAL → also update GITHUB_TOKEN)
        if (suffix && key.endsWith(suffix) && accounts.length === 1) {
          const baseKey = key.slice(0, -suffix.length)
          if (baseKey) updates[baseKey] = editValues[key]
        }
      }
    }
    if (Object.keys(updates).length === 0) return

    setEditSaving(true)
    try {
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      })
      setEditSaved(true)
      setTimeout(() => {
        setEditSaved(false)
        setEditingAcct(null)
        setEditValues({})
      }, 1500)
      onRefresh()
    } catch {}
    setEditSaving(false)
  }

  return (
    <div className="space-y-2">
      {/* Header with Select All */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={allEnabled}
            ref={el => { if (el) el.indeterminate = someEnabled && !allEnabled }}
            onChange={handleToggleAll}
            className="w-3.5 h-3.5 rounded border-white/20 bg-white/5 accent-accent cursor-pointer"
          />
          <span className="text-xs font-medium text-claw-300">Accounts</span>
          <span className="text-[10px] text-claw-500">({accounts.filter(a => a.enabled).length}/{accounts.length} active)</span>
        </div>
      </div>

      {/* Account rows */}
      {accounts.map(acct => {
        const isEditing = editingAcct === acct.id
        const envKeys = getEnvKeys(acct)
        const envLabels = getEnvKeyLabels(acct)
        const canEdit = !isEmailConnector && acct.connected && envKeys.length > 0

        return (
          <div key={acct.id} className={`rounded-lg border transition-all
            ${acct.connected ? 'border-white/5 bg-white/[0.02]' : 'border-white/5 bg-white/[0.01] opacity-60'}`}>
            <div className="flex items-center gap-3 px-3 py-2">
              <input
                type="checkbox"
                checked={acct.enabled}
                onChange={e => handleToggle(acct.id, e.target.checked)}
                className="w-3.5 h-3.5 rounded border-white/20 bg-white/5 accent-accent cursor-pointer"
              />
              <span className={`w-2 h-2 rounded-full flex-shrink-0 ${acct.connected ? 'bg-success' : 'bg-claw-600'}`} />
              <div className="flex-1 min-w-0">
                <div className="text-xs text-white truncate">{acct.label || acct.id}</div>
                {acct.id !== acct.label && (
                  <div className="text-[10px] text-claw-500 truncate">{acct.id}</div>
                )}
              </div>
              <div className="flex items-center gap-1 flex-shrink-0">
                {canEdit && (
                  <button onClick={() => isEditing ? setEditingAcct(null) : startEditing(acct)}
                    className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                      isEditing ? 'text-accent-light bg-accent/10' : 'text-claw-500 hover:text-claw-200'
                    }`}
                    title="Edit credentials">
                    Edit
                  </button>
                )}
                {acct.connected && (
                  <button onClick={() => handleDisconnect(acct.id)}
                    className="text-[10px] text-claw-500 hover:text-red-400 px-1.5 py-0.5 rounded transition-colors"
                    title="Disconnect">
                    Disconnect
                  </button>
                )}
                {acct.id !== 'default' && (
                  <button onClick={() => handleRemove(acct.id)}
                    className="text-[10px] text-claw-500 hover:text-red-400 px-1.5 py-0.5 rounded transition-colors"
                    title="Remove account">
                    Remove
                  </button>
                )}
              </div>
            </div>

            {/* Inline edit form */}
            {isEditing && (
              <div className="px-3 pb-3 pt-1 border-t border-white/5 space-y-2">
                {envKeys.map(key => (
                  <div key={key}>
                    <label className="text-[10px] text-claw-500 mb-1 block">
                      <code className="text-accent-light/70">{envLabels[key] || key}</code>
                    </label>
                    <input
                      type="password"
                      placeholder="Enter new value..."
                      value={editValues[key] ?? ''}
                      onChange={e => setEditValues(prev => ({ ...prev, [key]: e.target.value }))}
                      className="w-full bg-claw-900/60 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-claw-100
                        placeholder:text-claw-600 focus:outline-none focus:border-accent/40 transition-all"
                    />
                  </div>
                ))}
                <div className="flex items-center gap-2 pt-1">
                  <button
                    onClick={() => handleEditSave(acct)}
                    disabled={editSaving || Object.values(editValues).every(v => !v)}
                    className="px-3 py-1.5 rounded-lg text-[11px] font-medium bg-accent/20 text-accent-light
                      hover:bg-accent/30 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    {editSaving ? 'Saving...' : 'Update'}
                  </button>
                  <button
                    onClick={() => { setEditingAcct(null); setEditValues({}) }}
                    className="px-3 py-1.5 rounded-lg text-[11px] text-claw-400 hover:text-claw-200 transition-colors"
                  >
                    Cancel
                  </button>
                  {editSaved && (
                    <span className="text-[11px] text-green-400">Updated!</span>
                  )}
                </div>
              </div>
            )}
          </div>
        )
      })}

      {/* Disconnect All */}
      {accounts.filter(a => a.connected).length >= 2 && (
        <button onClick={handleDisconnectAll}
          className="w-full py-1.5 rounded-lg text-[10px] font-medium text-claw-500 hover:text-red-400
            bg-white/[0.02] hover:bg-red-500/5 border border-white/5 transition-all">
          Disconnect All
        </button>
      )}
    </div>
  )
}

function AddAccountButton({ connectorName, onAdded, isEmailConnector = false, envVars = [], startExpanded = false }) {
  const [showForm, setShowForm] = useState(startExpanded)
  const [label, setLabel] = useState('')
  const [envValues, setEnvValues] = useState({})
  const [error, setError] = useState(null)

  const handleAdd = async () => {
    if (!label.trim()) {
      setError('Name is required')
      return
    }
    // For env-var connectors, require at least the first env var value
    if (!isEmailConnector && envVars.length > 0) {
      const firstRequired = envVars.find(v => v.required)
      if (firstRequired && !envValues[firstRequired.key]?.trim()) {
        setError(`${firstRequired.key} is required`)
        return
      }
    }
    setError(null)
    const id = label.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
    try {
      const res = await fetch(`/api/accounts/${connectorName}/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, label: label.trim(), envValues }),
      })
      const data = await res.json()
      if (data.error) throw new Error(data.error)
      setLabel('')
      setEnvValues({})
      setShowForm(false)
      onAdded?.()
    } catch (e) {
      setError(e.message)
    }
  }

  if (!showForm) {
    return (
      <button onClick={() => setShowForm(true)}
        className="w-full py-2 rounded-lg text-xs font-medium text-claw-400 hover:text-accent-light
          bg-white/[0.02] hover:bg-accent/5 border border-dashed border-white/10 hover:border-accent/30 transition-all">
        + Add Account
      </button>
    )
  }

  return (
    <div className="space-y-2 p-3 rounded-lg border border-accent/20 bg-accent/[0.03]">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-white">Add Account</span>
      </div>
      <input
        type="text"
        placeholder={isEmailConnector ? "Name (e.g. work, personal2)" : "Name (e.g. work, staging)"}
        value={label}
        onChange={e => setLabel(e.target.value)}
        className="w-full px-3 py-1.5 rounded-lg bg-white/[0.06] border border-white/10 text-xs text-white
          placeholder-claw-500 focus:outline-none focus:border-accent/50"
      />
      {/* Env var credential fields for non-email connectors */}
      {!isEmailConnector && envVars.map(env => (
        <div key={env.key}>
          <label className="text-[10px] text-claw-400 mb-1 block">
            {env.description || env.key}
            {env.required && <span className="text-warning ml-1">*</span>}
          </label>
          <input
            type="password"
            placeholder={`Enter ${env.key}...`}
            value={envValues[env.key] || ''}
            onChange={e => setEnvValues(prev => ({ ...prev, [env.key]: e.target.value }))}
            className="w-full px-3 py-1.5 rounded-lg bg-white/[0.06] border border-white/10 text-xs text-white
              placeholder-claw-500 focus:outline-none focus:border-accent/50"
          />
        </div>
      ))}
      {error && <p className="text-[10px] text-red-400">{error}</p>}
      <div className="flex gap-2">
        <button onClick={handleAdd}
          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-accent/20 text-accent-light hover:bg-accent/30 transition-all">
          Add
        </button>
        <button onClick={() => { setShowForm(false); setError(null); setLabel(''); setEnvValues({}) }}
          className="px-3 py-1.5 rounded-lg text-xs font-medium text-claw-400 hover:text-claw-200 transition-all">
          Cancel
        </button>
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

  const popupRef = useRef(null)

  const writePopupLoading = (popup) => {
    try {
      popup.document.open()
      popup.document.write(`<html><head><title>Sign in — ${label}</title></head>
        <body style="background:#0f0f1a;color:#fff;font-family:system-ui,-apple-system,sans-serif;
          display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
        <div style="text-align:center">
          <div style="font-size:18px;margin-bottom:20px;opacity:0.9">Loading Google Sign-in...</div>
          <div style="width:32px;height:32px;border:3px solid #333;border-top-color:#4285F4;
            border-radius:50%;animation:s 1s linear infinite;margin:0 auto"></div>
        </div>
        <style>@keyframes s{to{transform:rotate(360deg)}}</style>
        </body></html>`)
      popup.document.close()
    } catch { /* cross-origin after navigation — expected */ }
  }

  const writePopupError = (popup, msg) => {
    try {
      popup.document.open()
      popup.document.write(`<html><head><title>Error — ${label}</title></head>
        <body style="background:#0f0f1a;color:#fff;font-family:system-ui,-apple-system,sans-serif;
          display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
        <div style="text-align:center;max-width:360px;padding:20px">
          <div style="font-size:18px;margin-bottom:12px;color:#f87171">Sign-in failed</div>
          <div style="font-size:14px;opacity:0.7;margin-bottom:20px">${msg}</div>
          <div style="font-size:13px;opacity:0.5">You can close this window.</div>
        </div></body></html>`)
      popup.document.close()
    } catch { /* cross-origin — just close */ popup.close() }
  }

  const handleLogin = async (accountId = 'default') => {
    setLoadingLogin(true)

    // Open popup immediately (synchronous, in click context) to avoid popup blocker
    // Only for personal Gmail — work email uses gcloud which opens its own browser
    const isPersonalGmail = !isWorkEmail
    let popup = null
    if (isPersonalGmail) {
      const w = 500, h = 700
      const left = Math.round(window.screenX + (window.outerWidth - w) / 2)
      const top = Math.round(window.screenY + (window.outerHeight - h) / 2)
      popup = window.open('', 'gmail_auth_' + accountId, `popup,width=${w},height=${h},left=${left},top=${top}`)
      if (popup) writePopupLoading(popup)
      popupRef.current = popup
    }

    try {
      const response = await fetch(`/api/${apiPath}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ accountId }),
      })
      const data = await response.json()

      // Navigate the already-open popup to the auth URL
      if (data.authUrl && popup && !popup.closed) {
        popup.location.href = data.authUrl
      } else if (data.authUrl && (!popup || popup.closed)) {
        // Popup was blocked or closed — try opening fresh
        popup = window.open(data.authUrl, 'gmail_auth_' + accountId)
        popupRef.current = popup
      } else if (popup && !popup.closed && !data.authUrl) {
        // No auth URL — show message in popup (don't just close it)
        const msg = data.message || data.error || 'Could not start login. Try again.'
        writePopupError(popup, msg)
        if (data.status === 'already_running') {
          // Still poll — an existing login might complete
        } else {
          setLoadingLogin(false)
          return
        }
      }

      // Poll for login completion + detect popup close
      stopPolling()
      pollRef.current = setInterval(async () => {
        // If popup was closed before login completed, cancel the login process
        if (popup && popup.closed) {
          const s = await fetchStatus()
          if (s.loggedIn || s.accounts?.some(a => a.id === accountId && a.connected)) {
            stopPolling()
            setLoadingLogin(false)
            onRefresh()
            setToast(`${label} connected!`)
            setTimeout(() => setToast(null), 3000)
          } else {
            stopPolling()
            setLoadingLogin(false)
            fetch(`/api/${apiPath}/login/cancel`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ accountId }),
            }).catch(() => {})
          }
          return
        }

        const s = await fetchStatus()
        if (s.loggedIn || s.accounts?.some(a => a.id === accountId && a.connected)) {
          stopPolling()
          setLoadingLogin(false)
          onRefresh()
          setToast(`${label} connected!`)
          setTimeout(() => setToast(null), 3000)
        }
      }, 2000)
      // Stop polling after 2 minutes
      timeoutRef.current = setTimeout(() => {
        stopPolling()
        setLoadingLogin(false)
        if (popup && !popup.closed) popup.close()
      }, 120000)
    } catch (err) {
      if (popup && !popup.closed) writePopupError(popup, err.message || 'Network error')
      setLoadingLogin(false)
    }
  }

  const isConnected = status?.loggedIn
  const accounts = status?.accounts || []
  const hasMultipleAccounts = accounts.length > 1
  const hasDisconnectedAccounts = accounts.some(a => !a.connected)

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
                {!status?.hasCalendarScopes && (
                  <p className="text-[11px] text-blue-400 mt-1">
                    📅 Re-authenticate to enable Google Calendar integration.
                  </p>
                )}
              </div>
            ) : (
              <button
                onClick={() => handleLogin()}
                disabled={loadingLogin || (!isWorkEmail && !status?.hasClientSecret)}
                className="ml-8 flex items-center gap-3 px-5 py-2.5 rounded-xl text-sm font-medium transition-all
                  bg-white/[0.08] hover:bg-white/[0.12] border border-white/10 hover:border-white/20
                  text-white disabled:opacity-50"
              >
                {loadingLogin ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Complete login in popup...
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

          {/* Account list (shown when multiple accounts or user clicked + Add) */}
          {(hasMultipleAccounts || accounts.length > 0) && (
            <div className="space-y-3 pt-2 border-t border-white/5">
              <AccountList
                connectorName={connectorName}
                accounts={accounts}
                onRefresh={() => { fetchStatus(); onRefresh() }}
                isEmailConnector={true}
              />

              {/* Sign in button for disconnected accounts */}
              {hasDisconnectedAccounts && accounts.filter(a => !a.connected).map(acct => (
                <button key={acct.id}
                  onClick={() => handleLogin(acct.id)}
                  disabled={loadingLogin}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-xs font-medium
                    bg-white/[0.06] hover:bg-white/[0.10] border border-white/10 text-white disabled:opacity-50 transition-all">
                  Sign in: {acct.label || acct.id}
                </button>
              ))}

              <AddAccountButton
                connectorName={connectorName}
                onAdded={() => { fetchStatus(); onRefresh() }}
                isEmailConnector={true}
              />
            </div>
          )}

          {/* Disconnect / Reset (only when single default account) */}
          {isConnected && !hasMultipleAccounts && (
            <button onClick={handleDisconnect}
              className="w-full mt-3 py-2 rounded-xl text-xs font-medium transition-all
                bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20">
              Disconnect {label}
            </button>
          )}
          {!isWorkEmail && !isConnected && status?.hasClientSecret && (
            <button onClick={async () => {
              if (!confirm('Reset OAuth credentials? You will need to re-enter your Client ID and Secret.')) return
              await fetch('/api/gmail/client-secret', { method: 'DELETE' })
              fetchStatus()
            }}
              className="w-full mt-2 py-2 rounded-xl text-[11px] font-medium transition-all
                bg-white/[0.04] text-claw-400 hover:bg-white/[0.08] border border-white/5 hover:text-claw-300">
              ↺ Reset OAuth credentials
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [tab, setTab] = useState('connect')
  const [chatPrefill, setChatPrefill] = useState(null)
  const [connectors, setConnectors] = useState([])
  const [config, setConfig] = useState({})
  const [isSetConfig, setIsSetConfig] = useState({})
  const [editValues, setEditValues] = useState({})
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState(null)
  const [expandedConnector, setExpandedConnector] = useState(null)
  const [showWizard, setShowWizard] = useState(false)

  const fetchAll = useCallback(async () => {
    const [cRes, cfgRes] = await Promise.all([
      fetch('/api/connectors'),
      fetch('/api/config'),
    ])
    const [cData, cfgData] = await Promise.all([cRes.json(), cfgRes.json()])
    setConnectors(cData.connectors)
    setConfig(cfgData.config)
    setIsSetConfig(cfgData.isSet || {})

    // Show setup wizard on first run (no LLM provider configured)
    const hasAnyProvider = PROVIDER_KEYS.some(p => cfgData.isSet?.[p.key])
    if (!hasAnyProvider && !sessionStorage.getItem('clawfounder_wizard_dismissed')) {
      setShowWizard(true)
    }
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
              onClick={() => setTab('briefing')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all
                ${tab === 'briefing'
                  ? 'bg-accent/20 text-accent-light shadow-sm'
                  : 'text-claw-400 hover:text-claw-200'}`}
            >
              <span>📋</span> Briefing
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
            <button
              onClick={() => setTab('voice')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all
                ${tab === 'voice'
                  ? 'bg-accent/20 text-accent-light shadow-sm'
                  : 'text-claw-400 hover:text-claw-200'}`}
            >
              <span>🎙️</span> Voice
            </button>
          </div>
        </div>
      </header>

      {/* Briefing Tab */}
      {tab === 'briefing' && (
        <BriefingView
          onSwitchToChat={(message) => {
            setChatPrefill(message)
            setTab('chat')
          }}
        />
      )}

      {/* Chat Tab */}
      {tab === 'chat' && <ChatView prefillMessage={chatPrefill} onPrefillConsumed={() => setChatPrefill(null)} />}

      {/* Voice Tab */}
      {tab === 'voice' && <VoiceView />}

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
                      {(hasValue(p.key) || (p.vertexai && hasValue('GOOGLE_CLOUD_PROJECT'))) && (
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
                    {p.vertexai && (
                      <div className="mt-3 pt-3 border-t border-white/5 space-y-2">
                        <div className="text-[11px] text-claw-400 font-medium">Vertex AI (optional — higher rate limits, uses Google Cloud credits)</div>
                        <ol className="text-[10px] text-claw-500 list-decimal ml-3 space-y-0.5 mb-1">
                          <li>Enable <a href="https://console.cloud.google.com/apis/library/aiplatform.googleapis.com" target="_blank" rel="noopener" className="underline hover:text-claw-300">Vertex AI API</a> in your Google Cloud project</li>
                          <li>Run <code className="bg-white/5 px-1 rounded">gcloud auth application-default login</code></li>
                          <li>Enter your Project ID below</li>
                        </ol>
                        {VERTEX_KEYS.map(v => (
                          <div key={v.key} className="flex gap-2">
                            <input
                              type="text"
                              placeholder={hasValue(v.key) ? config[v.key] : v.placeholder}
                              value={editValues[v.key] ?? ''}
                              onChange={e => setEditValues(prev => ({ ...prev, [v.key]: e.target.value }))}
                              className="flex-1 bg-claw-900/60 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-claw-100
                            placeholder:text-claw-500 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all"
                            />
                            <button
                              onClick={() => handleSave(v.key, editValues[v.key] || '')}
                              disabled={saving || !isEditing(v.key)}
                              className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all
                            bg-accent/20 text-accent-light hover:bg-accent/30
                            disabled:opacity-30 disabled:cursor-not-allowed"
                            >
                              Save
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
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
                          <ConnectorSetupGuide connectorName={connector.name} />
                          {connector.supportsMultiAccount ? (
                            /* Multi-account connectors: account-based flow */
                            <div className="space-y-3">
                              {(connector.accounts?.length > 0) && (
                                <AccountList
                                  connectorName={connector.name}
                                  accounts={connector.accounts || []}
                                  onRefresh={fetchAll}
                                />
                              )}
                              <AddAccountButton
                                connectorName={connector.name}
                                onAdded={fetchAll}
                                envVars={connector.envVars}
                                startExpanded={!connector.connected}
                              />
                            </div>
                          ) : connector.envVars.length === 0 ? (
                            <p className="text-sm text-claw-400">No configuration needed — just works!</p>
                          ) : (
                            /* Non-multi-account: raw env var inputs */
                            <>
                              {connector.envVars.map(env => (
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
                              ))}
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
                            </>
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

      {/* Setup Wizard overlay */}
      {showWizard && (
        <SetupWizard
          onComplete={() => { setShowWizard(false); setTab('chat'); fetchAll() }}
          onDismiss={() => { setShowWizard(false); sessionStorage.setItem('clawfounder_wizard_dismissed', 'true') }}
          connectors={connectors}
          isSetConfig={isSetConfig}
        />
      )}
    </div>
  )
}
