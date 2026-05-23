# vlm-sam-industrial-vision-v2

End-cloud industrial visual inspection pipeline: **RK3588 edge** (three-stage async inference) -> **FastAPI backend** -> **Next.js dashboard** (real-time observability).

## Architecture

```text
RK3588 16GB Edge (Orange Pi 5 Plus)
  T1: V4L2 Capture
  T2: EfficientAD-S (FP16 raw RKNN) -> load shedding gate
  T3: FastSAM (FP16 RKNN) bbox proposal + Qwen3-VL-2B (W8A8 RKLLM) structured JSON
  T4: libcurl multipart POST
      |
      v
FastAPI Backend (Python 3.12, SQLAlchemy 2.0, SQLite WAL)
      |
      v
Next.js 15 Dashboard (static export, WebSocket real-time stream, TanStack Table, SVG charts)
```

| Stage | Model | Role | Quantization |
|-------|-------|------|--------------|
| T2 | EfficientAD-S | Load shedding gate (anomaly score threshold) | FP16/no-quant RKNN |
| T3 | FastSAM-s | Bbox proposal (mask decode TODO) | FP16/no-quant RKNN |
| T3 | Qwen3-VL-2B | Structured JSON description (defect_type, severity, confidence, bbox) | W8A8 RKLLM |

## Key Design Decisions

- **4-thread async pipeline** with BoundedQueues and drop-oldest backpressure (Q1=4, Q2=2, Q3=4)
- **API contract v1.2** as single source of truth between edge and backend (`docs/API_CONTRACT.md`)
- **Multipart/form-data** for image upload — no Base64
- **15 MVTec AD categories** covering diverse industrial defect types
- **AB test matrix** (2x2): model size (2B/4B) x fine-tuning mode (base/LoRA), evaluated on JSON parse rate, TTFT, decode TPS, RSS

## What This Project Demonstrates

- End-to-end edge-to-cloud pipeline on resource-constrained hardware (16GB RAM, 6 TOPS NPU)
- Three-stage inference orchestration with backpressure management
- Quantization-aware engineering (FP16 vs INT8/W8A8 trade-offs documented in `docs/ENGINEERING_FINDINGS.md`)
- Structured VLM output with JSON schema validation
- Real-time observability dashboard with per-frame trace events and 4-variant metrics

## Current Status

- **Mainline**: EfficientAD-S FP16 -> FastSAM FP16 -> Qwen3-VL-2B base W8A8
- **EfficientAD-S** serves as a load shedding gate, not a precision defect classifier
- **LoRA** effective in PC bf16; fine-grained gains collapse under RK3588 W8A8 quantization
- **4B base** runtime path works but needs spatial merge fix for texture-sensitive categories
- **Threshold mode** throughput boundary inferred from pass_all data; soak test pending

## Project Structure

| Directory | Description |
|-----------|-------------|
| `edge/` | C++17 4-thread inference pipeline (RKNN + RKLLM + librga + libcurl + V4L2) |
| `backend/` | FastAPI server (REST + WebSocket + SQLAlchemy 2.0 async) |
| `frontend/` | Next.js 15 static dashboard (App Router + shadcn/ui + Tailwind v4) |
| `simulator/` | Python multi-thread simulator (RK3588 stand-in for contract testing) |
| `scripts/` | Training, conversion, evaluation, and prompt optimization scripts |
| `docs/` | Architecture, API contract, deployment guide, experiment reports |

## Quick Start

### Backend

```bash
cd backend && uvicorn app.main:app --reload --port 8000
pytest backend/tests/contract/ -v    # contract tests
```

### Frontend

```bash
cd frontend && npm install && npm run dev    # localhost:3000
npm run build                                 # static export to out/
```

### Simulator

```bash
cd simulator && python line_runner.py
```

### Edge (RK3588 cross-compile)

```bash
cd edge
cmake -DCMAKE_TOOLCHAIN_FILE=aarch64-toolchain.cmake -B build
cmake --build build -j$(nproc)
scp build/edge_pipeline orangepi@192.168.137.66:/home/orangepi/
```

## Documentation

- [System Architecture](docs/ARCHITECTURE.md) — component diagrams, data flow, model details
- [API Contract v1.2](docs/API_CONTRACT.md) — edge-backend interface specification
- [Engineering Findings](docs/ENGINEERING_FINDINGS.md) — quantization issues, debugging, solutions
- [Edge Deployment Summary](docs/reports/edge_deployment_summary.md) — full Phase 7/8 board results
- [Project Timeline](docs/PROJECT_TIMELINE.md) — 8-phase execution plan with per-step details

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Edge Hardware | Orange Pi 5 Plus 16GB (RK3588, 6 TOPS NPU x3) |
| Edge Runtime | C++17, librknnrt, librkllmrt, librga, libcurl, V4L2 |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 async, Pydantic v2 |
| Frontend | Next.js 15, React 19, Tailwind v4, shadcn/ui, TanStack Table v8 |
| Dataset | MVTec AD (15 categories, CC BY-NC-SA 4.0) |

## License

This project is for academic coursework and portfolio demonstration.
