import { useState, useCallback } from 'react'

const CONNECTOR_META = {
  gmail: { emoji: '📧', label: 'Gmail', color: '#ea4335' },
  work_email: { emoji: '💼', label: 'Work Email', color: '#4285f4' },
  telegram: { emoji: '💬', label: 'Telegram', color: '#26a5e4' },
  github: { emoji: '🐙', label: 'GitHub', color: '#8b5cf6' },
  supabase: { emoji: '⚡', label: 'Supabase', color: '#3ecf8e' },
  firebase: { emoji: '🔥', label: 'Firebase', color: '#ffca28' },
  yahoo_finance: { emoji: '📈', label: 'Yahoo Finance', color: '#7b61ff' },
  whatsapp: { emoji: '💬', label: 'WhatsApp', color: '#25d366' },
}

const PROVIDERS = [
  {
    key: 'GEMINI_API_KEY',
    label: 'Google Gemini',
    emoji: '✨',
    recommended: true,
    description: 'Powers Chat and Voice mode. Get a free API key from AI Studio.',
    link: 'https://aistudio.google.com/apikey',
    linkLabel: 'Get free API key',
  },
  {
    key: 'OPENAI_API_KEY',
    label: 'OpenAI',
    emoji: '🤖',
    description: 'Powers Chat mode with GPT-4.',
    link: 'https://platform.openai.com/api-keys',
    linkLabel: 'Get API key',
  },
  {
    key: 'ANTHROPIC_API_KEY',
    label: 'Anthropic Claude',
    emoji: '🧠',
    description: 'Powers Chat mode with Claude.',
    link: 'https://console.anthropic.com/settings/keys',
    linkLabel: 'Get API key',
  },
]

