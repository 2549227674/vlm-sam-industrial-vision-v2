'use client';

import React, { useEffect, useState, useMemo, useCallback } from 'react';
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from '@tanstack/react-table';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { toast } from 'sonner';
import { useDefectWebSocket } from '@/lib/ws';
import { API_BASE } from '@/lib/api';
import type { DefectRead } from '@/types/defect';

const MAX_ROWS = 200;

const SEV_COLORS: Record<string, string> = {
  high: 'var(--color-sev-high)',
  medium: 'var(--color-sev-med)',
  low: 'var(--color-sev-low)',
};

export default function DefectStream() {
  const [data, setData] = useState<DefectRead[]>([]);
  const [selectedRow, setSelectedRow] = useState<DefectRead | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/defects?page_size=50&sort=-edge_ts`)
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then((json) => setData(json.items ?? []))
      .catch((err) => console.error('Failed to fetch initial defects:', err));
  }, []);

  const handleNewDefect = useCallback((defect: DefectRead) => {
    setData((prev) => [defect, ...prev].slice(0, MAX_ROWS));
    toast(`缺陷检测 ${defect.category} - ${defect.defect_type}`, {
      description: `严重程度: ${defect.severity} | 变体: ${defect.variant}`,
    });
  }, []);

  useDefectWebSocket(handleNewDefect);

  const columns = useMemo<ColumnDef<DefectRead>[]>(() => [
    {
      accessorKey: 'image_url',
      header: 'Image',
      cell: ({ row }) => (
        <div className="w-10 h-10 rounded bg-bg-3 overflow-hidden shrink-0">
          <img
            src={`${API_BASE}${row.original.image_url}`}
            alt="defect"
            className="w-full h-full object-cover"
            loading="lazy"
          />
        </div>
      ),
    },
    {
      accessorKey: 'id',
      header: 'ID',
      cell: ({ getValue }) => (
        <span className="font-mono text-fg-3">#{getValue() as number}</span>
      ),
    },
    { accessorKey: 'category', header: 'Category' },
    { accessorKey: 'defect_type', header: 'Type' },
    {
      accessorKey: 'severity',
      header: 'Severity',
      cell: ({ getValue }) => {
        const sev = getValue() as string;
        const cls =
          sev === 'high' ? 'bg-sev-high text-bg-0' :
          sev === 'medium' ? 'bg-sev-med text-bg-0' :
          'bg-sev-low text-bg-0';
        return (
          <Badge variant="outline" className={`${cls} border-none text-[10px] font-mono tracking-wider`}>
            {sev.toUpperCase()}
          </Badge>
        );
      },
    },
    {
      accessorKey: 'confidence',
      header: 'Conf.',
      cell: ({ getValue }) => (
        <span className="font-mono text-xs">{((getValue() as number) * 100).toFixed(1)}%</span>
      ),
    },
    {
      accessorKey: 'variant',
      header: 'Var',
      cell: ({ getValue }) => {
        const v = getValue() as string;
        const cls = v === 'A' ? 'text-sig-violet border-sig-violet bg-sig-violet/10' : 'text-sig-teal border-sig-teal bg-sig-teal/10';
        return (
          <span className={`font-mono font-bold text-[11px] px-1.5 py-0.5 border ${cls}`}>
            {v}
          </span>
        );
      },
    },
    {
      accessorKey: 'pipeline_ms',
      header: 'Pipeline',
      cell: ({ getValue }) => {
        const ms = getValue() as DefectRead['pipeline_ms'];
        if (!ms) return <span className="text-fg-4">-</span>;
        return (
          <div className="flex gap-0.5 font-mono text-[9px]">
            <span className="bg-stage-1 text-bg-0 px-1 py-0.5 rounded-sm" title="EfficientAD-S">
              {ms.efficientad.toFixed(1)}
            </span>
            <span className="bg-stage-2 text-bg-0 px-1 py-0.5 rounded-sm" title="FastSAM">
              {ms.fastsam.toFixed(1)}
            </span>
            <span className="bg-stage-3 text-white px-1 py-0.5 rounded-sm" title="Qwen3-VL">
              {ms.qwen3vl.toFixed(1)}
            </span>
          </div>
        );
      },
    },
    {
      accessorKey: 'edge_ts',
      header: 'Time',
      cell: ({ getValue }) => (
        <span className="text-fg-3 text-xs font-mono">
          {new Date(getValue() as string).toLocaleTimeString()}
        </span>
      ),
    },
  ], []);

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const sevColor = selectedRow ? SEV_COLORS[selectedRow.severity] ?? SEV_COLORS.low : SEV_COLORS.low;
  const totalMs = selectedRow
    ? selectedRow.pipeline_ms.efficientad + selectedRow.pipeline_ms.fastsam + selectedRow.pipeline_ms.qwen3vl
    : 0;

  return (
    <>
      <div className="rounded-lg border border-line bg-bg-1 overflow-hidden">
        <ScrollArea className="h-[400px] w-full">
          <Table>
            <TableHeader className="sticky top-0 bg-bg-2 z-10">
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id} className="border-line hover:bg-bg-2">
                  {headerGroup.headers.map((header) => (
                    <TableHead key={header.id} className="text-fg-3 font-mono text-[10px] uppercase tracking-wider h-8 px-2">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </TableHead>
                  ))}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows?.length ? (
                table.getRowModel().rows.map((row) => (
                  <TableRow
                    key={row.id}
                    className="cursor-pointer hover:bg-bg-3/50 transition-colors border-line-soft h-12"
                    onClick={() => {
                      setSelectedRow(row.original);
                      setIsDrawerOpen(true);
                    }}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <TableCell key={cell.id} className="px-2 py-1 text-xs">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={columns.length} className="h-24 text-center text-fg-3 font-mono text-sm">
                    Listening to edge data stream...
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </ScrollArea>
      </div>

      {/* Detail Drawer */}
      <Sheet open={isDrawerOpen} onOpenChange={setIsDrawerOpen}>
        <SheetContent className="w-[400px] sm:w-[540px] overflow-y-auto border-l-line bg-bg-0">
          <SheetHeader className="mb-5">
            <SheetTitle className="text-xl font-mono text-sig-cyan">
              DEFECT #{selectedRow?.id}
            </SheetTitle>
            <SheetDescription className="text-fg-3 font-mono text-xs">
              {selectedRow?.edge_ts && new Date(selectedRow.edge_ts).toLocaleString()}
            </SheetDescription>
          </SheetHeader>

          {selectedRow && (
            <div className="flex flex-col gap-5">

              {/* Section 1: Image + BBox Overlay */}
              <div className="relative w-full rounded-xl border border-line bg-bg-1 overflow-hidden">
                <img
                  src={`${API_BASE}${selectedRow.image_url}`}
                  alt="defect"
                  className="w-full h-auto block"
                />
                {selectedRow.bboxes.map((bb, idx) => (
                  <div
                    key={idx}
                    className="absolute border-2 pointer-events-none"
                    style={{
                      left: `${bb.x * 100}%`,
                      top: `${bb.y * 100}%`,
                      width: `${bb.w * 100}%`,
                      height: `${bb.h * 100}%`,
                      borderColor: sevColor,
                      backgroundColor: `color-mix(in srgb, ${sevColor} 15%, transparent)`,
                      boxShadow: `0 0 8px color-mix(in srgb, ${sevColor} 40%, transparent)`,
                    }}
                  >
                    <span
                      className="absolute -top-4 left-[-2px] px-1 text-[8px] font-mono font-bold text-bg-0 whitespace-nowrap"
                      style={{ backgroundColor: sevColor }}
                    >
                      {selectedRow.defect_type.toUpperCase()}
                    </span>
                  </div>
                ))}
              </div>

              {/* Section 2: Metadata Grid */}
              <div className="grid grid-cols-2 gap-y-3 gap-x-4 p-3 rounded-lg bg-bg-1 border border-line">
                <MetaField label="CATEGORY" value={selectedRow.category} />
                <MetaField label="DEFECT TYPE" value={selectedRow.defect_type} />
                <MetaField label="SEVERITY" value={selectedRow.severity.toUpperCase()} />
                <div className="flex flex-col">
                  <span className="text-fg-3 font-mono text-[9px] tracking-wider uppercase">VARIANT</span>
                  <span className={`font-mono text-xs font-bold mt-0.5 px-1.5 py-0.5 border w-fit ${
                    selectedRow.variant === 'A' ? 'text-sig-violet border-sig-violet bg-sig-violet/10' : 'text-sig-teal border-sig-teal bg-sig-teal/10'
                  }`}>
                    {selectedRow.variant}
                  </span>
                </div>
                <MetaField label="CONFIDENCE" value={`${(selectedRow.confidence * 100).toFixed(1)}%`} />
                <MetaField label="ANOMALY SCORE" value={selectedRow.anomaly_score.toFixed(3)} />
                <MetaField label="BBOX COUNT" value={String(selectedRow.bboxes.length)} />
                <MetaField label="SCHEMA" value={selectedRow.schema_version} />
              </div>

              {/* Section 3: Pipeline Profiler */}
              <div className="bg-bg-1 border border-line rounded-lg p-3">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-fg-3 font-mono text-[9px] tracking-wider uppercase">PIPELINE PROFILER</span>
                  <span className="text-fg-2 font-mono text-[10px]">{totalMs.toFixed(1)} ms</span>
                </div>
                <div className="flex gap-0.5 h-6 rounded overflow-hidden">
                  <div
                    className="bg-stage-1 flex items-center justify-center text-[9px] font-mono text-bg-0 font-semibold"
                    style={{ width: `${(selectedRow.pipeline_ms.efficientad / totalMs) * 100}%` }}
                    title={`EfficientAD: ${selectedRow.pipeline_ms.efficientad}ms`}
                  >
                    {selectedRow.pipeline_ms.efficientad.toFixed(1)}
                  </div>
                  <div
                    className="bg-stage-2 flex items-center justify-center text-[9px] font-mono text-bg-0 font-semibold"
                    style={{ width: `${(selectedRow.pipeline_ms.fastsam / totalMs) * 100}%` }}
                    title={`FastSAM: ${selectedRow.pipeline_ms.fastsam}ms`}
                  >
                    {selectedRow.pipeline_ms.fastsam.toFixed(1)}
                  </div>
                  <div
                    className="bg-stage-3 flex items-center justify-center text-[9px] font-mono text-white font-semibold"
                    style={{ width: `${(selectedRow.pipeline_ms.qwen3vl / totalMs) * 100}%` }}
                    title={`Qwen3-VL: ${selectedRow.pipeline_ms.qwen3vl}ms`}
                  >
                    {selectedRow.pipeline_ms.qwen3vl.toFixed(1)}
                  </div>
                </div>
                <div className="flex justify-between mt-1.5 text-[8px] font-mono text-fg-4">
                  <span>EfficientAD-S</span>
                  <span>FastSAM-s</span>
                  <span>Qwen3-VL-2B</span>
                </div>
              </div>

              {/* Section 4: NPU Trace Placeholder */}
              {selectedRow.trace_events && selectedRow.trace_events.length > 0 ? (
                <div className="bg-bg-1 border border-line rounded-lg p-3">
                  <span className="text-fg-3 font-mono text-[9px] tracking-wider uppercase block mb-2">NPU / CPU / RGA TRACE</span>
                  <div className="h-20 border border-dashed border-line rounded flex items-center justify-center">
                    <span className="font-mono text-xs text-fg-3">
                      [TRACE CHART PLACEHOLDER &mdash; {selectedRow.trace_events.length} events]
                    </span>
                  </div>
                  <span className="font-mono text-[9px] text-fg-4 block mt-1">
                    Phase 7: ECharts gantt chart from trace_events
                  </span>
                </div>
              ) : (
                <div className="rounded-lg border border-dashed border-line p-4 text-center">
                  <span className="font-mono text-[10px] text-fg-3 tracking-wider block mb-1">
                    NPU / CPU / RGA TRACE
                  </span>
                  <span className="font-mono text-xs text-fg-3">
                    Awaiting C++ edge instrumentation (Phase 7)
                  </span>
                  <span className="font-mono text-[9px] text-fg-4 block mt-1">
                    trace_events: null {'→'} will render Chrome-trace style gantt chart
                  </span>
                </div>
              )}

              {/* Section 5: Description */}
              {selectedRow.description && (
                <div className="bg-bg-1 p-3 rounded-lg border border-line">
                  <span className="text-fg-3 font-mono text-[9px] tracking-wider uppercase block mb-1">DESCRIPTION</span>
                  <div className="text-fg text-sm">{selectedRow.description}</div>
                </div>
              )}

              {/* Section 6: VLM Raw JSON */}
              <div className="bg-bg-1 p-3 rounded-lg border border-line">
                <span className="text-fg-3 font-mono text-[9px] tracking-wider uppercase block mb-2">QWEN3-VL RAW JSON</span>
                <pre className="font-mono text-xs text-sig-cyan overflow-x-auto whitespace-pre-wrap break-all">
                  {JSON.stringify(selectedRow.vlm_metrics ?? { message: 'No metrics available' }, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </>
  );
}

function MetaField({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-fg-3 font-mono text-[9px] tracking-wider uppercase">{label}</span>
      <span className="text-fg font-medium text-sm">{value}</span>
    </div>
  );
}
