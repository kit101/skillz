---
name: paper2markdown
description: |
  Convert academic papers, theses, and technical documents from .docx to clean Markdown
  with proper LaTeX formulas, equation numbering, figures, and tables. Triggers when the
  user mentions converting a .docx paper/thesis/document to Markdown, extracting formulas
  from Word to LaTeX, or cleaning up pandoc-generated Markdown with formula artifacts.
  Also trigger when user says "docx转md", "word转markdown", "论文转markdown",
  "公式转latex", or mentions pandoc output has broken/escaped formulas.
---

# Paper to Markdown

Convert academic papers (.docx) to clean, publication-ready Markdown with proper
LaTeX formulas, equation numbering, figures, and tables.

## Output Convention

Given source file `<name>.docx`, output is:

```
<name>.md              # Clean Markdown output
<name>.artifacts/      # Extracted images and media
├── image1.name.png
├── image2.name.png
└── ...
```

All commands below use `INPUT=<name>.docx` and `OUTPUT=<name>` as placeholders.

## Dependencies

This skill works standalone (using Python `zipfile` for XML access) but benefits from
[docx skill](../docx/SKILL.md) for reliable XML analysis and image extraction:

| Scenario | With docx skill | Standalone fallback |
|----------|----------------|--------------------|
| Unpack & read XML | `python {docx-skill}/scripts/office/unpack.py INPUT unpacked/` | `zipfile.ZipFile(INPUT).read('word/document.xml')` |
| Image relationship check | Inspect `word/_rels/document.xml.rels` for orphan images | Parse rels XML via `zipfile` |
| Tracked changes | `pandoc --track-changes=all` | Same (pandoc handles it) |

## Workflow Overview

```
.docx → pandoc extraction → formula detection → formula cleanup →
table conversion → figure handling → equation numbering → final polish
```

> **Important**: The formula source may be OMML/MathType (producing pandoc escape
> artifacts) OR plain Unicode text with no escaping. Detect which case you're in
> before choosing cleanup strategy (see Phase 2).

## Phase 1: Initial Pandoc Conversion

```bash
# Set variables
INPUT="model.docx"
OUTPUT="model"

# Convert docx to raw Markdown
pandoc "$INPUT" -t markdown --wrap=none -o "$OUTPUT.raw.md"
```

This produces raw Markdown with potential escaping artifacts. Do NOT use
`+tex_math_dollars` — equations in .docx are OMML/MathType, not native LaTeX,
so it has no effect.

**Also extract images** (even if pandoc fails, try manual unzip):

```bash
# Attempt pandoc extraction
mkdir -p "$OUTPUT.artifacts"
pandoc "$INPUT" --extract-media="$OUTPUT.artifacts" -t markdown --wrap=none -o /dev/null

# If pandoc produced no files, manually unzip
if [ -z "$(ls -A $OUTPUT.artifacts 2>/dev/null)" ]; then
  unzip -o "$INPUT" "word/media/*" -d "$OUTPUT.artifacts/"
  mv "$OUTPUT.artifacts/word/media/"* "$OUTPUT.artifacts/" 2>/dev/null
  rm -rf "$OUTPUT.artifacts/word"
fi

# Move pandoc's media subdirectory up if needed
mv "$OUTPUT.artifacts/media/"* "$OUTPUT.artifacts/" 2>/dev/null
rmdir "$OUTPUT.artifacts/media" 2>/dev/null
```

## Phase 2: Formula Detection & Cleanup (LLM-driven)

### Step 0: Detect formula source type

Check the raw Markdown for formula encoding. Not all papers use OMML/MathType —
many Chinese academic papers have formulas as **plain Unicode text** with no LaTeX
escaping at all.

```bash
# Check for OMML/MathType artifacts
grep -c '\\\[' "$OUTPUT.raw.md"    # count display math escapes
grep -c '\\\$' "$OUTPUT.raw.md"    # count inline math escapes

# Check for Unicode math symbols (plain text formulas)
grep -c '[∑∏∫∂ΔΓΘΩαβγ]' "$OUTPUT.raw.md"
```

| Detection result | Cleanup strategy |
|-----------------|-----------------|
| Many `\[` / `\$` | Fix pandoc escaping artifacts (OMML path below) |
| Many Unicode math, no `\[` | Convert Unicode → LaTeX, wrap in `$...$`/`$$...$$` (Unicode path) |
| Mixed | Process OMML artifacts first, then convert remaining Unicode |

