---
name: markdown-changelog
description: >
  Compare two markdown files and generate a structured changelog in open-source
  standard format (date-based versions, Summary/Added/Changed/Removed tables).
  Use whenever the user wants to compare .md file versions, create a changelog
  or release notes, document version differences, or mentions "changelog",
  "版本差异", "修订日志", "diff", "变更记录" in context of markdown files.
---

# Markdown Changelog

Compare two markdown files and generate a changelog in open-source standard format.

## Workflow

### 1. Identify files
Confirm the two markdown files to compare:
- **New file** (current version)
- **Old file** (previous version)

Extract the date from each filename if present (e.g., `20260609` → `2026-06-09`), or ask the user.

### 2. Run diff
```bash
diff -u <old-file> <new-file>
```

### 3. Analyze and categorize
Read the diff output carefully. Group every change into:

- **Added** — new formulas, paragraphs, tables, sections, footnotes that appear only in the new version
- **Changed** — existing content that was modified (rewording, restructuring, formatting, notation changes)
- **Removed** — content present in old version but deleted in new version (include reason if inferable)

For each item, note its **location** (section number or heading name).

### 4. Write Summary
Extract 3-5 high-level themes from the changes, e.g.:
- 规范化 (standardization)
- 实操化 (practicality)
- 边界完善 (boundary refinement)

Present as a table:

```markdown
| 维度 | 说明 |
|------|------|
| **规范化** | ... |
```

### 5. Generate changelog
Write to `<original-name>.changelog.md` (e.g., `模型三.changelog.md`), in the same directory as the new file.

## Output format

ALWAYS use this exact structure:

```markdown
# Changelog

## [NEW-DATE]

> 从 [OLD-DATE](./path/to/old-file.md) 升级

### Summary

| 维度 | 说明 |
|------|------|
| ... | ... |

### Added

| 位置 | 内容 |
|------|------|
| ... | ... |

### Changed

| 位置 | 修订前 | 修订后 |
|------|--------|--------|
| ... | ... | ... |

### Removed

| 位置 | 内容 | 原因 |
|------|------|------|
| ... | ... | ... |

---

## [OLD-DATE]

- 初稿
```

## Rules

1. **Date as version** — Use dates from filenames (YYYY-MM-DD), not semantic versions (v1.0, v2.0)
2. **Table format for all items** — Every Added/Changed/Removed entry goes in a table row
3. **Changed table has before/after columns** — Show "修订前" and "修订后" side by side
4. **Removed table has reason column** — Explain why each removal happened
5. **Summary comes before details** — High-level themes first, then itemized changes
6. **Link old file** — The `从 [DATE]` line links to the old file's path
7. **Ask before writing** — Present the changelog preview and confirm with user before saving
8. **Keep it concise** — Each table row should be a single, specific change. Merge trivial formatting-only changes into one row
