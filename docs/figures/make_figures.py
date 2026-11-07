"""Regenerate the README figures (light + dark).

Usage: python3 docs/figures/make_figures.py [output_dir]
Needs matplotlib (Pillow comes with it) and a CJK font (Microsoft YaHei, Noto Sans CJK SC or similar).

- architecture_{light,dark}.png      示意：板端四个线程、后端、看板，VLM 补充走旁路
- pipeline_queues_{light,dark}.png   三个有界队列的容量和 30 分钟长跑里的最高水位
- drop_vs_interval_{light,dark}.png  节拍扫频的丢帧比例，和长跑画在同一根轴上
- fastsam_int8_{light,dark}.png      FastSAM 输出共用一个 INT8 scale，置信度被舍成 0
- dashboard_frame.jpg                看板单帧详情的截图，裁掉右侧抽屉（原图 docs/figures/前端/3.png）
每张图的数字出处写在对应函数里。
"""
import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)

for f in ("msyh.ttc", "msyhbd.ttc"):
    for base in ("/mnt/c/Windows/Fonts", "C:/Windows/Fonts"):
        if Path(base, f).exists():
            font_manager.fontManager.addfont(str(Path(base, f)))
for f in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
          "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"):
    if Path(f).exists():
        font_manager.fontManager.addfont(f)
plt.rcParams["font.family"] = ["Microsoft YaHei", "Noto Sans CJK SC", "Noto Sans CJK JP", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# 颜色按含义固定：data 数据与队列，compute 计算，fail 瓶颈与失败，good 正常与修好以后，其余用灰
THEMES = {
    "light": dict(surface="#ffffff", panel="#f6f8fa", ink="#1f2328", ink2="#59636e", muted="#818b98",
                  line="#d1d9e0", gray="#8c959f", gray_bg="#eef1f4",
                  data="#0072b2", data_bg="#cfe3f3", compute="#c98500", compute_bg="#fbe7bf",
                  fail="#d55e00", fail_bg="#f6d5c2", good="#00875f", good_bg="#c7ebdd"),
    "dark": dict(surface="#0d1117", panel="#161b22", ink="#f0f6fc", ink2="#9198a1", muted="#6e7681",
                 line="#30363d", gray="#6e7681", gray_bg="#21262d",
                 data="#4aa3df", data_bg="#0f2a40", compute="#f0b429", compute_bg="#3b2c0a",
                 fail="#ff8a4c", fail_bg="#3d1f10", good="#3fc49a", good_bg="#0f2e24"),
}
WIDTH_IN, DPI = 7.6, 180
SMALL = 9


def canvas(height_in, rect, t):
    """一张图加一块画布：横向 0–100，纵向按宽高比换算，方框不会被拉扁。"""
    fig = plt.figure(figsize=(WIDTH_IN, height_in))
    fig.patch.set_facecolor(t["surface"])
    ax = fig.add_axes(rect)
    h = 100 * (height_in * rect[3]) / (WIDTH_IN * rect[2])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax, h


def titles(fig, t, title, subtitle=None):
    fig.text(0.02, 0.965, title, fontsize=12, fontweight="bold", color=t["ink"], va="top")
    if subtitle:
        fig.text(0.02, 0.965 - 0.32 / fig.get_figheight(), subtitle, fontsize=SMALL + 0.5,
                 color=t["ink2"], va="top")


def note(fig, t, text):
    fig.text(0.02, 0.02, text, fontsize=SMALL - 0.5, color=t["muted"], va="bottom", linespacing=1.4)


def box(ax, x, y, w, h, text, fc, ec, color, size=SMALL, weight="normal", ls="-", lw=1.2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.8",
                                fc=fc, ec=ec, lw=lw, ls=ls))
    if text:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, color=color,
                weight=weight, linespacing=1.35)


def label(ax, x, y, text, color, size=SMALL, ha="left", va="center", weight="normal"):
    ax.text(x, y, text, ha=ha, va=va, fontsize=size, color=color, weight=weight, linespacing=1.35)


def arrow(ax, x0, y0, x1, y1, color, style="-|>", lw=1.3, ls="-"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=11,
                                 color=color, lw=lw, ls=ls, shrinkA=0, shrinkB=0))


def cells(ax, x, y, w, h, n, filled, t):
    for i in range(n):
        fc = t["data_bg"] if i < filled else t["surface"]
        ax.add_patch(Rectangle((x + i * w, y), w, h, fc=fc, ec=t["data"], lw=1.1))


