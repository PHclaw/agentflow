import { useEffect, useRef, useCallback, useState } from 'react'
import { useThemeStore } from './useTheme'

interface WebSocketMessage {
  type: string
  [key: string]: any
}

interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void
  onConnect?: () => void
  onDisconnect?: () => void
  onError?: (error: Event) => void
  reconnectInterval?: number
  maxReconnectAttempts?: number
}

export function useWebSocket(url: string | null, options: UseWebSocketOptions = {}) {
  const {
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
  } = options

  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>()

  const connect = useCallback(() => {
    if (!url) return

    try {
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        reconnectAttemptsRef.current = 0
        onConnect?.()
      }

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          setLastMessage(message)
          onMessage?.(message)
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e)
        }
      }

      ws.onclose = () => {
        setIsConnected(false)
        onDisconnect?.()

        // 自动重连
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current++
            connect()
          }, reconnectInterval)
        }
      }

      ws.onerror = (error) => {
        onError?.(error)
      }
    } catch (error) {
      console.error('WebSocket connection error:', error)
    }
  }, [url, onMessage, onConnect, onDisconnect, onError, reconnectInterval, maxReconnectAttempts])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  const send = useCallback((message: WebSocketMessage) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])

  return {
    isConnected,
    lastMessage,
    send,
    connect,
    disconnect,
  }
}

// 聊天 WebSocket hook
export function useChatWebSocket(agentId: string) {
  const url = agentId ? `ws://localhost:8000/ws/chat/${agentId}` : null
  
  return useWebSocket(url, {
    onMessage: (message) => {
      console.log('Chat message:', message)
    },
  })
}

// 工作流 WebSocket hook
export function useWorkflowWebSocket(workflowId: string) {
  const url = workflowId ? `ws://localhost:8000/ws/workflow/${workflowId}` : null
  
  return useWebSocket(url, {
    onMessage: (message) => {
      console.log('Workflow update:', message)
    },
  })
}

// 通知 WebSocket hook
export function useNotificationWebSocket(userId: string) {
  const url = userId ? `ws://localhost:8000/ws/user?user_id=${userId}` : null
  
  return useWebSocket(url, {
    onMessage: (message) => {
      if (message.type === 'notification') {
        // 显示通知
        useToastStore.getState().addToast({
          type: message.level || 'info',
          message: message.content,
        })
      }
    },
  })
}

// 导入 toast store（循环依赖问题需要解决）
import { useToastStore } from '../stores'