### OMML/MathType cleanup

#### Fix patterns

| Pandoc output | Correct LaTeX | Notes |
|---|---|---|
| `\\[ ... \\]` | `$$ ... $$` | Display math |
| `\$ ... \$`  | `$ ... $` | Inline math |
| `{{X}_{y}}` | `X_{y}` | Double braces → single |
| `{{X}\_{y}}` | `X_{y}` | Escaped underscore in braces |
| `\~X` | `\tilde{X}` | Tilde commands |
| `\~{{X}_{y}}` | `\tilde{X}_{y}` | Combined pattern |
| `\\frac`, `\\sum`, `\\max`, `\\min` | `\frac`, `\sum`, `\max`, `\min` | Double backslash → single |
| `\\left{ ... \\right}` | `\{ ... \}` or `\left\{ ... \right\}` | Brace escaping |
| `\\text{ }` | `\;` or remove | Excess spacing |
| `\\begin{aligned}` etc. | `\begin{aligned}` | Environment commands |

#### Special cases (OMML)

- **`.wmf` formula images**: Inline variables rendered as images in Word.
  Convert to inline LaTeX: `$t$`, `$r$`, etc. Remove `.wmf` files after conversion.
- **`\mathcal`, `\mathbb`, `\mathbf`**: Preserve as-is
- **`\text{...}` with Chinese**: Preserve and fix spacing
- **`\begin{cases}`**: Ensure proper syntax with `\text{}` for Chinese labels
- **Braces with Chinese**: `\left\{ ... \right\}` → `\{ ... \}` for simpler cases

#### Verification (OMML path)

- All `\tilde`, `\hat`, `\bar` commands work
- Subscripts/superscripts: `X_{i,j}` not `{{X}_{i,j}}`
- Fractions: `\frac{a}{b}` not `\\frac{a}{b}`
- No stray `\text{ }` blocks
- All `$$ ... $$` pairs are properly closed

### Unicode plain-text cleanup

When formulas are plain Unicode (common in Chinese academic .docx), the task is:
convert symbols to LaTeX AND wrap in `$...$` or `$$...$$`.

#### Step 1: Classify display vs inline

Display formulas (wrap in `$$...$$`):
- Stand on their own line, separated by blank lines
- Contain `=` or advanced operators
- Usually followed by "其中，" or "该式用于" explanatory paragraph
- Short (< 80 chars)

Inline formulas (wrap in `$...$`):
- Appear within running text paragraphs
- Single variables with sub/superscripts: `A^{0}`, `X^{M}`, `a_{i}`
- Function calls: `F(·)`, `F(A^{0})`

#### Step 2: Convert Unicode → LaTeX

| Unicode | LaTeX | Unicode | LaTeX |
|---------|-------|---------|-------|
| Γ | `\Gamma` | Δ | `\Delta` |
| Ω | `\Omega` | θ | `\theta` |
| ε | `\varepsilon` | η | `\eta` |
| ∑ | `\sum` | ∏ | `\prod` |
| ∂ | `\partial` | ∞ | `\infty` |
| ≤ | `\leq` | ≥ | `\geq` |
| ∈ | `\in` | → | `\rightarrow` |
| · | `\cdot` | × | `\times` |

#### Step 3: Merge fragmented inline math

After individual variable wrapping, scan for adjacent `$...$` blocks that should be
one expression. Merge patterns like:
- `F($A^{0}$)` → `$F(A^{0})$`
- `$P_{i}($x_{i}$)$` → `$P_{i}(x_{i})$`
- `$a_{i}$^{E}` → `$a_{i}^{E}$`

#### Critical: brace escaping order

When formulas contain both set notation `{a, b}` (needs `\{`, `\}`) AND LaTeX groups
`^{X}` (needs `{`, `}`), the order matters:

```
1. Fix pandoc escapes (\^0 → ^{0}, \_i → _{i})     # now has { and }
2. Protect ^{...} and _{...} groups (mark as safe)    # these { } must survive
3. Escape remaining { } → \{ \}                      # set notation braces
4. Restore protected groups
```

**NEVER** globally `replace('{','\\{')` after step 1 — it destroys LaTeX group braces.

#### Verification (Unicode path)

