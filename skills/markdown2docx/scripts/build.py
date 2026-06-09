#!/usr/bin/env python3
"""
md2docx build orchestrator.

Usage:
    python build.py input.md config.yaml [--output output.docx]

Steps:
1. Parse config (merge with defaults)
2. Render mermaid diagrams if configured
3. Build reference.docx via docx-js
4. Run pandoc with reference
5. Unpack docx
6. Post-process XML (styles, tables, borders, title, TOC, page breaks)
7. Pack and validate
"""

import sys, os, re, json, subprocess, shutil, yaml

# ---- Paths ----
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
DOCX_SKILL = os.path.join(os.path.dirname(SKILL_DIR), "docx")
UNPACK_PY = os.path.join(DOCX_SKILL, "scripts", "office", "unpack.py")
PACK_PY = os.path.join(DOCX_SKILL, "scripts", "office", "pack.py")

DEFAULT_CONFIG = os.path.join(SKILL_DIR, "assets", "config.default.yaml")
MERMAID_SCRIPT = os.path.join(SCRIPT_DIR, "render_mermaid.py")

# ================================================================
# Config handling
# ================================================================

def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base."""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result

def load_config(config_path: str) -> dict:
    """Load config, merging with defaults."""
    with open(DEFAULT_CONFIG, 'r', encoding='utf-8') as f:
        defaults = yaml.safe_load(f)
    
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            overrides = yaml.safe_load(f)
        return deep_merge(defaults, overrides)
    return defaults

# ================================================================
# Reference docx builder (Node.js)
# ================================================================

JS_TEMPLATE = r'''
const fs = require("fs");
const { Document, Packer, Paragraph, TextRun,
        Header, Footer, AlignmentType, HeadingLevel,
        PageNumber, BorderStyle, TableOfContents } = require("docx");

const cfg = JSON.parse(fs.readFileSync("config.json", "utf-8"));

const headingStyles = [];
for (const [key, h] of Object.entries(cfg.fonts.headings)) {
    const level = parseInt(key[1]);
    headingStyles.push({
        id: "Heading" + level,
        name: "Heading " + level,
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: {
            size: h.size,
            bold: h.bold,
            font: h.name,
            color: h.color
        },
        paragraph: {
            spacing: { before: Math.round(h.size * 7.5), after: Math.round(h.size * 5) },
            outlineLevel: level - 1,
            indent: { firstLine: 0 }
        }
    });
}

const doc = new Document({
    styles: {
        default: {
            document: {
                run: {
                    font: cfg.fonts.body.name,
                    size: cfg.fonts.body.size
                },
                paragraph: {
                    spacing: { line: cfg.paragraph.line_spacing },
                    indent: { firstLine: cfg.paragraph.first_line_indent }
                }
            }
        },
        paragraphStyles: headingStyles
    },
    sections: [{
        properties: {
            page: {
                size: { width: cfg.page.width, height: cfg.page.height },
                margin: {
                    top: cfg.page.margin_top,
                    bottom: cfg.page.margin_bottom,
                    left: cfg.page.margin_left,
                    right: cfg.page.margin_right
                }
            }
        },
        headers: {
            default: new Header({
                children: [new Paragraph({
                    alignment: AlignmentType.CENTER,
                    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "000000", space: 1 } },
                    children: [new TextRun({
                        text: cfg.header.text,
                        font: cfg.header.font,
                        size: cfg.header.size,
                        color: cfg.header.color
                    })]
                })]
            })
        },
        footers: {
            default: new Footer({
                children: [new Paragraph({
                    alignment: AlignmentType.CENTER,
                    children: [
                        new TextRun({ text: "\u2014 ", size: cfg.footer.size, color: cfg.footer.color }),
                        new TextRun({ children: [PageNumber.CURRENT], size: cfg.footer.size, color: cfg.footer.color }),
                        new TextRun({ text: " \u2014", size: cfg.footer.size, color: cfg.footer.color })
                    ]
                })]
            })
        },
        children: [
            new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("T1")] }),
            new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("T2")] }),
            new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun("T3")] }),
            new Paragraph({ heading: HeadingLevel.HEADING_4, children: [new TextRun("T4")] }),
            new Paragraph({ heading: HeadingLevel.HEADING_5, children: [new TextRun("T5")] }),
            new Paragraph({ children: [new TextRun("Body text sample.")] }),
            new TableOfContents("TOC", { hyperlink: true, headingStyleRange: "1-5" }),
        ]
    }]
});

Packer.toBuffer(doc).then(buffer => {
    fs.writeFileSync("reference.docx", buffer);
    console.log("OK");
});
'''

def build_reference(config: dict, work_dir: str) -> str:
    """Build reference.docx using docx-js. Returns path."""
    # Write config as JSON for the JS script
    config_path = os.path.join(work_dir, "config.json")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    
    # Write JS script
    js_path = os.path.join(work_dir, "build_ref.js")
    with open(js_path, 'w', encoding='utf-8') as f:
        f.write(JS_TEMPLATE)
    
    # Resolve global npm root for require('docx')
    npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=5)
    env = os.environ.copy()
    if npm_root.returncode == 0 and npm_root.stdout.strip():
        env["NODE_PATH"] = npm_root.stdout.strip()
    
    result = subprocess.run(["node", js_path], cwd=work_dir,
                          capture_output=True, text=True, timeout=30, env=env)
    if result.returncode != 0:
        print("Reference build stderr:", result.stderr, file=sys.stderr)
        raise RuntimeError(f"Failed to build reference.docx: {result.stderr}")
    
    ref_path = os.path.join(work_dir, "reference.docx")
    if not os.path.exists(ref_path):
        raise RuntimeError("reference.docx not created")
    return ref_path

# ================================================================
# Pandoc conversion
# ================================================================

def run_pandoc(md_path: str, ref_path: str, config: dict, work_dir: str) -> str:
    """Run pandoc with reference docx. Returns path to draft.docx."""
    draft_path = os.path.join(work_dir, "draft.docx")
    
    args = [
        "pandoc", md_path,
        "--reference-doc=" + ref_path,
        "--from=" + config.get("pandoc_from_format", "markdown+pipe_tables+multiline_tables"),
        "--to=docx",
        "--metadata", "title=" + config.get("title", ""),
        "--toc", "--toc-depth=" + str(config["toc"]["depth"]),
        "--resource-path=" + os.path.dirname(os.path.abspath(md_path)),
        "-o", draft_path
    ]
    
    if config.get("auto_numbering", False):
        args.append("--number-sections")
    
    result = subprocess.run(args, cwd=work_dir, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"Pandoc failed: {result.stderr}")
    
    return draft_path

# ================================================================
# XML post-processing
# ================================================================

def _apply_column_strategy(tbl_xml: str, strategy: str, content_width: int) -> str:
    """Apply column width strategy to a table.
    
    Strategies:
      auto    - strip all tcW, let Word auto-fit based on content
      scale   - scale pandoc's column proportions to content_width
      content - analyze per-column text length, allocate width proportionally
      none    - keep pandoc's original widths unchanged
    """
    if strategy == "none":
        return tbl_xml
    
    if strategy == "auto":
        # Remove all cell width constraints; Word auto-fits
        tbl_xml = re.sub(r'<w:tcW[^>]*/>', '', tbl_xml)
        return tbl_xml
    
    if strategy == "scale":
        # Original behavior: scale gridCol proportions to content_width
        grid_match = re.search(r'<w:tblGrid>(.*?)</w:tblGrid>', tbl_xml, re.DOTALL)
        if not grid_match:
            return tbl_xml
        col_widths = [int(w) for w in re.findall(r'<w:gridCol w:w="(\d+)"', grid_match.group(1))]
        if not col_widths or sum(col_widths) <= 0:
            return tbl_xml
        total = sum(col_widths)
        if total >= content_width * 0.95:
            return tbl_xml
        scale = content_width / total
        new_widths = [max(200, int(w * scale)) for w in col_widths]
        return _apply_new_widths(tbl_xml, col_widths, new_widths)
    
    if strategy == "content":
        # Analyze actual cell text length per column, allocate proportionally
        rows = re.findall(r'<w:tr\b.*?</w:tr>', tbl_xml, re.DOTALL)
        if not rows:
            return tbl_xml
        
        # Count columns from first row
        first_cells = re.findall(r'<w:tc\b.*?</w:tc>', rows[0], re.DOTALL)
        ncols = len(first_cells)
        if ncols == 0:
            return tbl_xml
        
        # Measure text length per column (sum across all rows)
        col_lengths = [0] * ncols
        for row in rows:
            cells = re.findall(r'<w:tc\b.*?</w:tc>', row, re.DOTALL)
            for j, cell in enumerate(cells[:ncols]):
                texts = re.findall(r'<w:t[^>]*>([^<]*)</w:t>', cell)
                text_len = sum(len(t) for t in texts)
                col_lengths[j] = max(col_lengths[j], text_len)
        
        # Allocate: each column gets at least MIN_RATIO of the total
        total_len = sum(col_lengths)
        if total_len <= 0:
            return tbl_xml
        
        MIN_RATIO = 0.08  # 8% minimum
        ratios = [max(MIN_RATIO, cl / total_len) for cl in col_lengths]
        # Normalize to sum to 1.0
        ratio_sum = sum(ratios)
        ratios = [r / ratio_sum for r in ratios]
        
        # Get original gridCol widths to use as keys for replacement
        grid_match = re.search(r'<w:tblGrid>(.*?)</w:tblGrid>', tbl_xml, re.DOTALL)
        if grid_match:
            col_widths = [int(w) for w in re.findall(r'<w:gridCol w:w="(\d+)"', grid_match.group(1))]
        else:
            col_widths = [1000] * ncols  # fallback
        
        new_widths = [max(200, int(ratio * content_width)) for ratio in ratios]
        return _apply_new_widths(tbl_xml, col_widths[:len(new_widths)], new_widths)
    
    return tbl_xml


def _apply_new_widths(tbl_xml: str, old_widths: list, new_widths: list) -> str:
    """Apply new column widths to gridCol and cell tcW elements."""
    # Update gridCol
    for old_w, new_w in zip(old_widths, new_widths):
        tbl_xml = tbl_xml.replace(f'w:w="{old_w}"', f'w:w="{new_w}"', 1)
    
    # Update cell widths per row
    for row_match in re.finditer(r'<w:tr\b.*?</w:tr>', tbl_xml, re.DOTALL):
        row = row_match.group()
        cells = re.findall(r'<w:tc\b.*?</w:tc>', row, re.DOTALL)
        new_row = row
        for j, cell in enumerate(cells):
            if j < len(old_widths):
                ow, nw = old_widths[j], new_widths[j]
                if f'w:w="{ow}"' in cell:
                    new_row = new_row.replace(f'w:w="{ow}"', f'w:w="{nw}"', 1)
        tbl_xml = tbl_xml.replace(row, new_row)
    
    return tbl_xml

def fix_content_types(unpack_dir: str):
    """Add PNG content type declaration."""
    ct_path = os.path.join(unpack_dir, "[Content_Types].xml")
    with open(ct_path, 'r') as f:
        ct = f.read()
    if 'Extension="png"' not in ct:
        ct = ct.replace(
            '<Default Extension="odttf"',
            '<Default Extension="png" ContentType="image/png"/>\n  <Default Extension="odttf"'
        )
    with open(ct_path, 'w') as f:
        f.write(ct)

def fix_styles(unpack_dir: str, config: dict):
    """Fix styles.xml: heading colors, sizes, add Normal/Compact styles."""
    styles_path = os.path.join(unpack_dir, "word", "styles.xml")
    with open(styles_path, 'r') as f:
        styles = f.read()
    
    # Body font size in docDefaults
    body_size = config["fonts"]["body"]["size"]
    styles = re.sub(
        r'(<w:rPrDefault>.*?<w:rPr>.*?)<w:sz w:val="\d+"/>',
        rf'\1<w:sz w:val="{body_size}"/>',
        styles, flags=re.DOTALL
    )
    styles = re.sub(
        r'(<w:rPrDefault>.*?<w:rPr>.*?)<w:szCs w:val="\d+"/>',
        rf'\1<w:szCs w:val="{body_size}"/>',
        styles, flags=re.DOTALL
    )
    
    # Heading colors: replace theme colors with explicit black
    styles = re.sub(
        r'<w:color w:themeColor="[^"]*"[^>]*/>',
        '<w:color w:val="000000"/>',
        styles
    )
    
    # Fix heading sizes in effective (outlineLvl) set
    for level in range(1, 6):
        h_key = f"h{level}"
        if h_key in config["fonts"]["headings"]:
            target_sz = config["fonts"]["headings"][h_key]["size"]
            styles = re.sub(
                rf'(<w:style w:styleId="Heading{level}".*?<w:outlineLvl w:val="{level-1}"/>.*?<w:rPr>.*?)<w:sz w:val="\d+"/>(.*?</w:rPr>.*?</w:style>)',
                rf'\1<w:sz w:val="{target_sz}"/>\2',
                styles, flags=re.DOTALL
            )
    
    # Add Normal style with indent
    indent = config["paragraph"]["first_line_indent"]
    body_font = config["fonts"]["body"]["name"]
    line_spacing = config["paragraph"]["line_spacing"]
    
    normal_style = f'''  <w:style w:default="1" w:styleId="Normal" w:type="paragraph">
    <w:name w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:line="{line_spacing}"/>
      <w:ind w:firstLine="{indent}"/>
    </w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="{body_font}" w:hAnsi="{body_font}" w:eastAsia="{body_font}" w:cs="{body_font}"/>
      <w:sz w:val="{body_size}"/>
      <w:szCs w:val="{body_size}"/>
    </w:rPr>
  </w:style>
'''
    styles = styles.replace(
        '</w:docDefaults>\n  <w:style w:styleId="Title"',
        '</w:docDefaults>\n' + normal_style + '  <w:style w:styleId="Title"'
    )
    
    # Add BodyText, FirstParagraph, Compact styles
    body_styles = f'''  <w:style w:styleId="BodyText" w:type="paragraph">
    <w:name w:val="Body Text"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
  </w:style>
  <w:style w:customStyle="1" w:styleId="FirstParagraph" w:type="paragraph">
    <w:name w:val="First Paragraph"/>
    <w:basedOn w:val="BodyText"/>
    <w:qFormat/>
  </w:style>
  <w:style w:customStyle="1" w:styleId="Compact" w:type="paragraph">
    <w:name w:val="Compact"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:before="0" w:after="0" w:line="240"/>
      <w:ind w:firstLine="0"/>
    </w:pPr>
  </w:style>
  <w:style w:customStyle="1" w:styleId="SourceCode" w:type="paragraph">
    <w:name w:val="Source Code"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:shd w:val="clear" w:color="auto" w:fill="F5F5F5"/>
      <w:spacing w:before="40" w:after="40" w:line="260"/>
      <w:ind w:left="120" w:right="120" w:firstLine="0"/>
      <w:jc w:val="left"/>
    </w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:eastAsia="SimSun" w:cs="Courier New"/>
      <w:sz w:val="18"/>
      <w:szCs w:val="18"/>
    </w:rPr>
  </w:style>
  <w:style w:customStyle="1" w:styleId="VerbatimChar" w:type="character">
    <w:name w:val="Verbatim Char"/>
    <w:basedOn w:val="DefaultParagraphFont"/>
    <w:rPr>
      <w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:eastAsia="SimSun" w:cs="Courier New"/>
      <w:sz w:val="18"/>
      <w:szCs w:val="18"/>
    </w:rPr>
  </w:style>
'''
    styles = styles.replace(
        '</w:style>\n  <w:style w:styleId="Title"',
        '</w:style>\n' + body_styles + '  <w:style w:styleId="Title"'
    )
    
    with open(styles_path, 'w') as f:
        f.write(styles)

def fix_document(unpack_dir: str, config: dict):
    """Fix document.xml: TOC title, title page, page breaks, table widths/borders/margins/columns."""
    doc_path = os.path.join(unpack_dir, "word", "document.xml")
    with open(doc_path, 'r') as f:
        doc = f.read()
    
    # Calculate page content width
    page = config["page"]
    content_width = page["width"] - page["margin_left"] - page["margin_right"]
    
    # TOC title
    toc_title = config["toc"]["title"]
    doc = doc.replace(
        '<w:t xml:space="preserve">Table of Contents</w:t>',
        f'<w:t xml:space="preserve">{toc_title}</w:t>'
    )
    doc = doc.replace(
        '<w:t xml:space="preserve">TOC</w:t>',
        f'<w:t xml:space="preserve">{toc_title}</w:t>'
    )
    
    # Title page: insert title paragraph if not present, add spacing/centering
    tp = config.get("title_page", {})
    title_text = config.get("title", config.get("header", {}).get("text", ""))
    
    # Check if Title paragraph already exists
    has_title = '<w:pStyle w:val="Title"/>' in doc
    
    if title_text and not has_title:
        # Create and insert a Title paragraph at the very beginning
        title_para = f'''<w:p>
      <w:pPr>
        <w:pStyle w:val="Title"/>
      </w:pPr>
      <w:r>
        <w:rPr>
          <w:rFonts w:hint="eastAsia"/>
        </w:rPr>
        <w:t xml:space="preserve">{title_text}</w:t>
      </w:r>
    </w:p>'''
        # Insert after <w:body> tag
        body_start = doc.find('<w:body>')
        if body_start < 0:
            body_start = doc.find('<w:body')
        body_end = doc.find('>', body_start) + 1 if body_start >= 0 else doc.find('>') + 1
        doc = doc[:body_end] + '\n    ' + title_para + doc[body_end:]
    
    # Apply title page formatting (spacing + centering) to existing Title paragraph
    # OOXML pPr order: pStyle → spacing → ind → jc → ...
    sp_before = tp.get("spacing_before", 0)
    title_match = re.search(r'<w:p\b.*?<w:pStyle w:val="Title"/>.*?</w:p>', doc, re.DOTALL)
    if title_match:
        title_p = title_match.group()
        new_title = title_p
        
        # Build replacements in correct OOXML order
        extra = ''
        if sp_before > 0:
            extra += f'\n        <w:spacing w:before="{sp_before}"/>'
        if tp.get("centered"):
            extra += '\n        <w:jc w:val="center"/>'
        
        if extra and '<w:spacing' not in new_title and '<w:jc' not in new_title:
            new_title = new_title.replace(
                '<w:pStyle w:val="Title"/>',
                '<w:pStyle w:val="Title"/>' + extra
            )
        elif sp_before > 0:
            if '<w:spacing' in new_title:
                new_title = re.sub(r'<w:spacing[^>]*/>', f'<w:spacing w:before="{sp_before}"/>', new_title)
            else:
                new_title = new_title.replace(
                    '<w:pStyle w:val="Title"/>',
                    f'<w:pStyle w:val="Title"/>\n        <w:spacing w:before="{sp_before}"/>'
                )
        if tp.get("centered") and '<w:jc' not in new_title:
            if '<w:spacing' in new_title:
                new_title = new_title.replace(
                    f'<w:spacing w:before="{sp_before}"/>',
                    f'<w:spacing w:before="{sp_before}"/>\n        <w:jc w:val="center"/>'
                )
            else:
                new_title = new_title.replace(
                    '<w:pStyle w:val="Title"/>',
                    '<w:pStyle w:val="Title"/>\n        <w:jc w:val="center"/>'
                )
        if new_title != title_p:
            doc = doc.replace(title_p, new_title)
    
    # Page break after title
    if tp.get("page_break_after"):
        pb = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
        title_match = re.search(r'<w:p\b.*?<w:pStyle w:val="Title"/>.*?</w:p>', doc, re.DOTALL)
        if title_match:
            insert_pos = title_match.end()
            after = doc[insert_pos:insert_pos+150]
            if 'w:br w:type="page"' not in after:
                doc = doc[:insert_pos] + '\n    ' + pb + doc[insert_pos:]
    
    # Page break after TOC → section break (so title+TOC pages have no headers/footers)
    if config["toc"].get("page_break_after"):
        sdt_end = doc.find('</w:sdt>')
        if sdt_end > 0:
            # Build section properties for the first section (no headers/footers)
            # Same page settings as main section, but without headerReference/footerReference
            page_cfg = config["page"]
            sect_pr = f'''<w:sectPr>
      <w:pgSz w:h="{page_cfg["height"]}" w:orient="portrait" w:w="{page_cfg["width"]}"/>
      <w:pgMar w:bottom="{page_cfg["margin_bottom"]}" w:footer="708" w:gutter="0" w:header="708" w:left="{page_cfg["margin_left"]}" w:right="{page_cfg["margin_right"]}" w:top="{page_cfg["margin_top"]}"/>
      <w:pgNumType/>
      <w:docGrid w:linePitch="360"/>
    </w:sectPr>'''
            # Remove existing page break (if any) and insert section break
            after_sdt = doc[sdt_end + len('</w:sdt>'):]
            # Strip any existing page break paragraph
            after_sdt = re.sub(r'^\s*<w:p><w:r><w:br w:type="page"/></w:r></w:p>\s*', '', after_sdt)
            # Build section break paragraph
            section_break = f'<w:p><w:pPr>{sect_pr}</w:pPr></w:p>'
            doc = doc[:sdt_end + len('</w:sdt>')] + '\n    ' + section_break + '\n    ' + after_sdt
    
    # Tables
    small_indices = config["tables"].get("small_table_indices", [])
    tbl_borders = config["tables"]["borders"]
    cell_margins = config["tables"]["cell_margins"]
    
    # Build border XML
    border_parts = []
    for side, b in tbl_borders.items():
        sz = b.get("sz", 0)
        color = b.get("color", "auto")
        border_parts.append(f'<w:{side} w:val="{b["val"]}" w:sz="{sz}" w:space="0" w:color="{color}"/>')
    tbl_borders_xml = '<w:tblBorders>' + ''.join(border_parts) + '</w:tblBorders>'
    
    cm = cell_margins
    cell_margins_xml = f'<w:tcMar><w:top w:w="{cm["top"]}" w:type="dxa"/><w:start w:w="{cm["start"]}" w:type="dxa"/><w:bottom w:w="{cm["bottom"]}" w:type="dxa"/><w:end w:w="{cm["end"]}" w:type="dxa"/></w:tcMar>'
    
    cell_bottom_xml = '<w:tcBorders><w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/></w:tcBorders>'
    
    tables = list(re.finditer(r'<w:tbl\b.*?</w:tbl>', doc, re.DOTALL))
    print(f"  Processing {len(tables)} tables...", file=sys.stderr)
    
    replacements = []
    for i, t in enumerate(tables):
        tbl = t.group()
        new_tbl = tbl
        
        # ---- Width ----
        if i not in small_indices:
            new_tbl = re.sub(r'<w:tblW\s+[^>]*/>', '<w:tblW w:w="5000" w:type="pct"/>', new_tbl)
            if not re.search(r'<w:tblW', new_tbl):
                new_tbl = re.sub(r'(<w:tblPr>)', r'\1<w:tblW w:w="5000" w:type="pct"/>', new_tbl, count=1)
        
        # ---- Column widths: apply configured strategy ----
        if i not in small_indices:
            strategy = config["tables"].get("column_strategy", "auto")
            new_tbl = _apply_column_strategy(new_tbl, strategy, content_width)
        
        # ---- Borders (insert after w:tblW to respect OOXML element order) ----
        if '<w:tblBorders>' in new_tbl:
            new_tbl = re.sub(r'<w:tblBorders>.*?</w:tblBorders>', tbl_borders_xml, new_tbl, flags=re.DOTALL)
        else:
            new_tbl = re.sub(r'(<w:tblW\s+[^>]*/>)', r'\1' + tbl_borders_xml, new_tbl, count=1)
        
        # ---- Cell margins on ALL cells ----
        def add_cell_margins(cell_match):
            cell = cell_match.group(0)
            if '<w:tcMar>' in cell:
                cell = re.sub(r'<w:tcMar>.*?</w:tcMar>', cell_margins_xml, cell, flags=re.DOTALL)
            elif '<w:tcPr/>' in cell:
                cell = cell.replace('<w:tcPr/>', '<w:tcPr>' + cell_margins_xml + '</w:tcPr>')
            elif '<w:tcPr>' in cell:
                cell = cell.replace('<w:tcPr>', '<w:tcPr>' + cell_margins_xml)
            else:
                cell = re.sub(r'(<w:tc[^>]*>)', r'\1<w:tcPr>' + cell_margins_xml + '</w:tcPr>', cell, count=1)
            return cell
        new_tbl = re.sub(r'<w:tc\b.*?</w:tc>', add_cell_margins, new_tbl, flags=re.DOTALL)
        
        # ---- Header row: solid bottom ----
        def fix_header_row(row_match):
            row = row_match.group(0)
            def fix_cell(c):
                cell = c.group(0)
                if '<w:tcBorders>' in cell:
                    cell = re.sub(r'<w:bottom [^>]*/>', '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>', cell)
                    return cell
                else:
                    return cell.replace('<w:tcPr>', '<w:tcPr>' + cell_bottom_xml)
            return re.sub(r'<w:tc\b.*?</w:tc>', fix_cell, row, flags=re.DOTALL)
        
        new_tbl = re.sub(r'(<w:tr\b.*?</w:tr>)', fix_header_row, new_tbl, count=1, flags=re.DOTALL)
        
        if new_tbl != tbl:
            replacements.append((t.start(), t.end(), new_tbl))
    
    # Apply replacements (end to start)
    for start, end, new_text in reversed(replacements):
        doc = doc[:start] + new_text + doc[end:]
    
    # Insert spacer paragraphs before/after each table (reverse order → no shift issues)
    spacer_before = '<w:p><w:pPr><w:spacing w:before="120" w:after="0" w:line="60" w:lineRule="auto"/></w:pPr></w:p>'
    spacer_after  = '<w:p><w:pPr><w:spacing w:before="0" w:after="120" w:line="60" w:lineRule="auto"/></w:pPr></w:p>'
    
    tables2 = list(re.finditer(r'<w:tbl\b.*?</w:tbl>', doc, re.DOTALL))
    for t in reversed(tables2):
        # Insert spacer AFTER table first (doesn't shift anything to the left)
        doc = doc[:t.end()] + '\n    ' + spacer_after + '\n    ' + doc[t.end():]
        # Insert spacer BEFORE table (shifts this table and right-side content, but that's ok
        # since we're working right-to-left and already placed the after-spacer)
        doc = doc[:t.start()] + '\n    ' + spacer_before + '\n    ' + doc[t.start():]
    
    print(f"  Fixed {len(replacements)} tables", file=sys.stderr)
    
    # Strip diagram filename captions ("diagram_00.png" etc. under images)
    doc = re.sub(
        r'\n\s*<w:p>\s*<w:pPr>\s*<w:pStyle w:val="ImageCaption"/>\s*</w:pPr>\s*<w:r>\s*<w:t[^>]*>diagram_\d+\.png</w:t>\s*</w:r>\s*</w:p>',
        '', doc
    )
    
    # Fix image paragraphs: add explicit non-indenting pPr to override
    # inherited Normal style firstLine indent (which pushes images out of margin)
    # Also handles the case where pandoc wraps images in CaptionedFigure style
    doc = re.sub(
        r'<w:p>\s*<w:pPr>\s*<w:pStyle w:val="CaptionedFigure"/>\s*</w:pPr>',
        '<w:p><w:pPr><w:ind w:firstLine="0"/></w:pPr>',
        doc
    )
    # Handle image paragraphs without any pPr (inherit Normal's firstLine indent)
    def fix_image_para(m):
        para = m.group()
        if '<w:pPr>' in para:
            return para  # already has pPr
        # Inject pPr with no indent before the first <w:r> containing a drawing
        return para.replace('<w:r><w:drawing>', '<w:pPr><w:ind w:firstLine="0"/></w:pPr><w:r><w:drawing>', 1)
    doc = re.sub(r'<w:p>\s*<w:r><w:drawing>.*?</w:drawing>.*?</w:p>', fix_image_para, doc, flags=re.DOTALL)
    
    with open(doc_path, 'w') as f:
        f.write(doc)

# ================================================================
# Main build pipeline
# ================================================================

def _auto_shift_headings(md_text: str, config: dict) -> str:
    """If markdown has exactly one H1 heading, extract it as the document title
    and shift all heading levels up by one (## → #, ### → ##, etc.).
    
    This makes the single H1 the cover-page title, and all H2+ become
    Heading 1+ in Word.
    """
    # Only match ATX headings at line start (not in code blocks, etc.)
    # The markdown has already been preprocessed (mermaid blocks removed)
    h1s = re.findall(r'^#(?!#)\s+(.+)', md_text, re.MULTILINE)
    
    if len(h1s) == 0:
        print("  No H1 heading found, skipping shift", file=sys.stderr)
        return md_text
    
    if len(h1s) > 1:
        # Multiple H1s — ambiguous, ask user
        print(f"  ⚠️  Found {len(h1s)} H1 headings, cannot auto-detect title:", file=sys.stderr)
        for t in h1s:
            print(f"     • {t.strip()}", file=sys.stderr)
        print(f"  💡  Set 'title' in config to pick one, or use only one H1", file=sys.stderr)
        # Don't shift — LLM/user intervention needed
        return md_text
    
    # Exactly one H1 — use as title, shift all headings down
    title = h1s[0].strip()
    if not config.get("title"):
        config["title"] = title
        print(f"  Title (auto): {title}", file=sys.stderr)
    else:
        print(f"  Title (config): {config['title']} (H1 '{title}' will be removed)", file=sys.stderr)
    
    # Remove the original H1 line from markdown
    md_text = re.sub(r'^# .*\n?', '', md_text, count=1, flags=re.MULTILINE)
    
    # Shift all remaining headings: ## → #, ### → ##, etc.
    # Only shift headings at line start
    md_text = re.sub(r'^#(#+) ', r'\1 ', md_text, flags=re.MULTILINE)
    
    print(f"  Headings shifted: ##→# , ###→## , ...", file=sys.stderr)
    return md_text


def build(input_md: str, config_path: str, output_path: str = None):
    """Run the full build pipeline."""
    config = load_config(config_path)
    
    md_dir = os.path.dirname(os.path.abspath(input_md))
    md_basename = os.path.splitext(os.path.basename(input_md))[0]
    
    # Resolve output path:
    #   --output/-o flag → relative to CWD (standard Unix convention)
    #   YAML config only  → relative to input markdown directory (more intuitive)
    #   If neither specified, default to input basename + .docx
    from_config = (output_path is None)
    if from_config:
        output_path = config.get("output") or f"{md_basename}.docx"
    if not os.path.isabs(output_path):
        output_path = os.path.join(md_dir if from_config else os.getcwd(), output_path)
    output_path = os.path.abspath(output_path)
    
    # Use named work directory (not temp) so intermediate artifacts persist
    # work_dir basename matches output filename (e.g. X.docx → X.docx-build)
    output_basename = os.path.splitext(os.path.basename(output_path))[0]
    output_dir = os.path.dirname(output_path)
    work_dir = os.path.join(output_dir, f"{output_basename}.docx-build")
    os.makedirs(work_dir, exist_ok=True)
    
    print(f"Working in: {work_dir}", file=sys.stderr)
    
    # Copy config to build directory (if not already there)
    if config_path and os.path.exists(config_path):
        dest_config = os.path.join(work_dir, "config.yaml")
        src_abs = os.path.abspath(config_path)
        dest_abs = os.path.abspath(dest_config)
        if src_abs != dest_abs:
            shutil.copy(config_path, dest_config)
        print(f"  Config: {dest_config}", file=sys.stderr)
    
    # Step 1: Render mermaid diagrams
    md_path = os.path.join(work_dir, "input.md")
    if config.get("render_mermaid", True):
        print("[1/7] Rendering mermaid diagrams...", file=sys.stderr)
        result = subprocess.run(
            [sys.executable, MERMAID_SCRIPT, os.path.abspath(input_md), work_dir],
            capture_output=True, text=True, timeout=30
        )
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(result.stdout)
        print(result.stderr.strip(), file=sys.stderr)
    else:
        shutil.copy(input_md, md_path)
    
    # Step 2: Auto-detect title + shift heading levels
    print("[2/7] Detecting title and shifting headings...", file=sys.stderr)
    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()
    md_text = _auto_shift_headings(md_text, config)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_text)
    
    # Step 3: Build reference docx
    print("[3/7] Building reference.docx...", file=sys.stderr)
    ref_path = build_reference(config, work_dir)
    
    # Step 4: Pandoc conversion
    print("[4/7] Running pandoc...", file=sys.stderr)
    draft_path = run_pandoc(md_path, ref_path, config, work_dir)
    
    # Step 5: Unpack
    print("[5/7] Unpacking...", file=sys.stderr)
    unpack_dir = os.path.join(work_dir, "unpacked")
    subprocess.run([sys.executable, UNPACK_PY, draft_path, unpack_dir],
                  capture_output=True, timeout=30, check=True)
    
    # Step 6: Post-process
    print("[6/7] Post-processing XML...", file=sys.stderr)
    fix_content_types(unpack_dir)
    fix_styles(unpack_dir, config)
    fix_document(unpack_dir, config)
    
    # Step 7: Pack
    print("[7/7] Packing...", file=sys.stderr)
    subprocess.run([sys.executable, PACK_PY, unpack_dir, output_path,
                   "--original", draft_path],
                  capture_output=True, timeout=30, check=True)
    
    print(f"Done: {output_path} (build artifacts in {work_dir})", file=sys.stderr)
    
    # Friendly summary
    size_str = f"{os.path.getsize(output_path) / 1024:.0f}KB" if os.path.exists(output_path) else "?"
    unpack_rel = os.path.join(work_dir, "unpacked")
    draft_rel = os.path.join(work_dir, "draft.docx")
    pack_script = os.path.join(DOCX_SKILL, "scripts", "office", "pack.py")
    summary_lines = [
        "",
        "=" * 60,
        f"  ✅  转换完成：{os.path.basename(output_path)} ({size_str})",
        f"  📁  中间产物：{work_dir}/",
        f"       ├─ unpacked/word/  ← 可编辑 XML 微调样式",
        f"       ├─ config.yaml      ← 本次使用的配置",
        f"       ├─ draft.docx       ← pandoc 原始输出",
        f"       └─ diagram_*.png    ← 渲染的图片",
        "",
        f"  💡  如需手动微调 XML 后重新打包：",
        f"       python {pack_script} {unpack_rel} {output_path} --original {draft_rel}",
        "",
        "  🔧  还需要进一步调整格式吗？（列宽策略、页边距、表格样式等）",
        "=" * 60,
    ]
    for line in summary_lines:
        print(line, file=sys.stderr)
    
    return output_path

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python build.py input.md [config.yaml] [--output output.docx]")
        sys.exit(1)
    
    input_md = sys.argv[1]
    config_path = None
    output_path = None
    
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] in ('--output', '-o') and i + 1 < len(sys.argv):
            output_path = sys.argv[i + 1]
            i += 2
        elif sys.argv[i].endswith('.yaml') or sys.argv[i].endswith('.yml'):
            config_path = sys.argv[i]
            i += 1
        else:
            print(f"Unknown argument: {sys.argv[i]}", file=sys.stderr)
            print(f"Usage: python build.py input.md [config.yaml] [--output|-o output.docx]", file=sys.stderr)
            sys.exit(1)
    
    result = build(input_md, config_path, output_path)
    print(result)
