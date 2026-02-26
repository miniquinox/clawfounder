import { useState, useEffect, useRef, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'

const CONNECTOR_META = {
    gmail: { emoji: '📧', label: 'Gmail', color: '#ea4335' },
    telegram: { emoji: '💬', label: 'Telegram', color: '#26a5e4' },
    github: { emoji: '🐙', label: 'GitHub', color: '#8b5cf6' },
    supabase: { emoji: '⚡', label: 'Supabase', color: '#3ecf8e' },
    firebase: { emoji: '🔥', label: 'Firebase', color: '#ffca28' },
    yahoo_finance: { emoji: '📈', label: 'Yahoo Finance', color: '#7b61ff' },
}

function ToolCallBlock({ event }) {
    const [expanded, setExpanded] = useState(false)
    const meta = CONNECTOR_META[event.connector] || { emoji: '🔧', label: event.connector, color: '#7f56d9' }

    return (
        <div className="my-2 rounded-xl border border-white/8 bg-white/[0.02] overflow-hidden">
            <button
                onClick={() => setExpanded(!expanded)}
                className="w-full flex items-center gap-3 px-4 py-3 text-left cursor-pointer hover:bg-white/[0.02] transition-colors"
            >
                <span className="text-accent-light text-sm">⟐</span>
                <span className="text-xs text-claw-300">
                    {meta.emoji} {event.connector} / <span className="text-claw-100 font-medium">{event.tool}</span>
                </span>
                <span className="ml-auto text-[10px] text-claw-500">
                    {expanded ? 'Hide Details ∧' : 'Show Details ∨'}
                </span>
            </button>

            {expanded && (
                <div className="px-4 pb-3 border-t border-white/5">
                    {event.args && Object.keys(event.args).length > 0 && (
                        <div className="mt-2">
                            <div className="text-[10px] text-claw-500 font-medium mb-1">Arguments</div>
                            <pre className="text-xs text-claw-200 bg-claw-900/60 rounded-lg px-3 py-2 overflow-x-auto">
                                {JSON.stringify(event.args, null, 2)}
                            </pre>
                        </div>
                    )}
                    {event.result && (
                        <div className="mt-2">
                            <div className="text-[10px] text-claw-500 font-medium mb-1">Output</div>
                            <pre className="text-xs text-claw-200 bg-claw-900/60 rounded-lg px-3 py-2 overflow-x-auto max-h-64 overflow-y-auto whitespace-pre-wrap">
                                {event.result}
                            </pre>
                            {event.truncated && (
                                <div className="text-[10px] text-claw-500 mt-1">⚠ Output truncated</div>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

function MessageBubble({ msg }) {
    if (msg.role === 'user') {
        return (
            <div className="flex justify-end mb-4">
                <div className="max-w-[80%] rounded-2xl rounded-br-md bg-accent/20 border border-accent/20 px-4 py-3">
                    <p className="text-sm text-claw-100 whitespace-pre-wrap">{msg.text}</p>
                </div>
            </div>
        )
    }

    // Assistant message with possible tool calls
    return (
        <div className="mb-4 max-w-[90%]">
            {msg.events?.map((event, i) => {
                if (event.type === 'thinking') {
                    return (
                        <div key={i} className="flex items-center gap-2 text-xs text-claw-500 mb-2 ml-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-accent-light/50 animate-pulse" />
                            {event.text}
                        </div>
                    )
                }
                if (event.type === 'tool_call' || event.type === 'tool_result') {
                    // Merge tool_call and tool_result into one block
                    if (event.type === 'tool_result') {
                        return <ToolCallBlock key={i} event={event} />
                    }
                    // Skip standalone tool_call — it'll be merged with result
                    return null
                }
                if (event.type === 'text') {
                    return (
                        <div key={i} className="rounded-2xl rounded-bl-md bg-white/[0.04] border border-white/5 px-4 py-3 mt-2">
                            <div className="text-sm text-claw-100 leading-relaxed markdown-body">
                                <ReactMarkdown
                                    components={{
                                        h1: ({ children }) => <h1 className="text-lg font-bold text-claw-50 mt-3 mb-2">{children}</h1>,
                                        h2: ({ children }) => <h2 className="text-base font-bold text-claw-50 mt-3 mb-1.5">{children}</h2>,
                                        h3: ({ children }) => <h3 className="text-sm font-semibold text-claw-100 mt-2 mb-1">{children}</h3>,
                                        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                                        ul: ({ children }) => <ul className="list-disc pl-5 mb-2 space-y-0.5">{children}</ul>,
                                        ol: ({ children }) => <ol className="list-decimal pl-5 mb-2 space-y-0.5">{children}</ol>,
                                        li: ({ children }) => <li className="text-claw-200">{children}</li>,
                                        strong: ({ children }) => <strong className="font-semibold text-claw-50">{children}</strong>,
                                        em: ({ children }) => <em className="italic text-claw-200">{children}</em>,
                                        pre: ({ children }) => (
                                            <pre className="bg-claw-900/60 rounded-lg px-3 py-2 my-2 overflow-x-auto [&>code]:bg-transparent [&>code]:p-0 [&>code]:rounded-none [&>code]:text-xs [&>code]:text-claw-200">{children}</pre>
                                        ),
                                        code: ({ children }) => (
                                            <code className="bg-white/10 text-accent-light px-1.5 py-0.5 rounded text-xs font-mono">{children}</code>
                                        ),
                                        a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-accent-light hover:underline">{children}</a>,
                                        blockquote: ({ children }) => <blockquote className="border-l-2 border-accent/40 pl-3 my-2 text-claw-300 italic">{children}</blockquote>,
                                        hr: () => <hr className="border-white/10 my-3" />,
                                        table: ({ children }) => <div className="overflow-x-auto my-2"><table className="text-xs w-full border-collapse">{children}</table></div>,
                                        th: ({ children }) => <th className="border border-white/10 px-2 py-1 text-left text-claw-100 bg-white/5 font-semibold">{children}</th>,
                                        td: ({ children }) => <td className="border border-white/10 px-2 py-1 text-claw-200">{children}</td>,
                                    }}
                                >{event.text}</ReactMarkdown>
                            </div>
                        </div>
                    )
                }
                if (event.type === 'error') {
                    return (
                        <div key={i} className="rounded-xl bg-danger/10 border border-danger/20 px-4 py-3 mt-2">
                            <p className="text-sm text-red-300">❌ {event.error}</p>
                        </div>
                    )
                }
                return null
            })}
        </div>
    )
}

export default function ChatView({ prefillMessage, onPrefillConsumed }) {
    const [providers, setProviders] = useState([])
    const [selectedProvider, setSelectedProvider] = useState('')
    const [messages, setMessages] = useState([])
    const [input, setInput] = useState('')
    const [isStreaming, setIsStreaming] = useState(false)
    const messagesEndRef = useRef(null)
    const inputRef = useRef(null)

    useEffect(() => {
        fetch('/api/providers').then(r => r.json()).then(d => {
            setProviders(d.providers || [])
            if (d.providers?.length > 0) {
                setSelectedProvider(d.providers[0].id)
            }
        })
    }, [])

    // Handle prefilled message from Briefing view
    useEffect(() => {
        if (prefillMessage && !isStreaming) {
            setInput(prefillMessage)
            onPrefillConsumed?.()
        }
    }, [prefillMessage, isStreaming, onPrefillConsumed])

    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [])

    useEffect(() => { scrollToBottom() }, [messages, scrollToBottom])

    const handleSend = async () => {
        const text = input.trim()
        if (!text || isStreaming || !selectedProvider) return

        setInput('')
        setIsStreaming(true)

        // Add user message
        const userMsg = { role: 'user', text }
        setMessages(prev => [...prev, userMsg])

        // Build chat history for the backend
        const history = messages
            .filter(m => m.role === 'user' || (m.role === 'assistant' && m.finalText))
            .map(m => ({
                role: m.role,
                text: m.role === 'assistant' ? m.finalText : m.text,
            }))

        // Create a placeholder assistant message
        const assistantMsg = { role: 'assistant', events: [], finalText: '' }
        setMessages(prev => [...prev, assistantMsg])

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text, provider: selectedProvider, history }),
            })

            const reader = response.body.getReader()
            const decoder = new TextDecoder()
            let buffer = ''
            let currentToolCall = null

            while (true) {
                const { value, done } = await reader.read()
                if (done) break

                buffer += decoder.decode(value, { stream: true })
                const lines = buffer.split('\n')
                buffer = lines.pop() || ''

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue
                    const jsonStr = line.slice(6).trim()
                    if (!jsonStr) continue

                    try {
                        const event = JSON.parse(jsonStr)

                        if (event.type === 'done') continue

                        if (event.type === 'tool_call') {
                            currentToolCall = event
                            // Add a pending tool event
                            setMessages(prev => {
                                const msgs = [...prev]
                                const last = { ...msgs[msgs.length - 1] }
                                last.events = [...last.events, { type: 'tool_call', ...event }]
                                msgs[msgs.length - 1] = last
                                return msgs
                            })
                            continue
                        }

                        if (event.type === 'tool_result') {
                            // Merge with the previous tool_call or add standalone
                            const merged = { ...event, ...(currentToolCall || {}), type: 'tool_result' }
                            currentToolCall = null

                            setMessages(prev => {
                                const msgs = [...prev]
                                const last = { ...msgs[msgs.length - 1] }
                                // Replace the last tool_call event with the merged result
                                const evts = [...last.events]
                                const callIdx = evts.findLastIndex(e => e.type === 'tool_call' && e.tool === merged.tool)
                                if (callIdx >= 0) {
                                    evts[callIdx] = merged
                                } else {
                                    evts.push(merged)
                                }
                                last.events = evts
                                msgs[msgs.length - 1] = last
                                return msgs
                            })
                            continue
                        }

                        if (event.type === 'text') {
                            setMessages(prev => {
                                const msgs = [...prev]
                                const last = { ...msgs[msgs.length - 1] }
                                const evts = [...last.events]
                                // Merge consecutive text chunks into one bubble
                                const lastEvt = evts[evts.length - 1]
                                if (lastEvt && lastEvt.type === 'text') {
                                    evts[evts.length - 1] = { ...lastEvt, text: lastEvt.text + event.text }
                                } else {
                                    evts.push(event)
                                }
                                last.events = evts
                                last.finalText = (last.finalText || '') + event.text
                                msgs[msgs.length - 1] = last
                                return msgs
                            })
                            continue
                        }

                        // thinking, error, etc.
                        setMessages(prev => {
                            const msgs = [...prev]
                            const last = { ...msgs[msgs.length - 1] }
                            last.events = [...last.events, event]
                            msgs[msgs.length - 1] = last
                            return msgs
                        })
                    } catch {
                        // Ignore parse errors
                    }
                }
            }
        } catch (err) {
            console.error('[Chat] Error:', err.message)
            setMessages(prev => {
                const msgs = [...prev]
                const last = { ...msgs[msgs.length - 1] }
                last.events = [...last.events, { type: 'error', error: err.message }]
                msgs[msgs.length - 1] = last
                return msgs
            })
        }

        setIsStreaming(false)
        inputRef.current?.focus()
    }

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSend()
        }
    }

    if (providers.length === 0) {
        return (
            <div className="flex-1 flex items-center justify-center">
                <div className="text-center space-y-4">
                    <span className="text-4xl">🔑</span>
                    <h3 className="text-lg font-medium text-white">No LLM Providers Configured</h3>
                    <p className="text-sm text-claw-400 max-w-md">
                        Switch to the <span className="text-accent-light">Connect</span> tab and add at least one
                        API key (Gemini, OpenAI, or Claude) to start chatting.
                    </p>
                </div>
            </div>
        )
    }

    return (
        <div className="flex-1 flex flex-col min-h-0">
            {/* Provider selector bar */}
            <div className="border-b border-white/5 bg-claw-900/30 backdrop-blur-sm px-6 py-3 flex items-center gap-4">
                <span className="text-xs text-claw-400">Agent:</span>
                <div className="flex gap-2">
                    {providers.map(p => (
                        <button
                            key={p.id}
                            onClick={() => setSelectedProvider(p.id)}
                            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all
                ${selectedProvider === p.id
                                    ? 'bg-accent/20 border border-accent/30 text-accent-light'
                                    : 'bg-white/[0.03] border border-white/5 text-claw-400 hover:text-claw-200 hover:border-white/10'
                                }`}
                        >
                            <span>{p.emoji}</span>
                            {p.label}
                        </button>
                    ))}
                </div>
                {messages.length > 0 && (
                    <button
                        onClick={() => setMessages([])}
                        className="ml-auto text-[10px] text-claw-500 hover:text-claw-300 transition-colors"
                    >
                        Clear chat
                    </button>
                )}
            </div>

            {/* Messages area */}
            <div className="flex-1 overflow-y-auto px-6 py-6 space-y-2">
                {messages.length === 0 && (
                    <div className="flex-1 flex items-center justify-center h-full">
                        <div className="text-center space-y-3 py-20">
                            <span className="text-5xl">🦀</span>
                            <h3 className="text-lg font-medium text-white">Ask me anything</h3>
                            <p className="text-sm text-claw-400 max-w-sm mx-auto">
                                I can use your connected services to take real actions.
                                Try asking about your emails, repos, or stock prices.
                            </p>
                            <div className="flex flex-wrap gap-2 justify-center pt-2">
                                {[
                                    "What's AAPL trading at?",
                                    "Check my GitHub repos",
                                    "List my Firestore collections",
                                ].map(q => (
                                    <button
                                        key={q}
                                        onClick={() => { setInput(q); inputRef.current?.focus() }}
                                        className="text-xs px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/5
                      text-claw-300 hover:bg-white/[0.08] hover:border-white/10 transition-all"
                                    >
                                        {q}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                )}

                {messages.map((msg, i) => (
                    <MessageBubble key={i} msg={msg} />
                ))}

                {isStreaming && (
                    <div className="flex items-center gap-2 text-xs text-claw-400 ml-2">
                        <div className="flex gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-accent-light animate-bounce" style={{ animationDelay: '0ms' }} />
                            <span className="w-1.5 h-1.5 rounded-full bg-accent-light animate-bounce" style={{ animationDelay: '150ms' }} />
                            <span className="w-1.5 h-1.5 rounded-full bg-accent-light animate-bounce" style={{ animationDelay: '300ms' }} />
                        </div>
                        Thinking...
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input bar */}
            <div className="border-t border-white/5 bg-claw-900/50 backdrop-blur-xl px-6 py-4">
                <div className="flex gap-3 items-end max-w-3xl mx-auto">
                    <textarea
                        ref={inputRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask ClawFounder anything..."
                        rows={1}
                        className="flex-1 bg-white/[0.04] border border-white/10 rounded-xl px-4 py-3 text-sm text-claw-100
              placeholder:text-claw-500 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20
              transition-all resize-none"
                        style={{ minHeight: '44px', maxHeight: '120px' }}
                    />
                    <button
                        onClick={handleSend}
                        disabled={isStreaming || !input.trim()}
                        className="px-5 py-3 rounded-xl text-sm font-medium transition-all
              bg-accent text-white hover:bg-accent/80 shadow-lg shadow-accent/20
              disabled:opacity-30 disabled:cursor-not-allowed disabled:shadow-none"
                    >
                        {isStreaming ? (
                            <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin inline-block" />
                        ) : (
                            'Send'
                        )}
                    </button>
                </div>
            </div>
        </div>
    )
}