- All display formulas use `$$...$$`, all inline use `$...$`
- No bare Unicode math symbols left in prose (Γ, Δ, ∈, etc.)
- No bare superscripts like `A^{0}` without `$` wrapping
- No fragmented patterns like `F($A^{0}$)`
- `$$` and `$` pairs are balanced
- Formula numbering is sequential

## Phase 3: Table Conversion

Pandoc may output tables as grid tables (ASCII art with `+`/`-`/`|` separators).
Convert ALL tables to standard Markdown pipe-table format:

```markdown
| Column A | Column B | Column C |
|----------|----------|----------|
| Value 1  | Value 2  | Value 3  |
```

- Preserve inline LaTeX within table cells: `$Y_t$`, `$\Delta \tilde{Y}_t$`
- Align columns with dashes: `|---|` for header separator
- Remove pandoc grid-table artifacts. If automatic parsing fails, manually
  reconstruct the table from the raw text — the LLM should read column alignment
  from the dashed separator lines.

## Phase 4: Figure Handling

Images should already be extracted to `$OUTPUT.artifacts/` from Phase 1.

### Identify orphan images

Not all files in `word/media/` are referenced in the document. Check:

```bash
python3 -c "
import zipfile, re
with zipfile.ZipFile('$INPUT') as z:
    doc = z.read('word/document.xml').decode()
    rels = z.read('word/_rels/document.xml.rels').decode()
    # Find image rIds in relationships
    img_rids = set(re.findall(r'Id=\"(rId\d+)\".*?Target=\"media/', rels))
    # Find rIds actually referenced in document body
    used_rids = set(re.findall(r'r:embed=\"(rId\d+)\"', doc))
    orphan = img_rids - used_rids
    if orphan:
        print(f'Orphan images (not referenced): {orphan}')
"
```

Delete orphan images from `$OUTPUT.artifacts/` if confirmed.

### Clean up

1. **Remove formula images** (`.wmf` files): These are inline formulas rendered as
   images in Word. Convert to LaTeX inline (`$...$`), then delete the `.wmf` file.
2. **Keep figure images** (`.png`, `.jpg`): Actual charts, diagrams, screenshots.

### Rename for clarity

Rename figures to `imageN.figure_name.png` format, matching the Word internal
sequence number. Remove spaces from filenames (they break Markdown URLs):

```bash
cd "$OUTPUT.artifacts"
for f in *.png; do mv "$f" "$(echo $f | sed 's/ //g')"; done
```

### Use `<figure>` for semantics

Replace plain `![alt](path)` with HTML `<figure>` elements:

```html
<figure>
  <img src="./模型.artifacts/image3.图1持续改善型.png" alt="持续改善型">
  <figcaption align="center">图 1 持续改善型</figcaption>
</figure>
```

- Use relative paths: `./$OUTPUT.artifacts/imageN.name.png`
- `alt` text: remove "图N " prefix, keep only the descriptive name
- `<figcaption>`: keep the full "图 N 名称" with `align="center"`
- Remove pandoc `{width="..." height="..."}` attributes

### Image numbering

Word internal image numbering may skip numbers (formula images are also numbered).
The actual figure images will have gaps in their sequence. Options:
- **Keep original numbering** if image filenames must match cross-references
- **Renumber to match figure sequence** (图1 → image1, 图2 → image2, ...)
  if the document doesn't reference images by number internally

Ask the user which approach they prefer, or default to renumbering for clarity.

## Phase 5: Equation Numbering

Word stores equation numbers as `SEQ MTEqn` field codes, which pandoc cannot
preserve. Since the numbering is sequential, recover it:

### Detect numbering in original

```bash
python3 -c "
import re
with open('unpacked/word/document.xml') as f:
    xml = f.read()
count = xml.count('SEQ MTEqn \\\\h')  # formula markers
print(f'Formulas: {count}')
"
```

### Add numbers to Markdown

Append `\qquad (N)` before the closing `$$` of each display formula.
This format works across ALL Markdown renderers (GitHub, MathJax, KaTeX).

```latex
$$ z_{m,t} = \frac{x_{m,t} - \min x_{m,t}}{\max x_{m,t} - \min x_{m,t} + \varepsilon} \qquad (1) $$
```

### Rules

- Only number **display** formulas (`$$...$$`), not inline (`$...$`)
- If a formula appears in an overview/intro paragraph without a number in the
  original, leave it unnumbered