def style_axes(ax, t):
    ax.set_facecolor(t["surface"])
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(t["line"])
    ax.tick_params(colors=t["ink2"], labelsize=SMALL, length=0, pad=5)


def save(fig, name, t_name, t):
    fig.savefig(OUT / f"{name}_{t_name}.png", dpi=DPI, facecolor=t["surface"])
    plt.close(fig)


# ---------------------------------------------------------------- 1. architecture
# 示意，按代码画：四个线程和 T3 二选一 edge/src/main.cpp；上传 edge/src/common/http_client.cpp；
# 后端路由 docs/API_CONTRACT.md 第 1 节和 backend/app/routers/；VLM 补充的开关 backend/app/services/enrichment_config.py，
# 只写回两段文字 docs/API_CONTRACT.md 第 14.6 节
def fig_arch(t_name, t):
    fig, ax, H = canvas(5.5, [0.02, 0.085, 0.96, 0.775], t)
    titles(fig, t, "板子上做检测，后端入库推送，VLM 只在旁路补说明",
           "数据是 MVTec AD 公开数据集，板子上按节拍循环读测试集图片模拟采集；T3 按配置二选一")
    # 板端泳道
    top, bot = H - 0.3, 29.0
    ax.add_patch(FancyBboxPatch((0, bot), 100, top - bot, boxstyle="round,pad=0,rounding_size=1.2",
                                fc=t["panel"], ec=t["line"], lw=1.0))
    label(ax, 1.5, top - 2.3, "RK3588 板端", t["ink"], size=10, weight="bold")
    label(ax, 14.5, top - 2.3, "C++20 程序 edge_pipeline，四个线程，三个有界队列（满了丢最旧）", t["ink2"])
    y0, bh = 37.0, 16.0
    xs = [(1.5, 14), (23, 18), (48, 30), (86.5, 12.5)]
    texts = [("T1 采集", "按节拍读\nMVTec 测试图"),
             ("T2 门控", "EfficientAD-S\nNPU · FP16\n约一成放行"),
             (None, None),
             ("T4 上传", "libcurl\nmultipart\n失败退避重试")]
    for (x, w), (ttl, body) in zip(xs, texts):
        box(ax, x, y0, w, bh, "", t["surface"], t["gray"], t["ink"])
        if ttl:
            label(ax, x + w / 2, y0 + bh - 2.6, ttl, t["ink"], size=10, ha="center", weight="bold")
            label(ax, x + w / 2, y0 + bh / 2 - 2.2, body, t["ink2"], ha="center")
    # T3：两种实现
    x3, w3 = xs[2]
    label(ax, x3 + w3 / 2, y0 + bh - 2.6, "T3 定位（按配置二选一）", t["ink"], size=10, ha="center",
          weight="bold")
    box(ax, x3 + 1.5, y0 + 6.6, w3 - 3, 5.0, "现在：YOLOv8n\nCPU · ONNX Runtime", t["good_bg"], t["good"],
        t["ink"])
    box(ax, x3 + 1.5, y0 + 1.0, w3 - 3, 5.0, "原来：FastSAM（NPU）\n＋ Qwen3-VL-2B（RKLLM）", t["gray_bg"],
        t["gray"], t["ink2"])
    # 队列
    for (xa, wa), (xb, _), q in zip(xs[:-1], xs[1:], ("Q1 · 4", "Q2 · 2", "Q3 · 4")):
        arrow(ax, xa + wa + 0.4, y0 + bh / 2, xb - 0.4, y0 + bh / 2, t["data"], lw=1.5)
        label(ax, (xa + wa + xb) / 2, y0 + bh / 2 + 1.8, q, t["data"], ha="center", va="bottom")
    # 板上的 VLM 服务（旁路）
    vx, vw, vy, vh = 1.5, 44.0, 30.6, 4.2
    box(ax, vx, vy, vw, vh, "VLM 服务（单独的进程）：Qwen3-VL-2B · NPU", t["surface"], t["compute"], t["ink"],
        ls="--")

    # 服务端泳道
    sbot, stop = 0.3, 23.0
    ax.add_patch(FancyBboxPatch((0, sbot), 100, stop - sbot, boxstyle="round,pad=0,rounding_size=1.2",
                                fc=t["panel"], ec=t["line"], lw=1.0))
    label(ax, 1.5, stop - 2.3, "服务端", t["ink"], size=10, weight="bold")
    by, bhh = 1.8, 16.0
    wk = (1.5, 28)
    be = (38.5, 30)
    db = (79.5, 19.5)
    box(ax, *wk[:1], by, wk[1], bhh, "", t["surface"], t["compute"], t["ink"], ls="--")
    label(ax, wk[0] + wk[1] / 2, by + bhh - 2.6, "补充 worker", t["ink"], size=10, ha="center", weight="bold")
    label(ax, wk[0] + wk[1] / 2, by + bhh / 2 - 2.2, "轮询待补充的任务\n环境变量打开，默认关", t["ink2"],
          ha="center")
    box(ax, be[0], by, be[1], bhh, "", t["surface"], t["gray"], t["ink"])
    label(ax, be[0] + be[1] / 2, by + bhh - 2.6, "FastAPI 后端", t["ink"], size=10, ha="center",
          weight="bold")
    label(ax, be[0] + be[1] / 2, by + bhh / 2 - 2.2, "POST /api/edge/report\n校验字段和框的范围\nSQLite 入库，图片落盘",
          t["ink2"], ha="center")
    box(ax, db[0], by, db[1], bhh, "", t["surface"], t["gray"], t["ink"])
    label(ax, db[0] + db[1] / 2, by + bhh - 2.6, "Next.js 看板", t["ink"], size=10, ha="center", weight="bold")
    label(ax, db[0] + db[1] / 2, by + bhh / 2 - 2.2, "缺陷列表、单帧详情\n框、类别、各段耗时", t["ink2"],
          ha="center")

    # T4 → 后端：先往下，再往左，再往下
    tx = xs[3][0] + xs[3][1] / 2
    bx = be[0] + be[1] * 0.75
    mid = 25.2
    ax.plot([tx, tx, bx], [y0, mid, mid], color=t["data"], lw=1.5, solid_joinstyle="miter")
    arrow(ax, bx, mid, bx, by + bhh + 0.2, t["data"], lw=1.5)
    label(ax, (tx + bx) / 2, mid + 0.5, "HTTP multipart：图片＋JSON", t["data"], ha="center", va="bottom")
    # 后端 → 看板
    arrow(ax, be[0] + be[1] + 0.4, by + bhh / 2, db[0] - 0.4, by + bhh / 2, t["data"], lw=1.5)
    label(ax, (be[0] + be[1] + db[0]) / 2, by + bhh / 2 + 1.2, "WebSocket", t["data"], ha="center",
          va="bottom")
    label(ax, (be[0] + be[1] + db[0]) / 2, by + bhh / 2 - 1.2, "推送", t["data"], ha="center", va="top")
    # 后端 ⇄ worker
    yl, yr = by + bhh / 2 + 2.6, by + bhh / 2 - 2.6
    arrow(ax, be[0] - 0.4, yl, wk[0] + wk[1] + 0.4, yl, t["compute"], lw=1.2, ls="--")
    label(ax, (be[0] + wk[0] + wk[1]) / 2, yl + 0.6, "取任务", t["compute"], ha="center", va="bottom")
    arrow(ax, wk[0] + wk[1] + 0.4, yr, be[0] - 0.4, yr, t["compute"], lw=1.2, ls="--")
    label(ax, (be[0] + wk[0] + wk[1]) / 2, yr - 0.6, "写回", t["compute"], ha="center", va="top")
    # worker ⇄ 板上 VLM 服务
    cx = 22.0
    arrow(ax, cx, by + bhh + 0.3, cx, vy - 0.3, t["compute"], style="<|-|>", lw=1.2, ls="--")
    label(ax, cx + 1.2, (stop + bot) / 2, "图＋框 → 两段文字", t["compute"])

    note(fig, t, "示意，按 edge/src/main.cpp、docs/API_CONTRACT.md 和 backend/app/ 画。虚线是旁路：上传接口不等 VLM，\n"
                 "VLM 只写回观察描述和严重程度理由，框、类别、置信度不改")
    save(fig, "architecture", t_name, t)


