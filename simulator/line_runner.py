"""simulator/line_runner.py

多产线缺陷模拟器 — 符合 API_CONTRACT.md v1 规范。

修正项（对照 Gemini 初版）：
  1. PNG→JPEG 内存转换，杜绝 MIME 欺骗 / 400 INVALID_IMAGE
  2. BBox 范围收紧：x≤0.70, w≤0.25，确保 x+w ≤ 0.95（不触发二次校验 400）
  3. 路径用 Path(__file__).parent 解析，从任意目录均可运行
  4. 指数退避重试：500ms × 2ⁿ + jitter，覆盖 408/429/5xx（API_CONTRACT.md §11）
  5. 每线程独享 requests.Session，复用 TCP 连接
  6. edge_ts：A 用 t0，B 用 t0+1ms，绝对杜绝 409 DUPLICATE_REPORT
  7. 传实际文件名（basename），便于后端日志定位
"""

import io
import json
import random
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from PIL import Image

# ─── 配置 ───────────────────────────────────────────────────────────────────
BACKEND_URL = "http://localhost:8000/api/edge/report"
# Path(__file__).parent = simulator/  →  simulator/mvtec/
MVTEC_DIR = Path(__file__).parent / "mvtec"

CATEGORIES: dict[str, str] = {
    "metal_nut": "L1",
    "screw":     "L2",
    "pill":      "L3",
}
BEAT_MS  = 1500   # 产线节拍（毫秒）
JITTER_MS = 200   # 节拍抖动上限（±）

# 重试策略（API_CONTRACT.md §11）
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}
MAX_RETRIES    = 5
BASE_DELAY_MS  = 500  # 首次重试等待（ms），后续 × 2ⁿ

# ─── 辅助：PNG → JPEG 内存转换 ──────────────────────────────────────────────
def to_jpeg_bytes(png_path: Path, quality: int = 85) -> bytes:
    """将任意图片读入内存并编码为 JPEG bytes，避免发送 PNG 二进制冒充 JPEG。"""
    with Image.open(png_path) as img:
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()


# ─── 辅助：构造 meta JSON ────────────────────────────────────────────────────
def fabricate_metadata(
    category: str,
    line_id: str,
    defect_type: str,
    variant: str,
    edge_ts: datetime,         # 由调用方显式传入，A/B 各不同
) -> dict:
    """严格遵循 DefectCreate schema（API_CONTRACT.md §2）。"""
    is_defect = defect_type != "good"

    # ── severity / confidence / anomaly_score ──
    severity  = random.choice(["low", "medium", "high"]) if is_defect else "low"
    confidence    = round(random.uniform(0.70, 0.99), 3) if is_defect else 0.99
    anomaly_score = round(random.uniform(5.0, 25.0), 2)  if is_defect else round(random.uniform(0.1, 2.0), 2)

    # ── bboxes：x≤0.70, w≤0.25 → x+w ≤ 0.95，绝不越界 ──
    bboxes: list[dict] = []
    if is_defect:
        for _ in range(random.randint(1, 3)):
            x = round(random.uniform(0.05, 0.70), 3)
            y = round(random.uniform(0.05, 0.70), 3)
            w = round(random.uniform(0.05, min(0.25, 0.95 - x)), 3)
            h = round(random.uniform(0.05, min(0.25, 0.95 - y)), 3)
            bboxes.append({"x": x, "y": y, "w": w, "h": h})
        bboxes = bboxes[:16]  # max_length=16

    # ── description ──
    desc = (
        f"检测到 {category} 的 {defect_type} 类型缺陷"
        if is_defect else "产品外观正常，未检测到缺陷"
    )

    # ── pipeline_ms：三键必须全部存在（field_validator 检查）──
    pipeline_ms = {
        "efficientad": round(random.uniform(10.0, 25.0), 1),
        "fastsam":     round(random.uniform(35.0, 65.0), 1),
        "qwen3vl":     round(random.uniform(400.0, 1300.0), 1),
    }

    # ── vlm_metrics：A 模拟长 Prompt，B 模拟短 Prompt ──
    prompt_tokens = random.randint(800, 1500) if variant == "A" else random.randint(40, 100)
    vlm_metrics = {
        "ttft_ms":       round(random.uniform(250.0, 900.0), 1),
        "decode_tps":    round(random.uniform(8.0, 22.0), 1),
        "prompt_tokens": prompt_tokens,
        "output_tokens": random.randint(25, 90),
        "rss_mb":        round(random.uniform(2400.0, 3600.0), 1),
        "json_parse_ok": True,
    }

    return {
        "line_id":        line_id,
        "category":       category,
        "defect_type":    defect_type,
        "severity":       severity,
        "confidence":     confidence,
        "anomaly_score":  anomaly_score,
        "bboxes":         bboxes,
        "description":    desc,
        "variant":        variant,
        # edge_ts 必须带时区（field_validator must_be_aware）
        "edge_ts":        edge_ts.isoformat(),
        "pipeline_ms":    pipeline_ms,
        "vlm_metrics":    vlm_metrics,
        "schema_version": "v1",
    }