- Use sequential numbering (1, 2, 3, ...)
- For `\begin{aligned}`, `\begin{cases}` etc., place `\qquad (N)` on the
  last line before `\end{...}`

### Batch numbering with Perl

```bash
perl -i -0777 -pe '
  my $n = 0;
  s{(\$\$)(.+?)(\$\$)}{
    $n++;
    if ($2 =~ /\\tag\{/ || $2 =~ /\\qquad\s*\(/) {
      "$1$2$3";
    } else {
      "$1$2 \\qquad ($n)$3";
    }
  }gse;
' "$OUTPUT.md"
```

WARNING: If you need to skip a formula, do it BEFORE batch numbering, then renumber
all formulas after the skip point.

## Phase 6: Final Polish

### Balance verification

```bash
# Check $$ and $ pairs are balanced
python3 -c "
import re
text = open('$OUTPUT.md').read()
dd = text.count('\$\$')
s = re.sub(r'\$\$.*?\$\$', '', text, flags=re.DOTALL).count('\$')
print(f'\$\$: {dd} (even={dd%2==0})  single \$: {s} (even={s%2==0})')
eqns = re.findall(r'\\\\qquad \((\d+)\)', text)
print(f'Equations numbered: {len(eqns)}, range: {eqns[0]}-{eqns[-1] if eqns else 0}')
"
```

### Remove pandoc artifacts
- Delete `{width="..." height="..."}` from image references
- Remove empty paragraphs created by pandoc
- Fix `\[` `\]` → `[` `]` inside `$$...$$` blocks (pandoc may escape brackets)

### Verify completeness
- All `$$...$$` pairs are balanced
- All formulas have correct LaTeX syntax
- Image paths match disk files (no spaces, relative paths)
- `grep -c '\\qquad (' "$OUTPUT.md"` matches expected formula count

## Common Pitfalls

1. **Brace escaping order**: Global `replace('{','\\{')` after `fix_escapes`
   destroys LaTeX group braces `^{X}` → `^\{X\}`. Always protect groups first.
2. **Python re.sub with backslashes**: Replacement strings like `'$\\Gamma$'`
   cause `bad escape \\G` errors. Use lambda: `lambda m: '$\\\\Gamma$'`.
3. **Pandoc bracket escaping**: `[` `]` may become `\[` `\]` in raw output.
   Inside `$$...$$`, these create invalid nested display math. Fix to `[` `]`.
4. **Cascading sed replacements**: `sed -e 's/a/b/' -e 's/b/c/'` turns `a` → `c`.
   Use single-pass perl with hash lookup or temporary markers.
5. **Spaces in image filenames**: Break Markdown URLs. Always remove spaces.
6. **`.wmf` vs `.png`**: `.wmf` files are formula fragments, not figures.
7. **Table cells with pipes**: Use `\|` or HTML entities if needed.
8. **Chinese in `\text{}`**: Pandoc may double-escape; check manually.
9. **Cross-references**: `SEQ MTEqn \c` in `fldSimple` format are cross-references,
   not formula counter increments. Don't count them as separate formulas.
10. **Orphan images**: Files in `word/media/` may have no references in
    `document.xml`. Check `document.xml.rels` before assuming all are figures.
11. **Fragmented inline math**: After wrapping individual variables, scan for
    adjacent `$...$` blocks (like `F($A^{0}$)`) and merge into one expression.

## Quick Reference

```bash
INPUT="model.docx"
OUTPUT="model"

# Convert docx to raw md + extract images
pandoc "$INPUT" -t markdown --wrap=none -o "$OUTPUT.raw.md"
mkdir -p "$OUTPUT.artifacts"
pandoc "$INPUT" --extract-media="$OUTPUT.artifacts" -t markdown --wrap=none -o /dev/null
# Fallback: unzip -o "$INPUT" "word/media/*" -d "$OUTPUT.artifacts/"

# Remove formula image fragments
rm -f "$OUTPUT.artifacts/"*.wmf

# Remove spaces from image filenames
cd "$OUTPUT.artifacts"
for f in *.png; do mv "$f" "$(echo $f | sed 's/ //g')"; done

# Count formulas in original docx
python3 -c "
import re
# Use zipfile or unpacked/word/document.xml
with open('unpacked/word/document.xml') as f: xml = f.read()
print('Formulas:', xml.count('SEQ MTEqn \\\\h'))
"

# Clean Markdown is written to $OUTPUT.md
```
