---
name: markdown2docx
description: |
  Convert Markdown files to professional .docx documents with Chinese formatting,
  table styling, automatic TOC, headers/footers, and page layout control.
  Use this skill whenever the user wants to turn a .md file into a Word document,
  especially for software requirement specifications, technical reports, requirements documents,
  or any structured Chinese document. Triggers include: "convert md to docx",
  "md转docx", "markdown to word", "生成word文档", "导出docx", "make a word doc from markdown".
---

# Markdown → DOCX 转换

将 Markdown 文件转换为格式良好的 .docx 文档。规则化的排版通过 YAML 配置 + 脚本自动处理，需要人工判断的决策由 LLM 完成。

## 快速开始

```bash
# 默认配置
python scripts/build.py input.md

# 软件需求规格 文档配置
python scripts/build.py input.md assets/config.srs.yaml --output SRS.docx

# 自定义配置（用 --output 指定输出路径；或用 YAML 的 output 字段控制）
python scripts/build.py input.md my-config.yaml --output report.docx
```

构建中间产物保留在 `{输出文件名}.docx-build/` 目录下（与输出 .docx 同名），方便手动修改 XML：
```
SRS.docx-build/
├── config.yaml        # ← 用户自定义配置（LLM 直接在此生成）
├── input.md           # 预处理后的 markdown
├── diagram_00.png    # 渲染的 Mermaid 图片
├── reference.docx    # 参考模板
├── draft.docx        # pandoc 原始输出
├── config.json       # 合并后的配置
├── build_ref.js      # 参考模板构建脚本
└── unpacked/         # 解包后的 XML（可直接编辑）
    ├── [Content_Types].xml
    └── word/
        ├── document.xml
        ├── styles.xml
        └── ...
```

## 工作流

```
 Markdown ──→ [render_mermaid] ──→ [pandoc + reference.docx] ──→ [XML post-process] ──→ .docx
                ↑ 脚本自动                     ↑ 按 config 自动           ↑ 按 config 自动
                                                                         ├─ 样式修正
                                                                         ├─ 表格列宽缩放
                                                                         ├─ 代码块美化
                                                                         └─ 边框/边距
```

脚本负责所有确定性操作，LLM 负责以下决策点。

---

## LLM 决策点

### 1. 配置文件选择与调整

根据文档类型选择或创建配置：

| 文档类型 | 推荐配置 |
|----------|----------|
| SRS | `assets/config.srs.yaml` |
| 通用技术文档 | 基于 `assets/config.default.yaml` 调整 |

**⚠️ 配置文件位置**：自定义配置必须直接写入 `{输出文件名}.docx-build/config.yaml`（与输出 .docx 同名目录），不要放在源文件目录。步骤：

```bash
mkdir -p doc/输出文件名.docx-build
# 然后 write 配置文件到 doc/输出文件名.docx-build/config.yaml
# 然后 build.py 指向该文件
```

**需要 LLM 判断的配置项：**

- `tables.small_table_indices`：哪些表不需要全宽（如封面信息表、简单键值表）
  观察 Markdown 中哪些表格只有 2 列且内容简短，记录其 0-based 索引
- `tables.column_strategy`：列宽策略（`content`/`auto`/`scale`/`none`，默认 `content`）
  - `content` 按每列最长文字比例分配（**推荐**，解决键值表键列过宽问题）
  - `auto` 让 Word 按内容自动适配
- `tables.header_style`：表头美化（`shaded`/`bold`/`none`，默认 `none`）
- `header.text`：页眉文字
- `title`：文档标题
- `fonts.body.size`：正文字号（一般五号=21，小四=24，四号=28）

### 2. Mermaid 图表处理

脚本自动调用 mermaid.ink API 将 ` ```mermaid ` 代码块渲染为 PNG。
如果外部网络不可用，设置 `render_mermaid: false`，图表将保留为代码块。

### 3. 标题层级与封面标题

**自动检测规则**（build.py 第 2 步自动执行）：

- 若 Markdown 有**且仅有 1 个** `#` 一级标题 → 自动提取为封面标题，所有标题层级上移：
  - `## Heading` → Word Heading 1
  - `### Subheading` → Word Heading 2
  - 以此类推
- 若 Markdown 有**0 个** `#` → 用 config 中的 `title`（若未设置则无封面页）
- 若 Markdown 有**≥2 个** `#` → 打印警告，不自动上移，**LLM 须询问用户哪个是封面标题**

**LLM 必须在运行 build.py 前检查**：读取 markdown，数一下 `# ` 开头的行，若 ≥2 个，询问用户。

### 4. 标题编号策略