# ─── 辅助：带指数退避的 POST ─────────────────────────────────────────────────
def post_with_retry(
    session: requests.Session,
    line_id: str,
    variant: str,
    jpeg_bytes: bytes,
    filename: str,
    meta: dict,
) -> None:
    """发送请求，对 408/429/5xx 做指数退避重试（API_CONTRACT.md §11）。"""
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = session.post(
                BACKEND_URL,
                files={"image": (filename, jpeg_bytes, "image/jpeg")},
                data={"meta": json.dumps(meta)},
                timeout=10,
            )
            if resp.status_code == 200:
                record_id = resp.json().get("id", "?")
                print(f"[{line_id}][{variant}] ✓ {meta['defect_type']:15s} → id={record_id}")
                return
            if resp.status_code not in RETRY_STATUSES or attempt == MAX_RETRIES:
                print(f"[{line_id}][{variant}] ✗ HTTP {resp.status_code}: {resp.text[:120]}")
                return
            # 需要重试
            delay_ms = (BASE_DELAY_MS * (2 ** attempt)) + random.randint(0, 250)
            print(f"[{line_id}][{variant}] ↺ HTTP {resp.status_code}，{delay_ms}ms 后重试 ({attempt+1}/{MAX_RETRIES})")
            time.sleep(delay_ms / 1000.0)

        except requests.exceptions.RequestException as exc:
            if attempt == MAX_RETRIES:
                print(f"[{line_id}][{variant}] ✗ 网络异常（已放弃）: {exc}")
                return
            delay_ms = (BASE_DELAY_MS * (2 ** attempt)) + random.randint(0, 250)
            print(f"[{line_id}][{variant}] ↺ 网络异常，{delay_ms}ms 后重试 ({attempt+1}/{MAX_RETRIES}): {exc}")
            time.sleep(delay_ms / 1000.0)


# ─── 产线线程 ────────────────────────────────────────────────────────────────
def run_line(category: str, line_id: str) -> None:
    print(f"[{line_id}] 启动产线：category={category}")

    image_paths = sorted((MVTEC_DIR / category / "test").rglob("*.png"))
    if not image_paths:
        print(f"[{line_id}] ⚠ 找不到图片：{MVTEC_DIR / category / 'test'}，线程退出")
        return
    print(f"[{line_id}] 共 {len(image_paths)} 张图片，开始循环…")

    session = requests.Session()  # 每线程独享，复用连接

    while True:
        random.shuffle(image_paths)

        for img_path in image_paths:
            defect_type = img_path.parent.name  # …/test/scratch/000.png → "scratch"
            filename    = img_path.name          # 保留真实文件名，便于调试

            # Bug 1 修正：真正的 JPEG bytes（内存转换，不发 PNG 二进制）
            try:
                jpeg_bytes = to_jpeg_bytes(img_path)
            except Exception as exc:
                print(f"[{line_id}] ⚠ 图片转换失败 {img_path.name}: {exc}")
                continue

            # Bug 6 修正：A 用 t0，B 用 t0+1ms，杜绝 409 DUPLICATE_REPORT
            t0 = datetime.now(timezone.utc)
            t_b = t0 + timedelta(milliseconds=1)

            post_with_retry(
                session, line_id, "A",
                jpeg_bytes, filename,
                fabricate_metadata(category, line_id, defect_type, "A", t0),
            )
            post_with_retry(
                session, line_id, "B",
                jpeg_bytes, filename,
                fabricate_metadata(category, line_id, defect_type, "B", t_b),
            )

            # 产线节拍：1500ms ± 200ms
            sleep_s = max(0.0, (BEAT_MS + random.uniform(-JITTER_MS, JITTER_MS)) / 1000.0)
            time.sleep(sleep_s)


# ─── 启动入口 ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  VLM 工业视觉检测模拟器")
    print(f"  目标后端: {BACKEND_URL}")
    print(f"  数据集路径: {MVTEC_DIR}")
    print("=" * 50)

    threads: list[threading.Thread] = []
    for category, line_id in CATEGORIES.items():
        t = threading.Thread(
            target=run_line,
            args=(category, line_id),
            name=f"Line-{line_id}",
            daemon=True,
        )
        threads.append(t)
        t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n模拟器收到中断信号，停止。")
