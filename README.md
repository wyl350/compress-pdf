# todos



# compress-pdf

基于逐页渲染重建的 PDF 压缩工具，保证内容完整清晰。

## 原理

1. `pdftoppm` 将 PDF 逐页渲染为图片
2. Pillow 将图片转为 JPEG 并压缩
3. `img2pdf` 将 JPEG 重新组装为 PDF

不破坏 PDF 内部结构，文字可复制，排版不变。

## 安装

### 系统依赖

```bash
# Debian/Ubuntu
sudo apt install poppler-utils

# macOS
brew install poppler
```

### Python 包管理工具

```bash
# 安装 uv
export ALl_PROXY=socks5h://127.0.0.1:1080
export all_proxy=socks5h://127.0.0.1:1080
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Python 依赖

```bash
uv sync
```

或手动安装：

```bash
uv pip install Pillow img2pdf pdf2image
```

## 用法

```bash
# 压缩单个文件
compress-pdf file.pdf

# 压缩整个目录
compress-pdf /path/to/pdfs/

# 指定输出路径
compress-pdf file.pdf -o compressed.pdf
compress-pdf ./pdfs/ -o ./output/

# 使用压缩级别
compress-pdf -l 3 file.pdf

# 自定义参数
compress-pdf --dpi 80 --quality 60 file.pdf
```

## 压缩级别

| 级别 | DPI | Quality | 压缩率 | 说明 |
|------|-----|---------|--------|------|
| 1 | 96 | 85 | ~72% | 最佳画质 |
| 2 | 96 | 70 | ~79% | 清晰 |
| 3 | 72 | 70 | ~86% | 清晰可读 |
| 4 | 72 | 55 | ~88% | 紧凑可读 |
| 5 | 60 | 50 | ~91% | 极致压缩 |
| 6 | 50 | 40 | ~94% | 极限压缩 |

## 作为库使用

```python
from compress_pdf import compress_pdf, LEVELS
from pathlib import Path

result = compress_pdf(
    input_path=Path("input.pdf"),
    output_path=Path("output.pdf"),
    dpi=72,
    quality=70,
)

print(f"压缩率: {result['ratio']:.1f}%")
```

## License

MIT
