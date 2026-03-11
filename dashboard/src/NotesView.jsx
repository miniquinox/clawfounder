import { useState, useEffect, useCallback } from 'react'

export default function NotesView() {
  const [notes, setNotes] = useState([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState(null)
  const [draft, setDraft] = useState({ title: '', content: '', tags: '' })
  const [saving, setSaving] = useState(false)
  const [showNew, setShowNew] = useState(false)

  const fetchNotes = useCallback(async () => {
    try {
      const res = await fetch('/api/notes')
      const data = await res.json()
      setNotes(data.notes || [])
    } catch {
      setNotes([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchNotes() }, [fetchNotes])

  const saveNote = async () => {
    if (!draft.content.trim()) return
    setSaving(true)
    const tags = draft.tags ? draft.tags.split(',').map(t => t.trim()).filter(Boolean) : []
    const body = { title: draft.title.trim(), content: draft.content.trim(), tags }

    try {
      if (editingId) {
        await fetch(`/api/notes/${editingId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
      } else {
        await fetch('/api/notes', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
      }
      setDraft({ title: '', content: '', tags: '' })
      setEditingId(null)
      setShowNew(false)
      fetchNotes()
    } catch (e) {
      console.error('Save failed:', e)
    } finally {
      setSaving(false)
    }
  }

  const deleteNote = async (id) => {
    try {
      await fetch(`/api/notes/${id}`, { method: 'DELETE' })
      fetchNotes()
    } catch (e) {
      console.error('Delete failed:', e)
    }
  }

  const startEdit = (note) => {
    setEditingId(note.id)
    setDraft({
      title: note.title,
      content: note.content,
      tags: (note.tags || []).join(', '),
    })
    setShowNew(true)
  }

  const cancelEdit = () => {
    setEditingId(null)
    setDraft({ title: '', content: '', tags: '' })
    setShowNew(false)
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <span className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center text-sm">
                &#128218;
              </span>
              Notes
            </h2>
            <p className="text-sm text-claw-400 mt-1">
              Add context the PM can reference — API keys, project details, team info, anything.
            </p>
          </div>
          {!showNew && (
            <button
              onClick={() => { setShowNew(true); setEditingId(null); setDraft({ title: '', content: '', tags: '' }) }}
              className="px-4 py-2 rounded-lg bg-accent/20 text-accent-light text-sm font-medium
                hover:bg-accent/30 transition-all border border-accent/20 hover:border-accent/40"
            >
              + Add Note
            </button>
          )}
        </div>

        {/* New/Edit form */}
        {showNew && (
          <div className="rounded-2xl border border-accent/20 bg-white/[0.03] backdrop-blur-xl p-5 space-y-3">
            <input
              type="text"
              placeholder="Title (optional)"
              value={draft.title}
              onChange={e => setDraft(d => ({ ...d, title: e.target.value }))}
              className="w-full bg-claw-900/60 border border-white/10 rounded-lg px-3 py-2 text-sm text-claw-100
                placeholder:text-claw-500 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20"
            />
            <textarea
              placeholder="Write anything — project context, API keys, team info, notes..."
              value={draft.content}
              onChange={e => setDraft(d => ({ ...d, content: e.target.value }))}
              rows={6}
              className="w-full bg-claw-900/60 border border-white/10 rounded-lg px-3 py-2 text-sm text-claw-100
                placeholder:text-claw-500 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20
                resize-y min-h-[100px]"
            />
            <input
              type="text"
              placeholder="Tags (comma-separated, e.g. api, credentials, aws)"
              value={draft.tags}
              onChange={e => setDraft(d => ({ ...d, tags: e.target.value }))}
              className="w-full bg-claw-900/60 border border-white/10 rounded-lg px-3 py-2 text-sm text-claw-100
                placeholder:text-claw-500 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20"
            />
            <div className="flex gap-2 justify-end">
              <button
                onClick={cancelEdit}
                className="px-4 py-2 rounded-lg text-sm text-claw-400 hover:text-claw-200 transition-all"
              >
                Cancel
              </button>
              <button
                onClick={saveNote}
                disabled={saving || !draft.content.trim()}
                className="px-4 py-2 rounded-lg bg-accent/20 text-accent-light text-sm font-medium
                  hover:bg-accent/30 transition-all border border-accent/20 disabled:opacity-40"
              >
                {saving ? 'Saving...' : editingId ? 'Update' : 'Save'}
              </button>
            </div>
          </div>
        )}

        {/* Notes list */}
        {loading ? (
          <div className="text-center text-claw-500 py-12">Loading...</div>
        ) : notes.length === 0 && !showNew ? (
          <div className="text-center py-16 space-y-3">
            <div className="text-4xl">&#128221;</div>
            <p className="text-claw-400">No notes yet.</p>
            <p className="text-sm text-claw-500">
              Add notes with context like API keys, project details, or team info.
              <br />The PM will automatically search these when relevant.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {notes.map(note => (
              <div
                key={note.id}
                className="group rounded-xl border border-white/5 bg-white/[0.03] backdrop-blur-xl p-4
                  hover:border-white/10 transition-all"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    {note.title && (
                      <h3 className="text-sm font-medium text-claw-100 mb-1">{note.title}</h3>
                    )}
                    <p className="text-sm text-claw-300 whitespace-pre-wrap break-words">{note.content}</p>
                    <div className="flex items-center gap-2 mt-2">
                      {(note.tags || []).map(tag => (
                        <span
                          key={tag}
                          className="px-2 py-0.5 rounded-full bg-accent/10 text-accent-light text-[10px] font-medium"
                        >
                          {tag}
                        </span>
                      ))}
                      <span className="text-[10px] text-claw-600 ml-auto">
                        {new Date(note.updated_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => startEdit(note)}
                      className="p-1.5 rounded-lg hover:bg-white/5 text-claw-400 hover:text-claw-200 text-xs"
                      title="Edit"
                    >
                      &#9998;
                    </button>
                    <button
                      onClick={() => deleteNote(note.id)}
                      className="p-1.5 rounded-lg hover:bg-red-500/10 text-claw-400 hover:text-red-400 text-xs"
                      title="Delete"
                    >
                      &#128465;
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
