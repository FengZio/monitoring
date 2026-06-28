import { useEffect, useRef, useCallback, useState } from "react";
import type { SSEMessage } from "../types";

const SSE_URL = "/api/stream";

interface UseSSEReturn {
  lastMessage: SSEMessage | null;
  connected: boolean;
  connect: () => void;
  disconnect: () => void;
}

export function useSSE(onMessage?: (msg: SSEMessage) => void): UseSSEReturn {
  const esRef = useRef<EventSource | null>(null);
  const [lastMessage, setLastMessage] = useState<SSEMessage | null>(null);
  const [connected, setConnected] = useState(false);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const connecting = useRef(false);
  const mounted = useRef(true);

  const cleanup = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = undefined;
    }
  }, []);

  const disconnect = useCallback(() => {
    cleanup();
    connecting.current = false;
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    setConnected(false);
  }, [cleanup]);

  const connect = useCallback(() => {
    if (connecting.current) return;
    connecting.current = true;
    cleanup();

    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }

    const es = new EventSource(SSE_URL);
    esRef.current = es;

    es.onopen = () => {
      connecting.current = false;
      if (mounted.current) setConnected(true);
    };

    es.addEventListener("frame", (ev: MessageEvent) => {
      try {
        const msg: SSEMessage = JSON.parse(ev.data);
        if (mounted.current) setLastMessage(msg);
        onMessage?.(msg);
      } catch { /* ignore parse errors */ }
    });

    es.onerror = () => {
      connecting.current = false;
      es.close();
      if (mounted.current) setConnected(false);
      // Auto-reconnect after 3 seconds
      reconnectTimer.current = setTimeout(() => {
        if (mounted.current && esRef.current === null) {
          connect();
        }
      }, 3000);
    };
  }, [cleanup, onMessage]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      cleanup();
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, [cleanup]);

  return { lastMessage, connected, connect, disconnect };
}
