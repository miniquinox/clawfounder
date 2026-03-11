import { useState, useRef, useCallback, useEffect } from 'react'

const TOOL_META = {
  email: { emoji: '\ud83d\udce7', label: 'Email', color: '#ea4335' },
  github: { emoji: '\ud83d\udc19', label: 'GitHub', color: '#8b5cf6' },
  calendar: { emoji: '\ud83d\udcc5', label: 'Calendar', color: '#4285f4' },
  messaging: { emoji: '\ud83d\udcac', label: 'Messaging', color: '#e01e5a' },
  finance: { emoji: '\ud83d\udcc8', label: 'Finance', color: '#7b61ff' },
  get_briefing: { emoji: '\ud83d\udcca', label: 'Briefing', color: '#7f56d9' },
  search_knowledge: { emoji: '\ud83e\udde0', label: 'Knowledge', color: '#7f56d9' },
  save_knowledge: { emoji: '\ud83d\udcbe', label: 'Saving', color: '#7f56d9' },
  show_draft: { emoji: '\ud83d\udcdd', label: 'Draft', color: '#f59e0b' },
}

// Audio playback queue with interrupt support
function createAudioPlayer() {
  let audioCtx = null
  let nextStartTime = 0
  let activeSources = []

  return {
    init() {
      if (!audioCtx) audioCtx = new AudioContext({ sampleRate: 24000 })
      return audioCtx
    },
    play(base64Data) {
      const ctx = this.init()
      // Decode base64 -> Int16 -> Float32
      const binary = atob(base64Data)
      const bytes = new Uint8Array(binary.length)
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
      const int16 = new Int16Array(bytes.buffer)
      const float32 = new Float32Array(int16.length)
      for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768

      const buffer = ctx.createBuffer(1, float32.length, 24000)
      buffer.getChannelData(0).set(float32)
      const source = ctx.createBufferSource()
      source.buffer = buffer
      source.connect(ctx.destination)

      const now = ctx.currentTime
      if (nextStartTime < now) nextStartTime = now
      source.start(nextStartTime)
      nextStartTime += buffer.duration

      activeSources.push(source)
      source.onended = () => {
        activeSources = activeSources.filter(s => s !== source)
      }
      return source
    },
    stop() {
      for (const source of activeSources) {
        try { source.stop() } catch {}
      }
      activeSources = []
      nextStartTime = 0
    },
    close() {
      this.stop()
      if (audioCtx) { audioCtx.close(); audioCtx = null }
    }
  }
}

