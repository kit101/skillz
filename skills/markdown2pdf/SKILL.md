---
name: markdown2pdf
description: Convert Markdown files to PDF with Chinese formatting, LaTeX math formulas, and embedded images. Use this skill whenever the user wants to turn a .md file into a PDF document, especially when the Markdown contains Chinese text, math formulas ($$ or $), tables, or images. Triggers include:"md转pdf", "markdown to pdf", "导出pdf", "生成pdf", "convert md to pdf", "转为pdf", or when the user mentions a .md file and asks to make it a PDF.
---

# MD to PDF Converter

Convert Markdown files to professional PDF documents using pandoc + xelatex, with proper Chinese rendering, LaTeX math formula support, and image embedding.

## Prerequisites

The conversion requires:
- **pandoc** (usually pre-installed)
- **BasicTeX** (lightweight LaTeX, ~100MB, includes xelatex + ctex for Chinese)

Verify tools are available before conversion. If any are missing, tell the user how to install and ask before executing:

```bash
export PATH="/Library/TeX/texbin:$PATH"
which pandoc xelatex
kpsewhich ctexart.cls  # verify ctex Chinese support
```

- If **BasicTeX** not installed: `brew install --cask basictex` (~100MB, includes xelatex + ctex)
- If **ctex** missing: `sudo tlmgr install ctex`

