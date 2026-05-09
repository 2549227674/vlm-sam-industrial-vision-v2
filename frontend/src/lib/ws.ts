'use client';

import { useEffect, useRef } from 'react';
import type { DefectRead } from '@/types/defect';
import { API_BASE } from '@/lib/api';

const WS_RETRY_DELAYS = [1000, 2000, 4000, 8000, 15000];

export function useDefectWebSocket(onDefect: (defect: DefectRead) => void) {
  const onDefectRef = useRef(onDefect);
  onDefectRef.current = onDefect;

  useEffect(() => {
    if (typeof window === 'undefined') return;

    let retryCount = 0;
    let ws: WebSocket | null = null;
    let stopped = false;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    function connect() {
      const wsUrl = API_BASE.replace(/^http/, 'ws') + '/ws/dashboard';
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        retryCount = 0;
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'defect_created') {
            onDefectRef.current(msg.data as DefectRead);
          }
          if (msg.type === 'ping') {
            ws?.send(JSON.stringify({ type: 'pong' }));
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        if (stopped) return;
        const delay = WS_RETRY_DELAYS[Math.min(retryCount, WS_RETRY_DELAYS.length - 1)];
        retryCount++;
        reconnectTimer = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        ws?.close();
      };
    }

    connect();

    return () => {
      stopped = true;
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, []);
}
