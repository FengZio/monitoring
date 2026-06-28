import { useEffect, useRef, useCallback, useState } from "react";
import type { WSMessage } from "../types";

interface UseWSReturn {
  lastMessage: WSMessage | null;
  connected: boolean;
  connect: (sourceId: string) => void;
  disconnect: () => void;
}

export function useWS(onMessage?: (msg: WSMessage) => void): UseWSReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null);
  const [connected, setConnected] = useState(false);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const mounted = useRef(true);
  const intentionalClose = useRef(false);
  const currentSource = useRef("");
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const cleanup = useCallback(() => {
    if (reconnectTimer.current) { clearTimeout(reconnectTimer.current); reconnectTimer.current = undefined; }
  }, []);

  const disconnect = useCallback(() => {
    cleanup();
    intentionalClose.current = true;
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    setConnected(false);
    currentSource.current = "";
  }, [cleanup]);

  const connect = useCallback((sourceId: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN && currentSource.current === sourceId) return;
    disconnect();
    cleanup();
    intentionalClose.current = false;
    currentSource.current = sourceId;

    const url = `ws://${window.location.hostname}:8000/ws/${sourceId}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => { if (mounted.current) setConnected(true); };
    ws.onmessage = (ev: MessageEvent) => {
      try {
        const msg: WSMessage = JSON.parse(ev.data);
        if (msg.type === "frame" && msg.image) {
          if (mounted.current) setLastMessage(msg);
          onMessageRef.current?.(msg);
        }
      } catch { /* ignore */ }
    };
    ws.onclose = () => {
      if (mounted.current) setConnected(false);
      if (!intentionalClose.current && mounted.current) {
        reconnectTimer.current = setTimeout(() => {
          if (mounted.current && currentSource.current) connect(currentSource.current);
        }, 2000);
      }
    };
    ws.onerror = () => { ws.close(); };
  }, [cleanup, disconnect]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      cleanup();
      intentionalClose.current = true;
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    };
  }, [cleanup]);

  return { lastMessage, connected, connect, disconnect };
}