export default function VoiceView() {
  const [status, setStatus] = useState('idle') // idle | connecting | listening | speaking | error
  const [transcript, setTranscript] = useState([])
  const [toolEvents, setToolEvents] = useState([])
  const [actionCards, setActionCards] = useState([])
  const [errorMsg, setErrorMsg] = useState(null)
  const wsRef = useRef(null)
  const captureCtxRef = useRef(null)
  const streamRef = useRef(null)
  const workletNodeRef = useRef(null)
  const playerRef = useRef(createAudioPlayer())
  const userStoppedRef = useRef(false)
  const transcriptEndRef = useRef(null)

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcript])

  const cleanup = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }
    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect()
      workletNodeRef.current = null
    }
    if (captureCtxRef.current) {
      captureCtxRef.current.close()
      captureCtxRef.current = null
    }
    if (wsRef.current) {
      try { wsRef.current.close() } catch {}
      wsRef.current = null
    }
    playerRef.current.close()
    playerRef.current = createAudioPlayer()
  }, [])

  useEffect(() => cleanup, [cleanup])

  const startVoice = async () => {
    userStoppedRef.current = false
    setStatus('connecting')
    setTranscript([])
    setToolEvents([])
    setActionCards([])
    setErrorMsg(null)

    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws/voice`)
      wsRef.current = ws

      ws.onclose = () => {
        if (userStoppedRef.current) {
          cleanup()
          setStatus('idle')
        } else if (wsRef.current) {
          // Unexpected close — reconnect
          console.log('[voice] Unexpected close, reconnecting...')
          cleanup()
          setStatus('connecting')
          setTimeout(() => startVoice(), 1500)
        }
      }
      ws.onerror = () => {
        // onclose fires after onerror
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)

          if (msg.type === 'ready') {
            setStatus('listening')
          } else if (msg.type === 'audio') {
            setStatus('speaking')
            playerRef.current.play(msg.data)
          } else if (msg.type === 'transcript') {
            setTranscript(prev => {
              const last = prev[prev.length - 1]
              if (last && last.role === msg.role && !last.final) {
                return [...prev.slice(0, -1), { ...last, text: last.text + msg.text }]
              }
              return [...prev, { role: msg.role, text: msg.text }]
            })
          } else if (msg.type === 'text') {
            setTranscript(prev => [...prev, { role: 'system', text: msg.text, final: true }])
          } else if (msg.type === 'tool_call') {
            setToolEvents(prev => [...prev, { ...msg, done: false }])
          } else if (msg.type === 'tool_result') {
            setToolEvents(prev =>
              prev.map(e => e.id === msg.id ? { ...e, done: true } : e)
            )
            if (msg.card) {
              setActionCards(prev => [...prev.slice(-4), { id: msg.id, ...msg.card }])
            }
          } else if (msg.type === 'turn_complete') {
            setStatus('listening')
            playerRef.current.stop()
          } else if (msg.type === 'interrupted') {
            setStatus('listening')
            playerRef.current.stop()
          } else if (msg.type === 'error') {
            setErrorMsg(msg.error)
            setStatus('error')
          }
        } catch (e) { console.warn('[voice] Bad message:', e) }
      }

      await new Promise((resolve, reject) => {
        ws.onopen = resolve
        setTimeout(() => reject(new Error('Connection timeout')), 20000)
      })

      // Set up mic capture
      const captureCtx = new AudioContext({ sampleRate: 16000 })
      captureCtxRef.current = captureCtx

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }
      })
      streamRef.current = stream

      try {
        await captureCtx.audioWorklet.addModule('/audio-processor.js')
        const source = captureCtx.createMediaStreamSource(stream)
        const worklet = new AudioWorkletNode(captureCtx, 'pcm-capture')
        workletNodeRef.current = worklet

        worklet.port.onmessage = (e) => {
          if (ws.readyState === WebSocket.OPEN) {
            const int16buf = e.data
            const b64 = arrayBufferToBase64(int16buf)
            ws.send(JSON.stringify({ type: 'audio', data: b64 }))
          }
        }

        source.connect(worklet)
        worklet.connect(captureCtx.destination)
      } catch {
        const source = captureCtx.createMediaStreamSource(stream)
        const processor = captureCtx.createScriptProcessor(4096, 1, 1)
        processor.onaudioprocess = (e) => {
          if (ws.readyState !== WebSocket.OPEN) return
          const float32 = e.inputBuffer.getChannelData(0)
          const int16 = new Int16Array(float32.length)
          for (let i = 0; i < float32.length; i++) {
            const s = Math.max(-1, Math.min(1, float32[i]))
            int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF
          }
          const b64 = arrayBufferToBase64(int16.buffer)
          ws.send(JSON.stringify({ type: 'audio', data: b64 }))
        }
        source.connect(processor)
        processor.connect(captureCtx.destination)
      }

    } catch (err) {
      setErrorMsg(err.message || 'Failed to start voice')
      setStatus('error')
      cleanup()
    }
  }

  const stopVoice = () => {
    userStoppedRef.current = true
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'end' }))
    }
    cleanup()
    setStatus('idle')
  }

  const isActive = status === 'listening' || status === 'speaking' || status === 'connecting'

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Main voice area */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 pb-4 min-h-0">

        {/* Voice orb */}
        <div className="relative mb-8">
          {status === 'listening' && (
            <div className="absolute inset-0 -m-4 rounded-full bg-accent/20 animate-ping" style={{ animationDuration: '2s' }} />
          )}
          {status === 'speaking' && (
            <>
              <div className="absolute inset-0 -m-6 rounded-full bg-accent/10 animate-pulse" />
              <div className="absolute inset-0 -m-3 rounded-full bg-accent/15 animate-pulse" style={{ animationDelay: '0.5s' }} />
            </>
          )}

          <button
            onClick={isActive ? stopVoice : startVoice}
            disabled={status === 'connecting'}
            className={`relative w-24 h-24 rounded-full flex items-center justify-center text-3xl
              transition-all duration-300 shadow-lg
              ${status === 'idle' || status === 'error'
                ? 'bg-accent/20 hover:bg-accent/30 text-accent-light border-2 border-accent/30 hover:border-accent/50 hover:scale-105'
                : status === 'connecting'
                  ? 'bg-accent/10 text-accent-light/50 border-2 border-accent/20 cursor-wait'
                  : status === 'listening'
                    ? 'bg-accent/30 text-white border-2 border-accent/50 hover:bg-red-500/30 hover:border-red-500/50'
                    : 'bg-accent/40 text-white border-2 border-accent/60 hover:bg-red-500/30 hover:border-red-500/50'
              }`}
          >
            {status === 'connecting' ? (
              <span className="animate-spin text-2xl">&#9696;</span>
            ) : isActive ? (
              <span className="text-2xl">&#9632;</span>
            ) : (
              <span>&#127908;</span>
            )}
          </button>
        </div>

        {/* Status label */}
        <div className="text-sm text-claw-400 mb-6 h-5">
          {status === 'idle' && 'Click to start'}
          {status === 'connecting' && 'Connecting to Gemini Live...'}
          {status === 'listening' && <span className="text-accent-light">Listening...</span>}
          {status === 'speaking' && <span className="text-accent-light">Speaking...</span>}
          {status === 'error' && <span className="text-red-400">{errorMsg || 'Connection error'}</span>}
        </div>

        {/* Tool activity */}
        {toolEvents.length > 0 && (
          <div className="w-full max-w-md mb-4 space-y-1.5">
            {toolEvents.slice(-3).map((e, i) => {
              const meta = TOOL_META[e.name] || { emoji: '\ud83d\udd27', label: e.name, color: '#7f56d9' }
              return (
                <div key={i} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/5">
                  <span className="text-xs">{meta.emoji}</span>
                  <span className="text-[11px] text-claw-300 flex-1 truncate">{meta.label}</span>
                  {e.done
                    ? <span className="text-[10px] text-green-400">Done</span>
                    : <span className="text-[10px] text-accent-light animate-pulse">Working...</span>
                  }
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Action Cards — pinned above transcript, always visible */}
      {actionCards.length > 0 && (
        <div className="border-t border-white/5 px-6 py-3 space-y-3 max-h-[35vh] overflow-y-auto shrink-0">
          {actionCards.map((card, i) => (
            <ActionCard key={card.id || i} card={card} />
          ))}
        </div>
      )}

      {/* Transcript — scrollable bottom section */}
      {transcript.length > 0 && (
        <div className={`border-t border-white/5 ${actionCards.length === 0 ? '' : 'border-t-0'} max-h-[30vh] overflow-y-auto px-6 py-3 shrink-0`}>
          <div className="space-y-2">
            <div className="text-[10px] text-claw-600 uppercase tracking-wider">Transcript</div>
            {transcript.map((t, i) => (
              <div key={i} className={`text-sm leading-relaxed ${
                t.role === 'user' ? 'text-claw-300' : t.role === 'system' ? 'text-claw-500 text-xs' : 'text-claw-100'
              }`}>
                {t.role !== 'system' && (
                  <span className={`text-[10px] font-medium mr-2 ${
                    t.role === 'user' ? 'text-claw-500' : 'text-accent-light'
                  }`}>
                    {t.role === 'user' ? 'You' : 'ClawFounder'}
                  </span>
                )}
                {t.text}
              </div>
            ))}
            <div ref={transcriptEndRef} />
          </div>
        </div>
      )}
    </div>
  )
}

// ── Action Card components ───────────────────────────────────────

function ActionCard({ card }) {
  if (card.type === 'email_draft') return <DraftCard card={card} />
  if (card.type === 'email') return <EmailCard card={card} />
  if (card.type === 'email_list') return <EmailListCard card={card} />
  if (card.type === 'email_sent') return <SentCard card={card} />
  if (card.type === 'event_list') return <EventListCard card={card} />
  if (card.type === 'github_list') return <GithubListCard card={card} />
  return null
}

function DraftCard({ card }) {
  return (
    <div className="rounded-xl border-2 border-amber-500/30 bg-amber-500/5 p-5 space-y-3 animate-in fade-in">
      <div className="flex items-center gap-2">
        <span className="text-base">{'\ud83d\udcdd'}</span>
        <span className="text-xs font-semibold text-amber-300 uppercase tracking-wider">Draft — Review Before Sending</span>
      </div>
      <div className="space-y-2 bg-black/20 rounded-lg p-4">
        <div className="flex gap-2 text-xs">
          <span className="text-claw-500 w-10 shrink-0">To:</span>
          <span className="text-claw-200">{card.to_name ? `${card.to_name} <${card.to}>` : card.to}</span>
        </div>
        <div className="flex gap-2 text-xs">
          <span className="text-claw-500 w-10 shrink-0">Subj:</span>
          <span className="text-claw-100 font-medium">{card.subject}</span>
        </div>
        <div className="border-t border-white/5 mt-2 pt-2">
          <div className="text-xs text-claw-200 leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">
            {card.body}
          </div>
        </div>
      </div>
      <div className="text-[10px] text-amber-400/70 italic">
        Say &quot;send it&quot; to approve or &quot;change it&quot; to edit
      </div>
    </div>
  )
}

function EmailCard({ card }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.04] p-4 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-sm">{'\ud83d\udce7'}</span>
        <span className="text-xs font-medium text-claw-200 flex-1 truncate">{card.subject}</span>
      </div>
      <div className="flex gap-4 text-[10px] text-claw-400">
        <span>From: {card.from}</span>
        <span>{card.date}</span>
      </div>
      <div className="text-xs text-claw-300 leading-relaxed whitespace-pre-wrap max-h-32 overflow-y-auto">
        {card.body}
      </div>
    </div>
  )
}

function EmailListCard({ card }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.04] p-3 space-y-1.5">
      <div className="text-[10px] text-claw-500 uppercase tracking-wider">
        {card.total} email{card.total !== 1 ? 's' : ''}
      </div>
      {card.emails.map((e, i) => (
        <div key={i} className="flex items-start gap-2 py-1.5 border-t border-white/5 first:border-0">
          <span className="text-[10px] mt-0.5">{'\ud83d\udce7'}</span>
          <div className="flex-1 min-w-0">
            <div className="text-xs text-claw-200 truncate">{e.subject}</div>
            <div className="text-[10px] text-claw-400 truncate">{e.from}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

function SentCard({ card }) {
  return (
    <div className="rounded-xl border border-green-500/20 bg-green-500/5 px-4 py-3 flex items-center gap-2">
      <span className="text-green-400 text-sm">{'\u2713'}</span>
      <span className="text-xs text-green-300">{card.message}</span>
    </div>
  )
}

function EventListCard({ card }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.04] p-3 space-y-1.5">
      <div className="text-[10px] text-claw-500 uppercase tracking-wider">Calendar</div>
      {card.events.map((e, i) => (
        <div key={i} className="flex items-center gap-2 py-1.5 border-t border-white/5 first:border-0">
          <span className="text-[10px]">{'\ud83d\udcc5'}</span>
          <div className="flex-1 min-w-0">
            <div className="text-xs text-claw-200 truncate">{e.summary}</div>
            <div className="text-[10px] text-claw-400">{e.start}{e.location ? ` \u00b7 ${e.location}` : ''}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

function GithubListCard({ card }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.04] p-3 space-y-1.5">
      <div className="text-[10px] text-claw-500 uppercase tracking-wider">GitHub</div>
      {card.items.map((item, i) => (
        <div key={i} className="flex items-center gap-2 py-1.5 border-t border-white/5 first:border-0">
          <span className={`text-[10px] ${item.state === 'open' ? 'text-green-400' : 'text-claw-400'}`}>
            {item.state === 'open' ? '\u25cf' : '\u25cb'}
          </span>
          <div className="flex-1 min-w-0">
            <div className="text-xs text-claw-200 truncate">#{item.number} {item.title}</div>
            {item.author && <div className="text-[10px] text-claw-400">{item.author}</div>}
          </div>
        </div>
      ))}
    </div>
  )
}

function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}