# ---------------------------------------------------------------- 2. pipeline and queues
# 容量：edge/src/main.cpp 第 161–163 行
# 每帧耗时：docs/experiments/phase7_prompt2e_e2e_acceptance_report.md 第 182–219 行（24 帧验收的均值）
# 节拍、帧数：docs/experiments/phase9_experiment_validation_release_gates.md 第 39–40、64–68 行
# 水位和进出数：results/phase9_threshold_soak/raw/edge_run.log 第 6788–6790 行
def fig_pipeline(t_name, t):
    fig, ax, H = canvas(3.15, [0.02, 0.13, 0.96, 0.56], t)
    titles(fig, t, "Q2 只给 2 格，因为它后面的 T3 最慢",
           "满了都丢最旧的；30 分钟长跑里 Q2 到过满，没有溢出，丢帧 0")
    bh, cw, ch, g = 8.6, 3.2, 4.2, 2.6
    y = 13.6
    threads = [("T1 采集\n取图片路径", 11.0, False, "节拍 5 秒"),
               ("T2 门控\nEfficientAD", 14.0, False, "约 0.35 秒／帧"),
               ("T3 定位与报告\nFastSAM、VLM", 15.5, True, "约 11 秒／帧"),
               ("T4 上传\nHTTP", 11.0, False, "看网络")]
    queues = [("Q1", 4, 1, "进 366 帧"), ("Q2", 2, 2, "进 37 帧"), ("Q3", 4, 1, "进 36 条结果")]
    x = 0.5
    for i, (name, w, hot, cost) in enumerate(threads):
        box(ax, x, y, w, bh, "", t["fail_bg"] if hot else t["surface"], t["fail"] if hot else t["gray"],
            t["ink"], lw=1.8 if hot else 1.2)
        label(ax, x + w / 2, y + bh / 2 + 1.2, name, t["ink"], ha="center", weight="bold" if hot else "normal")
        label(ax, x + w / 2, y + 1.6, cost, t["fail"] if hot else t["muted"], ha="center")
        x += w
        if i == len(queues):
            break
        qname, cap, high, count = queues[i]
        arrow(ax, x + 0.2, y + bh / 2, x + g - 0.3, y + bh / 2, t["muted"])
        qx, qy = x + g, y + bh / 2 - ch / 2
        cells(ax, qx, qy, cw, ch, cap, high, t)
        full = high == cap
        color = t["fail"] if full else t["data"]
        mid = qx + cap * cw / 2
        label(ax, mid, qy + ch + 0.8, f"{qname}：容量 {cap}", color, ha="center", va="bottom",
              weight="bold" if full else "normal")
        label(ax, mid, y - 0.6, f"最高水位 {high}" + ("，到满" if full else "") + f"\n{count}", color,
              ha="center", va="top")
        x = qx + cap * cw
        arrow(ax, x + 0.2, y + bh / 2, x + g - 0.3, y + bh / 2, t["muted"])
        x += g
    label(ax, 0.5, 4.4, "蓝格子是长跑里排到过的最多帧数。门控只放过一成（37／366）；VLM 36 次、上传 35 次，"
          "每级少的 1 帧\n是停机时还留在队列里的。队列里传的是图片路径和元数据，不传像素", t["muted"])
    note(fig, t, "容量见 edge/src/main.cpp；每帧耗时是 24 帧端到端验收的均值（phase7_prompt2e_e2e_acceptance_report.md）；\n"
                 "节拍、帧数、水位是 30 分钟长跑（phase9_experiment_validation_release_gates.md、edge_run.log）")
    save(fig, "pipeline_queues", t_name, t)