- 如果 Markdown 标题已含手动编号（如 `# 1 范围`）→ `auto_numbering: false`
- 如果 Markdown 标题无编号（如 `# 范围`）→ `auto_numbering: true`，由 pandoc 自动编号

### 5. 诊断与修复

当输出不符合预期时，LLM 应使用 docx skill 的脚本解包检查：

```bash
python ../docx/scripts/office/unpack.py output.docx unpacked/
# 检查 word/styles.xml、word/document.xml 等
```

常见问题及修复方法：

- **标题颜色不对**：参考 docx 的 heading 样式与 `config.fonts.headings` 对比
- **缩进不生效**：检查 `Compact` 样式是否被继承链上的 `firstLine` 影响
- **表格边框位置错**：OOXML 对 `<w:tblPr>` 子元素有严格顺序要求
- **验证失败**：`pack.py` 输出会提示具体元素位置错误

### 6. 表格内虚线可见性

`tables.borders.insideH` 控制中间横线：
- `val: none` → PDF 不可见，Word 中可通过「视图→表格虚框」辅助编辑
- `val: dashed` → 打印/PDF 中可见虚线
- `val: single` → 实线

### 7. 代码块样式

脚本默认将代码块渲染为：等宽字体（Courier New）+ 浅灰背景（#F5F5F5）+ 9pt 字号。如需调整，编辑 `unpacked/word/styles.xml` 中 `SourceCode` 和 `VerbatimChar` 样式，然后手动运行 pack：

```bash
python ../docx/scripts/office/pack.py SRS.docx-build/unpacked/ SRS.docx --original SRS.docx-build/draft.docx
```

### 8. 表格列宽优化

通过 `tables.column_strategy` 配置，四种策略可选：

| 策略 | 效果 | 适用场景 |
|------|------|----------|
| `content` | 扫描每列最长 cell，按文字比例分配 | **默认推荐**，95% 场景 |
| `auto` | 删除 cell width，Word 按内容自动适配 | 内容简单、不想干预时 |
| `scale` | 保留 pandoc 列宽比例，等比缩放 | 表头长度能代表列宽时 |
| `none` | 不做任何调整 | 调试或特殊需求 |

小表格（`small_table_indices` 中指定的）不受列宽策略影响。

---

## 配置参考

完整配置项参见 `assets/config.default.yaml`（含注释）。关键配置组：

```yaml
page:          # 页面尺寸、边距 (DXA)
fonts:         # body 和 headings 的字体、字号、颜色
paragraph:     # 行距、首行缩进
title_page:    # 标题页布局
toc:           # 目录标题、层级深度、分页
header/footer: # 页眉页脚内容
tables:        # 宽度策略、单元格边距、边框样式
```

---

## 构建步骤详解

`build.py` 内部执行七个步骤：

1. **渲染 Mermaid** — 调用 `scripts/render_mermaid.py`，将 ` ```mermaid ` 块替换为 `![alt](diagram_NN.png)`
2. **标题检测与层级上移** — 若仅有 1 个 H1，提取为封面标题，同时 `## → #`（Word Heading 1）、`### → ##`（Word Heading 2）...
3. **构建参考模板** — 根据 config 用 docx-js 生成 `reference.docx`
4. **Pandoc 转换** — `pandoc --reference-doc=reference.docx --toc` 产生初始 .docx
5. **解包** — 使用 docx skill 的 `unpack.py`
6. **XML 后处理** — 按 config 修复：
   - 字体、字号、标题颜色
   - `Normal`/`Compact` 样式（含首行缩进）
   - 表格列宽策略（auto/scale/content/none）
   - 表格边框（表头框 + 表底线）、单元格边距
   - **表格前后间距**（自动插入 120 DXA 的 spacer 段落）
   - 标题页布局（居中、间距）、分页符
   - **代码块美化**：`SourceCode` 样式 → 等宽字体、浅灰背景、9pt
7. **打包** — 使用 docx skill 的 `pack.py`，含 Schema 验证

中间产物保留在 `{文件名}.docx-build/`，不会自动删除。

---

## 依赖

- Python ≥ 3.8, PyYAML
- Node.js ≥ 18, `docx` (npm install -g docx)
- pandoc ≥ 3.0
- docx skill（提供 unpack/pack/validate 脚本）
- 网络（mermaid.ink API，可选）

## 文件结构

```
md2docx/
├── SKILL.md                    ← 本文件
├── scripts/
│   ├── build.py                ← 主编排脚本
│   └── render_mermaid.py       ← Mermaid → PNG
└── assets/
    ├── config.default.yaml     ← 默认配置（含注释）
    └── config.srs.yaml         ← 软件需求规格 示例配置
```