export default function SetupWizard({ onComplete, onDismiss, connectors, isSetConfig }) {
  const [step, setStep] = useState(0) // 0=welcome, 1=provider, 2=connectors
  const [selectedProvider, setSelectedProvider] = useState(null)
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)

  // Connector setup state
  const [expandedConnector, setExpandedConnector] = useState(null)
  const [connectorValues, setConnectorValues] = useState({})
  const [connectorSaving, setConnectorSaving] = useState(false)
  const [connectedSet, setConnectedSet] = useState(new Set(
    (connectors || []).filter(c => c.connected).map(c => c.name)
  ))

  const handleSaveProvider = useCallback(async () => {
    if (!selectedProvider || !apiKey.trim()) return
    setSaving(true)
    setError(null)
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates: { [selectedProvider.key]: apiKey.trim() } }),
      })
      if (!res.ok) throw new Error('Failed to save')
      setSaved(true)
    } catch {
      setError('Failed to save API key. Please try again.')
    }
    setSaving(false)
  }, [selectedProvider, apiKey])

  const handleSaveConnector = useCallback(async (connector) => {
    const updates = {}
    for (const env of connector.envVars) {
      const val = connectorValues[env.key]
      if (val && val.trim()) updates[env.key] = val.trim()
    }
    if (Object.keys(updates).length === 0) return

    setConnectorSaving(true)
    try {
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates }),
      })
      setConnectedSet(prev => new Set([...prev, connector.name]))
      setExpandedConnector(null)
      setConnectorValues({})
    } catch {}
    setConnectorSaving(false)
  }, [connectorValues])

  // Filter connectors to just env-var ones (skip gmail/work_email/firebase which need OAuth)
  const simpleConnectors = (connectors || []).filter(c =>
    c.envVars.length > 0 && c.name !== 'gmail' && c.name !== 'work_email' && c.name !== 'firebase'
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-claw-900/95 backdrop-blur-xl" />
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-accent/8 rounded-full blur-[150px]" />

      {/* Content */}
      <div className="relative z-10 w-full max-w-2xl mx-6">

        {/* Step 0: Welcome */}
        {step === 0 && (
          <div className="text-center animate-fadeIn">
            <div className="text-7xl mb-6">🦀</div>
            <h1 className="text-4xl font-bold text-white mb-3 tracking-tight">ClawFounder</h1>
            <p className="text-lg text-claw-300 mb-2">Your AI agent that actually does things.</p>
            <p className="text-sm text-claw-500 mb-10 max-w-md mx-auto">
              Connect your services and let AI manage your emails, repos, messages, and more — by text or voice.
            </p>

            <button
              onClick={() => setStep(1)}
              className="px-8 py-3 rounded-xl text-base font-semibold bg-accent/20 text-accent-light
                border border-accent/30 hover:bg-accent/30 hover:border-accent/50
                transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
            >
              Get Started
            </button>

            <div className="mt-6">
              <button onClick={onDismiss} className="text-xs text-claw-600 hover:text-claw-400 transition-colors">
                Skip setup for now
              </button>
            </div>
          </div>
        )}

        {/* Step 1: LLM Provider */}
        {step === 1 && (
          <div className="animate-fadeIn">
            <div className="text-center mb-8">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/[0.04] border border-white/5 text-[11px] text-claw-400 mb-4">
                Step 1 of 2
              </div>
              <h2 className="text-2xl font-bold text-white mb-2">Choose your AI provider</h2>
              <p className="text-sm text-claw-400">Pick at least one to power your assistant. You can add more later.</p>
            </div>

            <div className="space-y-3">
              {PROVIDERS.map(provider => {
                const isSelected = selectedProvider?.key === provider.key
                const alreadySet = isSetConfig?.[provider.key]

                return (
                  <div key={provider.key}>
                    <button
                      onClick={() => {
                        if (!saved) {
                          setSelectedProvider(provider)
                          setApiKey('')
                          setError(null)
                        }
                      }}
                      disabled={saved}
                      className={`w-full flex items-center gap-4 p-4 rounded-xl border text-left transition-all duration-200
                        ${isSelected
                          ? 'border-accent/40 bg-accent/[0.06] ring-1 ring-accent/20'
                          : 'border-white/5 bg-white/[0.03] hover:border-white/10'
                        } ${saved && !isSelected ? 'opacity-40' : ''}`}
                    >
                      <div className="w-11 h-11 rounded-xl bg-white/[0.06] flex items-center justify-center text-xl flex-shrink-0">
                        {provider.emoji}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-white">{provider.label}</span>
                          {provider.recommended && (
                            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-accent/20 text-accent-light border border-accent/30">
                              Recommended
                            </span>
                          )}
                          {alreadySet && (
                            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-success/15 text-green-400">
                              Already set
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-claw-400 mt-0.5">{provider.description}</p>
                      </div>
                    </button>

                    {/* Expanded: API key input */}
                    {isSelected && !saved && (
                      <div className="mt-2 ml-4 mr-4 p-4 rounded-xl bg-white/[0.02] border border-white/5 space-y-3">
                        <div className="flex gap-2">
                          <input
                            type="password"
                            placeholder="Paste your API key..."
                            value={apiKey}
                            onChange={e => setApiKey(e.target.value)}
                            autoFocus
                            className="flex-1 bg-claw-900/60 border border-white/10 rounded-lg px-3 py-2.5 text-sm text-claw-100
                              placeholder:text-claw-500 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all"
                          />
                          <button
                            onClick={handleSaveProvider}
                            disabled={saving || !apiKey.trim()}
                            className="px-5 py-2.5 rounded-lg text-sm font-medium bg-accent/20 text-accent-light
                              hover:bg-accent/30 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                          >
                            {saving ? 'Saving...' : 'Save'}
                          </button>
                        </div>

                        {error && (
                          <p className="text-xs text-red-400">{error}</p>
                        )}

                        {provider.link && (
                          <p className="text-xs text-claw-500">
                            <a href={provider.link} target="_blank" rel="noopener"
                              className="text-accent-light hover:underline">{provider.linkLabel}</a>
                          </p>
                        )}
                      </div>
                    )}

                    {/* Saved confirmation */}
                    {isSelected && saved && (
                      <div className="mt-2 ml-4 mr-4 p-3 rounded-xl bg-success/[0.06] border border-success/20 flex items-center gap-2">
                        <span className="text-green-400 text-sm">✓</span>
                        <span className="text-sm text-green-300">{provider.label} configured!</span>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>

            <div className="flex items-center justify-between mt-8">
              <button onClick={() => setStep(0)} className="text-sm text-claw-500 hover:text-claw-300 transition-colors">
                Back
              </button>
              <button
                onClick={() => setStep(2)}
                disabled={!saved && !PROVIDERS.some(p => isSetConfig?.[p.key])}
                className="px-6 py-2.5 rounded-xl text-sm font-semibold bg-accent/20 text-accent-light
                  border border-accent/30 hover:bg-accent/30 hover:border-accent/50
                  transition-all disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Continue
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Connectors */}
        {step === 2 && (
          <div className="animate-fadeIn">
            <div className="text-center mb-6">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/[0.04] border border-white/5 text-[11px] text-claw-400 mb-4">
                Step 2 of 2
              </div>
              <h2 className="text-2xl font-bold text-white mb-2">Connect your services</h2>
              <p className="text-sm text-claw-400">Optional — you can always add these later from the Connect tab.</p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-[50vh] overflow-y-auto pr-1">
              {simpleConnectors.map(connector => {
                const meta = CONNECTOR_META[connector.name] || { emoji: '🔗', label: connector.name, color: '#7f56d9' }
                const isExpanded = expandedConnector === connector.name
                const isConnected = connectedSet.has(connector.name)

                return (
                  <div key={connector.name}
                    className={`rounded-xl border transition-all duration-200 overflow-hidden
                      ${isConnected
                        ? 'border-success/20 bg-success/[0.03]'
                        : 'border-white/5 bg-white/[0.03]'
                      } ${isExpanded ? 'col-span-1 sm:col-span-2 ring-1 ring-accent/20' : ''}`}
                  >
                    <button
                      onClick={() => setExpandedConnector(isExpanded ? null : connector.name)}
                      className="w-full flex items-center gap-3 p-3.5 text-left"
                    >
                      <div className="w-9 h-9 rounded-lg flex items-center justify-center text-lg flex-shrink-0"
                        style={{ background: meta.color + '18' }}>
                        {meta.emoji}
                      </div>
                      <div className="flex-1 min-w-0">
                        <span className="font-medium text-sm text-white">{meta.label}</span>
                      </div>
                      {isConnected && (
                        <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-success/15 text-green-400">
                          Connected
                        </span>
                      )}
                    </button>

                    {isExpanded && !isConnected && (
                      <div className="px-3.5 pb-3.5 space-y-2.5 border-t border-white/5 pt-3">
                        {connector.envVars.map(env => (
                          <div key={env.key}>
                            <label className="text-[11px] text-claw-400 mb-1 block">
                              <code className="text-accent-light/70">{env.key}</code>
                              {env.required && <span className="text-warning/60 ml-1">*</span>}
                            </label>
                            <input
                              type="password"
                              placeholder={env.description || 'Enter value...'}
                              value={connectorValues[env.key] ?? ''}
                              onChange={e => setConnectorValues(prev => ({ ...prev, [env.key]: e.target.value }))}
                              className="w-full bg-claw-900/60 border border-white/10 rounded-lg px-3 py-2 text-sm text-claw-100
                                placeholder:text-claw-600 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all"
                            />
                          </div>
                        ))}
                        <button
                          onClick={() => handleSaveConnector(connector)}
                          disabled={connectorSaving}
                          className="w-full py-2 rounded-lg text-sm font-medium bg-accent/20 text-accent-light
                            hover:bg-accent/30 transition-all disabled:opacity-30"
                        >
                          {connectorSaving ? 'Saving...' : 'Save'}
                        </button>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>

            <div className="flex items-center justify-between mt-8">
              <button onClick={() => { setStep(1); setSaved(false); setApiKey(''); setSelectedProvider(null) }}
                className="text-sm text-claw-500 hover:text-claw-300 transition-colors">
                Back
              </button>
              <button
                onClick={onComplete}
                className="px-6 py-2.5 rounded-xl text-sm font-semibold bg-accent/20 text-accent-light
                  border border-accent/30 hover:bg-accent/30 hover:border-accent/50
                  transition-all hover:scale-[1.02] active:scale-[0.98]"
              >
                Start Using ClawFounder
              </button>
            </div>
          </div>
        )}
      </div>

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fadeIn { animation: fadeIn 0.4s ease-out; }
      `}</style>
    </div>
  )
}