On macOS, `/Library/TeX/texbin` must be in PATH for xelatex to be found (BasicTeX installs here but doesn't add it automatically).

## Conversion Workflow

### Step 1: Read the Markdown file

Always read the full file first to understand:
- Document structure (headings, sections)
- Image references and their paths
- Math formula syntax (`$inline$`, `$$block$$`)
- Whether headings already have manual numbering (一、二、三 or （一）（二）)

### Step 2: Pre-conversion fixes

There are two critical pre-conversion checks. Apply fixes BEFORE running pandoc.

#### Fix 1: HTML `<figure>` images → Markdown syntax

Pandoc's LaTeX writer discards raw HTML `<figure>` blocks. Images inside `<figure>` tags will be silently dropped from the PDF. Convert them to standard Markdown image syntax first.

**Pattern to detect:**
```html
<figure>
  <img src="path/to/image.png" alt="description">
  <figcaption align="center">图 1 description</figcaption>
</figure>
```

**Convert to:**
```markdown
![图 1 description](path/to/image.png)
```

Use this Python one-liner to batch-convert all figures in a file:

```python
import re
with open("input.md", "r", encoding="utf-8") as f:
    content = f.read()

def replace_figure(match):
    block = match.group(0)
    src = re.search(r'<img[^>]*src="([^"]*)"', block)
    cap = re.search(r'<figcaption[^>]*>(.*?)</figcaption>', block)
    if src and cap:
        return f'\n![{cap.group(1).strip()}]({src.group(1)})\n'
    return block

content = re.sub(r'<figure>.*?</figure>', replace_figure, content, flags=re.DOTALL)

with open("input_fixed.md", "w", encoding="utf-8") as f:
    f.write(content)
```

After conversion, verify:
- Count of `![` matches number of original images
- No residual `<figure>` tags remain

#### Fix 2: Avoid duplicate section numbering

If the Markdown headings already contain manual Chinese numbering (一、二、三…, （一）（二）…, 1. 2. 3.…), LaTeX's automatic section numbering will create duplicates like "1 一、…" or "1.1 （一）…".

**Solution**: Add `-V secnumdepth=0` to the pandoc command (see Step 3). This completely disables LaTeX auto-numbering while preserving manual numbers from the Markdown.

Note: `--number-sections` / `-N` flag must NOT be used if headings have manual numbering.

### Step 3: Run pandoc conversion

```bash
# Ensure xelatex is on PATH
export PATH="/Library/TeX/texbin:$PATH"

# Run from the directory containing the .md file (important for relative image paths)
cd /path/to/markdown/directory

pandoc "input.md" \
  -o "output.pdf" \
  --pdf-engine=xelatex \
  --from=markdown+tex_math_dollars+raw_tex \
  --resource-path="." \
  --toc --toc-depth=2 \
  -V documentclass=ctexart \
  -V classoption=12pt \
  -V "geometry:margin=2.5cm" \
  -V secnumdepth=0 \
  --standalone \
  -H <(cat <<'EOF'
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[R]{\leftmark}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0.4pt}
EOF
  )
```

**Key parameters explained:**

| Parameter | Purpose |
|-----------|---------|
| `--pdf-engine=xelatex` | Use XeLaTeX for Unicode/CJK support |
| `--from=markdown+tex_math_dollars` | Parse `$...$` and `$$...$$` as LaTeX math |
| `--resource-path="."` | Resolve relative image paths from current directory |
| `--toc --toc-depth=2` | Generate table of contents (depth 2 = sections + subsections) |
| `-V documentclass=ctexart` | Chinese-friendly document class (provides ctex, xeCJK) |
| `-V secnumdepth=0` | **Disable all automatic section numbering** |
| `--standalone` | Produce complete document with preamble |
| `-V geometry:margin=2.5cm` | Page margins (adjustable) |
| `-H ...` | Inject LaTeX header for page layout: section title top-right, page number centered footer |

**When headings do NOT have manual numbering**: remove `-V secnumdepth=0` and add `--number-sections` if you want auto-numbering.

**To disable TOC**: remove `--toc --toc-depth=2`.

**To customize page layout**: adjust the `-H` heredoc. Common tweaks:
- Remove header entirely: delete the `\fancyhead[R]{\leftmark}` line
- Left-align header: change `[R]` to `[L]`
- Add header rule: `\renewcommand{\headrulewidth}{0.4pt}` (remove line to hide rule)
- Adjust toc depth: change `--toc-depth=2` (1 = sections only, 3 = sub-subsections)

### Step 4: Verify the output

Check that images are actually embedded (not silently dropped):

```bash
ls -lh output.pdf
# File size should be roughly: text size + sum of image sizes
# If PDF is suspiciously small (e.g., 300KB with 5MB of images), images were dropped
```

Quick verification:
```bash
# Check for image-related LaTeX commands in intermediate .tex
pandoc input.md -o check.tex --from=markdown+tex_math_dollars --standalone
grep -c "includegraphics" check.tex  # should match number of images
```

### Step 5: Clean up

Remove intermediate files if any were generated (`.tex`, `_fixed.md`).

## Common Issues

### Images not appearing in PDF
- **Cause**: HTML `<figure>` blocks were stripped by pandoc
- **Fix**: Apply Step 2 Fix 1 to convert to `![caption](path)` syntax
- **Also check**: Run pandoc from the directory containing the .md file so relative image paths resolve correctly. Use `--resource-path="."` 

### Duplicate heading numbers (e.g., "1 一、概述", "1.1 （一）背景")
- **Cause**: LaTeX auto-numbering layered on top of manual numbering
- **Fix**: Add `-V secnumdepth=0` and remove `--number-sections` / `-N`

### "xelatex not found" error
- **Cause**: BasicTeX is installed but `/Library/TeX/texbin` is not in PATH
- **Fix**: Add `export PATH="/Library/TeX/texbin:$PATH"` before running pandoc. Inform the user and ask whether to proceed.

### "ctexart.cls not found" error
- **Cause**: ctex package not installed
- **Fix**: Tell the user to run `sudo tlmgr install ctex` (or `brew reinstall --cask basictex`). Ask whether to execute the install before running it.

### Chinese characters showing as tofu (□□□)
- **Cause**: Wrong PDF engine (pdflatex instead of xelatex)
- **Fix**: Ensure `--pdf-engine=xelatex` is used

### Math formulas not rendering
- **Cause**: Missing `tex_math_dollars` extension
- **Fix**: Use `--from=markdown+tex_math_dollars`

### Image paths with Chinese characters
- XeLaTeX handles Unicode paths well; no special encoding needed
- Ensure paths are relative to the markdown file location

### "Undefined control sequence \lt" (or \gt) error
- **Cause**: Raw LaTeX `\lt` / `\gt` in math blocks may not be defined in xelatex + unicode-math (loaded by ctex)
- **Fix**: Replace `\lt` with `<` and `\gt` with `>` in the markdown source before conversion

### Chinese characters missing in math formulas (□□□ or blank)
- **Cause**: Chinese text inside `$$...$$` or `$...$` blocks uses the math font (latinmodern-math.otf) which lacks CJK glyphs; xelatex will emit `Missing character` warnings
- **Fix**: Wrap Chinese text inside math blocks with `\text{...}`, e.g. `$$ z_i = 0, \text{当} ... $$`
