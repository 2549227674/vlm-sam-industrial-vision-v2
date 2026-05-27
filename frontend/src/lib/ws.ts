'use client';

import { useEffect, useRef } from 'react';
import type { DefectRead } from '@/types/defect';
import { API_BASE } from '@/lib/api';

const WS_RETRY_DELAYS = [1000, 2000, 4000, 8000, 15000];

export interface EnrichmentUpdate {
  defect_id: number;
  enrichment_id: number;
  status: 'pending' | 'running' | 'complete' | 'rejected' | 'failed';
  provider: string;
  observation_source?: string | null;
  updated_fields: string[];
  error_message?: string | null;
  ts: string;
}

export function useDefectWebSocket(
  onDefect: (defect: DefectRead) => void,
  onEnrichment?: (update: EnrichmentUpdate) => void,
) {
  const onDefectRef = useRef(onDefect);
  onDefectRef.current = onDefect;
  const onEnrichmentRef = useRef(onEnrichment);
  onEnrichmentRef.current = onEnrichment;

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
          if (msg.type === 'defect_enrichment_updated' && onEnrichmentRef.current) {
            onEnrichmentRef.current(msg as EnrichmentUpdate);
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
