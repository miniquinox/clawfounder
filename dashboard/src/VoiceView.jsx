import { useState, useRef, useCallback, useEffect } from 'react'

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
      // Decode base64 → Int16 → Float32
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

      // Schedule sequentially so chunks don't overlap
      const now = ctx.currentTime
      if (nextStartTime < now) nextStartTime = now
      source.start(nextStartTime)
      nextStartTime += buffer.duration

      // Track active sources for interrupt
      activeSources.push(source)
      source.onended = () => {
        activeSources = activeSources.filter(s => s !== source)
      }

      return source
    },
    stop() {
      // Immediately stop all playing/queued audio
      for (const source of activeSources) {
        try { source.stop() } catch {}
      }
      activeSources = []
      nextStartTime = 0
    },
    reset() {
      this.stop()
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
  const [errorMsg, setErrorMsg] = useState(null)
  const wsRef = useRef(null)
  const captureCtxRef = useRef(null)
  const streamRef = useRef(null)
  const workletNodeRef = useRef(null)
  const playerRef = useRef(createAudioPlayer())

  const cleanup = useCallback(() => {
    // Stop mic
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
    // Close WebSocket
    if (wsRef.current) {
      try { wsRef.current.close() } catch {}
      wsRef.current = null
    }
    // Close audio player
    playerRef.current.close()
    playerRef.current = createAudioPlayer()
  }, [])

  // Cleanup on unmount
  useEffect(() => cleanup, [cleanup])

  const startVoice = async () => {
    setStatus('connecting')
    setTranscript([])
    setToolEvents([])
    setErrorMsg(null)

    try {
      // 1. Connect WebSocket
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws/voice`)
      wsRef.current = ws

      ws.onclose = () => {
        if (status !== 'idle') {
          setStatus('idle')
          cleanup()
        }
      }
      ws.onerror = () => {
        setErrorMsg('WebSocket connection failed')
        setStatus('error')
        cleanup()
      }

      // 2. Handle incoming messages
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
              // Merge consecutive same-role transcripts
              const last = prev[prev.length - 1]
              if (last && last.role === msg.role && !last.final) {
                return [...prev.slice(0, -1), { ...last, text: last.text + msg.text }]
              }
              return [...prev, { role: msg.role, text: msg.text }]
            })
          } else if (msg.type === 'text') {
            setTranscript(prev => [...prev, { role: 'assistant', text: msg.text, final: true }])
          } else if (msg.type === 'tool_call') {
            const connName = msg.name?.split('_')[0] || 'unknown'
            setToolEvents(prev => [...prev, { ...msg, connector: connName, done: false }])
          } else if (msg.type === 'tool_result') {
            setToolEvents(prev =>
              prev.map(e => e.id === msg.id ? { ...e, done: true } : e)
            )
          } else if (msg.type === 'turn_complete') {
            setStatus('listening')
            playerRef.current.reset()
          } else if (msg.type === 'interrupted') {
            setStatus('listening')
            playerRef.current.reset()
          } else if (msg.type === 'error') {
            setErrorMsg(msg.error)
            setStatus('error')
          }
        } catch {}
      }

      // Wait for WebSocket to open
      await new Promise((resolve, reject) => {
        ws.onopen = resolve
        setTimeout(() => reject(new Error('Connection timeout')), 10000)
      })

      // 3. Set up mic capture
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

      // Try AudioWorklet, fall back to ScriptProcessor
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
        // Fallback: ScriptProcessorNode
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
      <div className="flex-1 flex flex-col items-center justify-center px-6 pb-4">

        {/* Voice orb */}
        <div className="relative mb-8">
          {/* Outer pulse ring */}
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
              <span className="text-2xl">&#9632;</span> // stop square
            ) : (
              <span>&#127908;</span> // mic
            )}
          </button>
        </div>

        {/* Status label */}
        <div className="text-sm text-claw-400 mb-6 h-5">
          {status === 'idle' && 'Click to start voice chat'}
          {status === 'connecting' && 'Connecting to Gemini Live...'}
          {status === 'listening' && (
            <span className="text-accent-light">Listening...</span>
          )}
          {status === 'speaking' && (
            <span className="text-accent-light">ClawFounder is speaking...</span>
          )}
          {status === 'error' && (
            <span className="text-red-400">{errorMsg || 'Connection error'}</span>
          )}
        </div>

        {/* Tool activity */}
        {toolEvents.length > 0 && (
          <div className="w-full max-w-md mb-4 space-y-1.5">
            {toolEvents.slice(-5).map((e, i) => {
              const meta = CONNECTOR_META[e.connector] || { emoji: '\ud83d\udd27', label: e.connector, color: '#7f56d9' }
              return (
                <div key={i} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/5">
                  <span className="text-xs">{meta.emoji}</span>
                  <span className="text-[11px] text-claw-300 flex-1 truncate">{e.name}</span>
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

      {/* Transcript */}
      {transcript.length > 0 && (
        <div className="border-t border-white/5 max-h-[40vh] overflow-y-auto px-6 py-4 space-y-3">
          <div className="text-[10px] text-claw-600 uppercase tracking-wider mb-2">Transcript</div>
          {transcript.map((t, i) => (
            <div key={i} className={`text-sm leading-relaxed ${
              t.role === 'user' ? 'text-claw-300' : 'text-claw-100'
            }`}>
              <span className={`text-[10px] font-medium mr-2 ${
                t.role === 'user' ? 'text-claw-500' : 'text-accent-light'
              }`}>
                {t.role === 'user' ? 'You' : 'ClawFounder'}
              </span>
              {t.text}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// Utility: ArrayBuffer → base64
function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}
