import { useEffect, useRef, useState } from 'react'

import { ROOT_API } from '../utils/api'

export function useRealtime(token, onMessage) {
  const onMessageRef = useRef(onMessage)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    onMessageRef.current = onMessage
  }, [onMessage])

  useEffect(() => {
    if (!token) {
      setConnected(false)
      return undefined
    }

    const wsUrl = `${ROOT_API.replace(/^http/, 'ws')}/ws?token=${encodeURIComponent(token)}`
    let socket
    let interval
    let reconnectTimer

    const connect = () => {
      console.info('[SPYGYM][WS] connecting', wsUrl)
      socket = new WebSocket(wsUrl)

      socket.onopen = () => {
        setConnected(true)
        console.info('[SPYGYM][WS] connected')
        interval = window.setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send('ping')
          }
        }, 15000)
      }

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data)
          onMessageRef.current?.(payload)
        } catch {
          onMessageRef.current?.({ type: 'unknown', raw: event.data })
        }
      }

      socket.onclose = (event) => {
        setConnected(false)
        if (interval) window.clearInterval(interval)
        console.warn('[SPYGYM][WS] closed', {
          code: event.code,
          reason: event.reason || 'no_reason',
          wasClean: event.wasClean,
        })
        // Authentication and server errors should wait for a new login/token instead of looping forever.
        if (![1008, 1011].includes(event.code)) {
          reconnectTimer = window.setTimeout(connect, 3000)
        }
      }

      socket.onerror = (event) => {
        setConnected(false)
        console.warn('[SPYGYM][WS] error', event)
      }
    }

    connect()

    return () => {
      if (interval) window.clearInterval(interval)
      if (reconnectTimer) window.clearTimeout(reconnectTimer)
      if (socket && socket.readyState < 2) {
        socket.close()
      }
    }
  }, [token])

  return { connected }
}