# ---------------------------------------------------------------- 3. drop vs interval
# 扫频：results/phase8c_beat_sweep/phase8c_beat_sweep_results.csv，每帧都进 VLM（pass_all），
#   所以 VLM 收帧的间隔就是采集节拍；丢帧比例 = queue_drop_count ÷ frames_emitted_or_attempted
# 长跑：docs/experiments/phase9_experiment_validation_release_gates.md 第 60、64、66、83–85 行
SOAK_MIN, SOAK_FRAMES, SOAK_GATED, SOAK_VLM_MS = 30.2, 366, 37, 15419


def sweep_rows():
    with open(ROOT / "results/phase8c_beat_sweep/phase8c_beat_sweep_results.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    return [(int(r["beat_ms"]) / 1000, int(r["queue_drop_count"]), int(r["frames_emitted_or_attempted"]),
             int(r["avg_qwen3vl_ms"]) / 1000) for r in rows]


def fig_drop(t_name, t):
    rows = sweep_rows()
    stable = [v for _, drop, _, v in rows if drop <= 1]
    vlm_s = sum(stable) / len(stable)            # 没积压的三档里 VLM 处理一帧的平均时间，约 10.8 秒
    soak_interval = SOAK_MIN * 60 / SOAK_GATED    # 长跑里 VLM 平均约 49 秒收到一帧
    fig = plt.figure(figsize=(WIDTH_IN, 4.6))
    fig.patch.set_facecolor(t["surface"])
    titles(fig, t, "VLM 收帧的间隔比它处理一帧的时间长，就不丢帧",
           "最坏情况扫频（每帧都进 VLM）和 30 分钟长跑（门控后约 49 秒一帧）画在同一根轴上")
    ax = fig.add_axes([0.1, 0.2, 0.86, 0.6])
    style_axes(ax, t)
    ax.set_xscale("log")
    ax.set_xlim(4.2, 62)
    ax.set_ylim(-4, 64)
    ticks = [5, 6, 8, 10, 13, 15, 20, 30, 49]
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(v) for v in ticks])
    ax.minorticks_off()
    ax.set_xlabel("VLM 平均多久收到一帧（秒，对数轴）", color=t["ink2"], fontsize=SMALL)
    ax.set_ylabel("丢帧比例（%）", color=t["ink2"], fontsize=SMALL)
    ax.add_patch(Rectangle((4.2, -4), vlm_s - 4.2, 68, fc=t["fail_bg"], ec="none", alpha=0.6, zorder=0))
    ax.axvline(vlm_s, color=t["ink"], lw=1.1, ls=(0, (4, 2)), zorder=1)
    ax.text(vlm_s * 1.03, 60, f"VLM 处理一帧约 {vlm_s:.0f} 秒\n（扫频里没积压的三档）", fontsize=SMALL,
            color=t["ink"], va="top", linespacing=1.35)
    ax.text(4.45, 2, "送得比 VLM 快：\n队列积压，丢最旧", fontsize=SMALL, color=t["fail"], va="bottom",
            linespacing=1.35)
    ax.plot([r[0] for r in rows], [100 * r[1] / r[2] for r in rows], color=t["gray"], lw=1.2, zorder=2)
    for beat, drop, n, _ in rows:
        y = 100 * drop / n
        ax.scatter([beat], [y], s=34, color=t["fail"] if drop else t["gray"], zorder=3)
        left = drop == 1  # 10 秒那个点紧挨着虚线，标签放左边
        ax.text(beat * (0.97 if left else 1), y + (1 if left else 3.2), f"丢 {drop}/{n}" if drop else "0",
                ha="right" if left else "center", va="bottom", fontsize=SMALL - 0.5,
                color=t["fail"] if drop else t["muted"])
    ax.scatter([soak_interval], [0], s=80, color=t["good"], zorder=4)
    ax.annotate(f"30 分钟长跑：每 5 秒采一帧，\n门控只放过 {SOAK_GATED}/{SOAK_FRAMES}，\n"
                f"VLM 约 {soak_interval:.0f} 秒收一帧、\n处理一帧平均 {SOAK_VLM_MS / 1000:.1f} 秒，丢 0 帧",
                xy=(soak_interval, 0), xytext=(19.5, 22), fontsize=SMALL, color=t["good"], linespacing=1.35,
                arrowprops=dict(arrowstyle="-|>", color=t["good"], lw=1.1))
    note(fig, t, "扫频：results/phase8c_beat_sweep/phase8c_beat_sweep_results.csv，丢帧比例 = 丢帧数 ÷ 采集帧数，"
                 "每档跑 2–4 分钟。\n长跑：phase9_experiment_validation_release_gates.md；长跑的 VLM 耗时含视觉编码，"
                 "和扫频的口径不同")
    save(fig, "drop_vs_interval", t_name, t)


