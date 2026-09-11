import { useEffect, useRef, useState } from 'react'

/**
 * Listen for what the backend says without being asked.
 *
 * Everything else in this app asks the API a question and renders the answer.
 * This listens: a jam forming on the driver's route is exactly the case where
 * waiting to be asked is the wrong behaviour, so the monitor pushes and the
 * robot delivers what arrives.
 *
 * The socket reconnects with a widening delay, because a backend restart
 * during a demonstration should heal itself rather than leave a page that
 * looks fine and is quietly deaf.
 *
 * `onNote` is held in a ref, so a new callback each render does not tear the
 * connection down and rebuild it.
 */

function wsUrl() {
  const base = import.meta.env.VITE_API_BASE || '/api'
  if (base.startsWith('http')) {
    return `${base.replace(/^http/, 'ws')}/notifications/ws`
  }
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}${base}/notifications/ws`
}

export default function useNotificationSocket(onNote) {
  const [connected, setConnected] = useState(false)
  const onNoteRef = useRef(onNote)
  onNoteRef.current = onNote

  useEffect(() => {
    let closed = false
    let retries = 0
    let retryTimer = 0
    let socket = null

    const connect = () => {
      if (closed) return
      try {
        socket = new WebSocket(wsUrl())
      } catch {
        return
      }

      socket.onopen = () => { retries = 0; setConnected(true) }

      socket.onmessage = (event) => {
        let data
        try { data = JSON.parse(event.data) } catch { return }
        // The backlog is history, not news — delivering it would replay old
        // alerts every time a page loads.
        if (data.type === 'backlog') return
        onNoteRef.current?.(data)
      }

      socket.onclose = () => {
        setConnected(false)
        if (closed) return
        retries = Math.min(retries + 1, 6)
        retryTimer = setTimeout(connect, 500 * 2 ** (retries - 1))
      }

      socket.onerror = () => socket.close()
    }

    connect()
    return () => {
      closed = true
      clearTimeout(retryTimer)
      socket?.close()
    }
  }, [])

  return connected
}
