#!/usr/bin/env python3
"""PDF 压缩工具 — 两种模式，清晰与体积兼得。

模式:
  raster  — 逐页渲染重建（原方式），适合扫描件
  vector  — Ghostscript 优化，保留向量文字，文字永远清晰（推荐）

依赖：pip install Pillow img2pdf pdf2image
系统：需要 poppler-utils (pdftoppm) 和 ghostscript (gs)
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from pdf2image import convert_from_path
except ImportError:
    print("请先安装依赖：pip install pdf2image")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("请先安装依赖：pip install Pillow")
    sys.exit(1)

try:
    import img2pdf
except ImportError:
    print("请先安装依赖：pip install img2pdf")
    sys.exit(1)

# ── Ghostscript 预设 ──────────────────────────────────────────────
GS_LEVELS = {
    1: {"pdfsettings": "/prepress", "dpi": 300, "desc": "印刷品质 (300dpi)"},
    2: {"pdfsettings": "/printer",  "dpi": 300, "desc": "打印品质 (300dpi)"},
    3: {"pdfsettings": "/ebook",    "dpi": 150, "desc": "电子书 (150dpi)"},
    4: {"pdfsettings": "/screen",   "dpi": 120, "desc": "屏幕显示 (120dpi)"},
    5: {"pdfsettings": "/screen",   "dpi": 90,  "desc": "清晰浏览 (90dpi)"},
    6: {"pdfsettings": "/screen",   "dpi": 60,  "desc": "紧凑压缩 (60dpi)"},
    7: {"pdfsettings": "/screen",   "dpi": 50,  "desc": "极限压缩 (50dpi)"},
}

# ── 光栅模式预设（原方式）─────────────────────────────────────────
RASTER_LEVELS = {
    1: {"dpi": 96,  "quality": 85, "desc": "最佳画质 (~72%)"},
    2: {"dpi": 96,  "quality": 70, "desc": "清晰 (~79%)"},
    3: {"dpi": 72,  "quality": 70, "desc": "清晰可读 (~86%)"},
    4: {"dpi": 72,  "quality": 55, "desc": "紧凑可读 (~88%)"},
    5: {"dpi": 60,  "quality": 50, "desc": "极致压缩 (~91%)"},
    6: {"dpi": 50,  "quality": 40, "desc": "极限压缩 (~94%)"},
}


def _check_gs():
    if not shutil.which("gs"):
        print("错误：未找到 Ghostscript，请安装：sudo apt install ghostscript")
        sys.exit(1)


def compress_vector(input_path: Path, output_path: Path, pdfsettings: str, dpi: int = 150) -> dict:
    """Ghostscript 向量压缩 — 保留文字，只压图片和冗余数据。"""
    original_size = input_path.stat().st_size
    cmd = [
        "gs",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={pdfsettings}",
        "-dNOPAUSE",
        "-dBATCH",
        "-dQUIET",
        "-dColorImageDownsampleType=/Bicubic",
        f"-dColorImageResolution={dpi}",
        "-dGrayImageDownsampleType=/Bicubic",
        f"-dGrayImageResolution={dpi}",
        "-dMonoImageDownsampleType=/Bicubic",
        f"-dMonoImageResolution={dpi}",
        "-sOutputFile=" + str(output_path),
        str(input_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            return {"original": original_size, "compressed": original_size,
                    "ratio": 0.0, "error": result.stderr.strip() or "gs failed"}
    except subprocess.TimeoutExpired:
        return {"original": original_size, "compressed": original_size,
                "ratio": 0.0, "error": "gs timeout (300s)"}

    compressed_size = output_path.stat().st_size if output_path.exists() else original_size
    ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
    return {"original": original_size, "compressed": compressed_size,
            "ratio": ratio, "error": None}


def compress_raster(input_path: Path, output_path: Path, dpi: int, quality: int) -> dict:
    """光栅模式 — 逐页渲染重建（扫描件适合）。"""
    import io

    original_size = input_path.stat().st_size
    try:
        imgs = convert_from_path(str(input_path), dpi=dpi)
    except Exception as e:
        return {"original": original_size, "compressed": original_size,
                "ratio": 0.0, "error": str(e)}

    if not imgs:
        return {"original": original_size, "compressed": original_size,
                "ratio": 0.0, "error": "no pages"}

    jpeg_list = []
    for img in imgs:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        jpeg_list.append(buf.getvalue())

    try:
        output_path.write_bytes(img2pdf.convert(jpeg_list))
    except Exception as e:
        return {"original": original_size, "compressed": original_size,
                "ratio": 0.0, "error": str(e)}

    compressed_size = output_path.stat().st_size if output_path.exists() else original_size
    ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
    return {"original": original_size, "compressed": compressed_size,
            "ratio": ratio, "error": None}


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


def build_parser():
    parser = argparse.ArgumentParser(
        description="PDF 压缩工具 — vector 模式保留向量文字，清晰不糊",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""模式说明:
  vector  推荐！Ghostscript 优化，文字保持向量，永远清晰锐利
  raster  逐页渲染为图片再组装，适合扫描件

vector 级别:
  1  印刷品质  /prepress  (300dpi)
  2  打印品质  /printer   (300dpi)
  3  电子书    /ebook     (150dpi)  ← 推荐
  4  屏幕显示  /screen    (120dpi)
  5  清晰浏览  /screen    (90dpi)
  6  紧凑压缩  /screen    (60dpi)
  7  极限压缩  /screen    (50dpi)

raster 级别:
  1  最佳画质  DPI=96  Q=85
  2  清晰      DPI=96  Q=70
  3  清晰可读  DPI=72  Q=70
  4  紧凑可读  DPI=72  Q=55
  5  极致压缩  DPI=60  Q=50
  6  极限压缩  DPI=50  Q=40

示例:
  %(prog)s input.pdf                          vector 模式，默认 ebook
  %(prog)s -m vector -l 3 input.pdf           vector 模式 ebook
  %(prog)s -m raster -l 5 input.pdf           raster 模式极致压缩
  %(prog)s -m vector -l 3 .                   批量压缩当前目录
""",
    )
    parser.add_argument("input", help="PDF 文件或目录")
    parser.add_argument("-o", "--output", help="输出路径（文件或目录）")
    parser.add_argument("-m", "--mode", choices=["vector", "raster"], default="vector",
                        help="压缩模式: vector（推荐）或 raster（默认: vector）")
    parser.add_argument("-l", "--level", type=int, default=5,
                        help="压缩级别（vector: 1-7, raster: 1-6, 默认: 5）")
    parser.add_argument("--dpi", type=int, help="raster 模式: 渲染分辨率（覆盖级别默认值）")
    parser.add_argument("--quality", type=int, help="raster 模式: JPEG 质量 1-100（覆盖级别默认值）")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "vector":
        _check_gs()
        if args.level < 1 or args.level > 7:
            print("vector 模式级别范围: 1-7")
            sys.exit(1)
        cfg = GS_LEVELS[args.level]
        pdfsettings = cfg["pdfsettings"]
        gs_dpi = cfg["dpi"]
        mode_label = f"vector {cfg['desc']} {pdfsettings}"
    else:
        if args.level < 1 or args.level > 6:
            print("raster 模式级别范围: 1-6")
            sys.exit(1)
        cfg = RASTER_LEVELS[args.level]
        dpi = args.dpi if args.dpi else cfg["dpi"]
        quality = args.quality if args.quality else cfg["quality"]
        dpi = max(50, min(300, dpi))
        quality = max(1, min(100, quality))
        mode_label = f"raster {cfg['desc']} DPI={dpi} Q={quality}"

    input_arg = Path(args.input)

    if input_arg.is_file() and input_arg.suffix.lower() == ".pdf":
        pdf_files = [input_arg]
        if args.output:
            output_arg = Path(args.output)
            if output_arg.suffix.lower() == ".pdf":
                outputs = [output_arg]
            else:
                output_arg.mkdir(parents=True, exist_ok=True)
                outputs = [output_arg / input_arg.name]
        else:
            outputs = [input_arg.parent / f"{input_arg.stem}_compressed{input_arg.suffix}"]
    elif input_arg.is_dir():
        pdf_files = sorted(input_arg.glob("**/*.pdf"))
        if not pdf_files:
            print(f"未找到 PDF 文件：{input_arg}")
            sys.exit(1)
        if args.output:
            output_dir = Path(args.output)
        else:
            output_dir = input_arg.parent / f"{input_arg.name}_compressed"
        output_dir.mkdir(parents=True, exist_ok=True)
        outputs = [output_dir / pdf.name for pdf in pdf_files]
    else:
        print(f"无效的输入：{input_arg}")
        sys.exit(1)

    print(f"模式: {args.mode} | {mode_label}")
    print(f"找到 {len(pdf_files)} 个 PDF 文件\n")
    print(f"{'文件':<45} {'原始':>10} {'压缩后':>10} {'缩减':>8}")
    print("-" * 77)

    total_original = 0
    total_compressed = 0
    saved_count = 0

    for pdf_file, output_file in zip(pdf_files, outputs):
        try:
            if args.mode == "vector":
                result = compress_vector(pdf_file, output_file, pdfsettings, gs_dpi)
            else:
                result = compress_raster(pdf_file, output_file, dpi, quality)

            total_original += result["original"]
            total_compressed += result["compressed"]
            if result["ratio"] > 0:
                saved_count += 1

            name = pdf_file.name
            if len(name) > 42:
                name = name[:39] + "..."

            error = result.get("error")
            if error:
                print(f"{name:<45} 错误：{error}")
            else:
                print(
                    f"{name:<45} "
                    f"{format_size(result['original']):>10} "
                    f"{format_size(result['compressed']):>10} "
                    f"{result['ratio']:>6.1f}%"
                )
        except Exception as e:
            print(f"{pdf_file.name:<45} 错误：{e}")

    if len(pdf_files) > 1:
        total_ratio = (1 - total_compressed / total_original) * 100 if total_original > 0 else 0
        print("-" * 77)
        print(
            f"{'合计':<45} "
            f"{format_size(total_original):>10} "
            f"{format_size(total_compressed):>10} "
            f"{total_ratio:>6.1f}%"
        )
        print(f"\n共 {len(pdf_files)} 个文件，{saved_count} 个成功缩小")


if __name__ == "__main__":
    main()