# ---------------------------------------------------------------- 4. FastSAM INT8
# zp、scale：docs/experiments/phase7_prompt2c_fastsam_edge_report.md 第 58 行（output0 [1,37,8400]，INT8）
# FP16 模型上置信度最高 0.8794：同一文件第 258 行
# 能表示的范围按 scale × (q − zp) 算，q 取 −128 到 127；框坐标是几百像素（输入 640）是推断
ZP, SCALE = -119, 2.820890
LO, HI = SCALE * (-128 - ZP), SCALE * (127 - ZP)
FP16_TOP1, THRESH = 0.8794, 0.25


def fig_fastsam(t_name, t):
    fig = plt.figure(figsize=(WIDTH_IN, 4.2))
    fig.patch.set_facecolor(t["surface"])
    titles(fig, t, "INT8 一格是 2.82，置信度的整个范围不到半格，全被舍成 0",
           "FastSAM 的 output0 按整个张量量化，范围要装下几百像素的框坐标")
    ax1 = fig.add_axes([0.06, 0.56, 0.9, 0.16])
    style_axes(ax1, t)
    ax1.barh(0, HI - LO, left=LO, height=0.5, color=t["gray_bg"], edgecolor=t["line"])
    ax1.barh(0, 640, left=0, height=0.5, color=t["data_bg"], edgecolor=t["data"])
    ax1.barh(0, 1, left=0, height=0.5, color=t["fail"])
    ax1.text(320, 0, "框坐标：几百像素（输入 640）", ha="center", va="center", color=t["data"], fontsize=10)
    ax1.annotate("置信度 0–1：在这个尺度上只是一条线", xy=(0.5, 0.25), xytext=(40, 0.62), color=t["fail"],
                 fontsize=SMALL, arrowprops=dict(arrowstyle="->", color=t["fail"], lw=1))
    ax1.text(HI, 0.42, f"INT8 能表示 {LO:.0f} 到 {HI:.0f}，共 256 格", ha="right", va="bottom",
             color=t["ink2"], fontsize=SMALL)
    ax1.set_xlim(LO - 15, HI + 15)
    ax1.set_ylim(-0.9, 0.9)
    ax1.set_yticks([])
    ax1.spines["left"].set_visible(False)
    ax1.set_xticks([0, 200, 400, 600])
    fig.text(0.06, 0.445, "放大到 0 附近：竖线是 INT8 能取到的值，相邻两格差 2.82；落在 ±1.41 之间的数都舍入到 0",
             fontsize=SMALL, color=t["ink2"])
    ax2 = fig.add_axes([0.06, 0.16, 0.9, 0.215])
    ax2.set_facecolor(t["surface"])
    half = SCALE / 2
    ax2.axvspan(-half, half, ymin=0.12, ymax=0.88, color=t["gray_bg"])
    ax2.text(-0.72, 0.7, "这一段\n都舍入到 0", ha="center", va="center", color=t["ink2"], fontsize=SMALL,
             linespacing=1.3)
    for v in [SCALE * k for k in range(-1, 3)]:
        ax2.axvline(v, color=t["ink"] if v == 0 else t["gray"], lw=1.6 if v == 0 else 1)
        ax2.text(v, 1.04, f"{v:.2f}", ha="center", va="bottom", fontsize=SMALL,
                 color=t["ink"] if v == 0 else t["ink2"])
    ax2.axvspan(0, 1, ymin=0.38, ymax=0.62, color=t["fail_bg"])
    ax2.text(0.5, 0.5, "置信度 0–1", ha="center", va="center", color=t["fail"], fontsize=SMALL)
    ax2.plot([FP16_TOP1], [0.2], marker="v", color=t["good"], ms=7)
    ax2.text(half + 0.15, 0.2, f"FP16 模型上置信度最高 {FP16_TOP1:.3f}，INT8 上它也被舍成 0", color=t["good"],
             fontsize=SMALL, va="center", bbox=dict(facecolor=t["surface"], edgecolor="none", pad=1.5))
    ax2.axvline(THRESH, ymin=0.0, ymax=0.3, color=t["compute"], lw=1.4)
    ax2.text(-0.15, 0.02, "阈值 0.25", color=t["compute"], fontsize=SMALL - 0.5, ha="right", va="bottom")
    ax2.set_xlim(-3.4, 6.2)
    ax2.set_ylim(-0.12, 1.0)
    ax2.set_xticks([])
    ax2.set_yticks([])
    for s in ax2.spines.values():
        s.set_visible(False)
    note(fig, t, "数据：docs/experiments/phase7_prompt2c_fastsam_edge_report.md 第 58、258 行；\n"
                 "可表示范围按 scale ×（q − zp）算出；坐标的量级是推断")
    save(fig, "fastsam_int8", t_name, t)


# ---------------------------------------------------------------- 5. dashboard screenshot
def screenshot():
    # docs/figures/前端/3.png：看板的单帧详情，数据是 YOLOv8n（ORT CPU）那次的导出记录。
    # 裁掉顶上的浏览器边和右侧的详情抽屉，只留图片、框和 JSON
    im = Image.open(ROOT / "docs/figures/前端/3.png").convert("RGB")
    im = im.crop((60, 26, 1592, im.height))
    im.thumbnail((1300, 1300), Image.LANCZOS)
    im.save(OUT / "dashboard_frame.jpg", quality=90, optimize=True)


if __name__ == "__main__":
    for name, theme in THEMES.items():
        for fn in (fig_arch, fig_pipeline, fig_drop, fig_fastsam):
            fn(name, theme)
    screenshot()
    print("wrote", len(list(OUT.glob("*.png")) + list(OUT.glob("*.jpg"))), "files to", OUT)
