#!/usr/bin/env python3
"""PDF 压缩工具 — 逐页渲染重建，保证内容完整清晰。

原理：pdftoppm 逐页渲染 → JPEG 压缩 → img2pdf 重新组装

依赖：pip install Pillow img2pdf pdf2image
系统：需要 poppler-utils (pdftoppm)
"""

import argparse
import io
import sys
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

LEVELS = {
    1: {"dpi": 96,  "quality": 85, "desc": "最佳画质 (~72%)"},
    2: {"dpi": 96,  "quality": 70, "desc": "清晰 (~79%)"},
    3: {"dpi": 72,  "quality": 70, "desc": "清晰可读 (~86%)"},
    4: {"dpi": 72,  "quality": 55, "desc": "紧凑可读 (~88%)"},
    5: {"dpi": 60,  "quality": 50, "desc": "极致压缩 (~91%)"},
    6: {"dpi": 50,  "quality": 40, "desc": "极限压缩 (~94%)"},
}


def compress_pdf(input_path: Path, output_path: Path, dpi: int, quality: int) -> dict:
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
        description="PDF 压缩工具 — 保证内容完整清晰，逐级压缩",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""级别说明:
  1  最佳画质  DPI=96  Q=85  (~72%% 压缩)
  2  清晰      DPI=96  Q=70  (~79%% 压缩)
  3  清晰可读  DPI=72  Q=70  (~86%% 压缩)
  4  紧凑可读  DPI=72  Q=55  (~88%% 压缩)
  5  极致压缩  DPI=60  Q=50  (~91%% 压缩)
  6  极限压缩  DPI=50  Q=40  (~94%% 压缩)

示例:
  %(prog)s -l 3 .                           压缩当前目录
  %(prog)s -l 3 二年级上册unit3-4.pdf       压缩单个文件
  %(prog)s --dpi 80 --quality 60 .          自定义参数
""",
    )
    parser.add_argument("input", help="PDF 文件或目录")
    parser.add_argument("-o", "--output", help="输出路径（文件或目录）")
    parser.add_argument("-l", "--level", type=int, default=5, choices=[1, 2, 3, 4, 5, 6],
                        help="压缩级别 1-6（默认: 5）")
    parser.add_argument("--dpi", type=int, help="渲染分辨率（覆盖级别默认值）")
    parser.add_argument("--quality", type=int, help="JPEG 质量 1-100（覆盖级别默认值）")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    cfg = LEVELS[args.level]
    dpi = args.dpi if args.dpi else cfg["dpi"]
    quality = args.quality if args.quality else cfg["quality"]
    dpi = max(50, min(300, dpi))
    quality = max(1, min(100, quality))

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

    print(f"Level {args.level} ({cfg['desc']}) | DPI={dpi} Q={quality}")
    print(f"找到 {len(pdf_files)} 个 PDF 文件\n")
    print(f"{'文件':<45} {'原始':>10} {'压缩后':>10} {'缩减':>8}")
    print("-" * 77)

    total_original = 0
    total_compressed = 0
    saved_count = 0

    for pdf_file, output_file in zip(pdf_files, outputs):
        try:
            result = compress_pdf(pdf_file, output_file, dpi=dpi, quality=quality)
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
