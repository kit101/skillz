# md2docx

将 Markdown 文件转换为专业排版 .docx 文档。

## 功能

- **智能排版**：自动处理中文字体、字号、行距、首行缩进
- **目录生成**：自动生成并插入可更新目录
- **表格美化**：列宽自适应、表头样式、边框控制
- **图表渲染**：自动将 Mermaid 代码块渲染为图片
- **封面页**：根据配置生成标题页
- **页眉页脚**：自定义页眉文字与页码
- **样式灵活**：通过 YAML 配置控制所有排版参数

## 快速使用

```bash
# 基本转换
python scripts/build.py input.md

# 使用 srs 文档配置
python scripts/build.py input.md assets/config.srs.yaml --output SRS.docx

# 自定义配置
python scripts/build.py input.md my-config.yaml --output report.docx
```

## 目录结构

```
md2docx/
├── scripts/
│   ├── build.py           # 主转换脚本
│   └── render_mermaid.py  # Mermaid 图表渲染
├── assets/
│   ├── config.default.yaml # 默认配置
│   └── config.srs.yaml     # 软件需求规格 示例配置
└── readme.md
```

## 依赖

- Python ≥ 3.8, PyYAML
- Node.js ≥ 18, `docx` (npm install -g docx)
- pandoc ≥ 3.0
- docx skill（提供 unpack/pack/validate 脚本）

## 工作流

```
Markdown → [渲染 Mermaid] → [构建参考模板] → [Pandoc 转换] → [XML 后处理] → .docx
```

构建中间产物保留在 `{文件名}.docx-build/` 目录，方便手动调整。
