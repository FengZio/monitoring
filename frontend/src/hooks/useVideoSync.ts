import { useRef, useCallback, useEffect, useState } from "react";
import type { SSEMessage } from "../types";

const FPS = 25.0;
const BUFFER_SECS = 10; // keep last 10 seconds of data

interface SyncedData {
  detections: SSEMessage["detections"];
  tracks: SSEMessage["tracks"];
  fence_pixels: SSEMessage["fence_pixels"];
  orb_tracking: boolean;
}

interface UseVideoSyncReturn {
  synced: SyncedData;
  alerts: SSEMessage["alerts"];
}

/** Buffers SSE data keyed by frame time, returns the entry matching video.currentTime. */
export function useVideoSync(
  videoRef: React.RefObject<HTMLVideoElement | null>,
  lastMessage: SSEMessage | null
): UseVideoSyncReturn {
  const buffer = useRef<Map<number, SyncedData>>(new Map());
  const [synced, setSynced] = useState<SyncedData>({
    detections: [],
    tracks: [],
    fence_pixels: [],
    orb_tracking: false,
  });
  const [alerts, setAlerts] = useState<SSEMessage["alerts"]>([]);
  const alertsAcc = useRef<SSEMessage["alerts"]>([]);

  // Ingest new SSE data into buffer
  useEffect(() => {
    if (!lastMessage) return;
    const frameIndex = lastMessage.frame_index ?? 0;
    const frameTime = frameIndex / FPS;

    buffer.current.set(frameTime, {
      detections: lastMessage.detections || [],
      tracks: lastMessage.tracks || [],
      fence_pixels: lastMessage.fence_pixels || [],
      orb_tracking: lastMessage.orb_tracking || false,
    });

    // Accumulate alerts
    if (lastMessage.alerts && lastMessage.alerts.length > 0) {
      alertsAcc.current = [...alertsAcc.current, ...lastMessage.alerts];
    }

    // Cleanup old entries
    const cutoff = frameTime - BUFFER_SECS;
    for (const t of buffer.current.keys()) {
      if (t < cutoff) buffer.current.delete(t);
    }
  }, [lastMessage]);

  // Every 100ms, sync to video.currentTime
  useEffect(() => {
    const interval = setInterval(() => {
      const video = videoRef.current;
      if (!video || video.paused) return;

      const ct = video.currentTime;
      if (ct === undefined || ct === 0) return;

      // Find closest entry in buffer
      let bestTime = 0;
      let bestDiff = Infinity;
      for (const t of buffer.current.keys()) {
        const diff = Math.abs(t - ct);
        if (diff < bestDiff) {
          bestDiff = diff;
          bestTime = t;
        }
      }

      const entry = buffer.current.get(bestTime);
      if (entry) {
        setSynced(entry);
      }
    }, 100);

    return () => clearInterval(interval);
  }, [videoRef]);

  // Flush alerts periodically
  useEffect(() => {
    const interval = setInterval(() => {
      if (alertsAcc.current.length > 0) {
        setAlerts(alertsAcc.current);
        alertsAcc.current = [];
      }
    }, 200);
    return () => clearInterval(interval);
  }, []);

  return { synced, alerts };
}
