# Skills Repository

技能库，用于 qwen-code/qodercli/opencode/codex/trae 等 AI Agent。

## 技能清单

| 技能名称 | 描述 | 状态 |
|----------|------|------|
| [markdown2docx](skills/markdown2docx/) | Markdown 转为正式 DOCX（论文、标准文档），支持自定义样式、封面、页眉页脚、首行缩进、表格美化、Mermaid 图表渲染，保留 build 中间产物供 Agent 手动微调 | ✅ 已创建 |
| [markdown2pdf](skills/markdown2pdf/) | Markdown 转为 PDF，支持中文排版、LaTeX 数学公式、嵌入式图片（基于 pandoc + xelatex） | ✅ 已创建 |
| [markdown-changelog](skills/markdown-changelog/) | 对比两个 Markdown 文件，生成结构化变更日志（开源标准格式） | ✅ 已创建 |
| [paper2markdown](skills/paper2markdown/) | 学术论文 .docx 转 Markdown，保留 LaTeX 公式、图表编号与交叉引用 | ✅ 已创建 |
| hello-world | 示例技能 | ✅ 已创建 |
| session-pretty-replay | 会话回放技能 | ⚠️ 废弃 |
| ssl-checker | SSL 证书检查技能 | ⚠️ 废弃 |


## 目录结构

```
.
├── skills/                  # 技能目录
│   ├── markdown2docx/      # Markdown → DOCX 转换
│   │   ├── SKILL.md        # 技能定义（必需）
│   │   ├── readme.md       # 技能说明（推荐）
│   │   ├── scripts/        # 可执行脚本
│   │   │   ├── build.py
│   │   │   └── render_mermaid.py
│   │   └── assets/         # 配置模板、字体等资源
│   │       ├── config.default.yaml
│   │       └── config.srs.yaml
│   ├── markdown2pdf/       # Markdown → PDF 转换
│   ├── markdown-changelog/ # Markdown 变更日志生成
│   ├── paper2markdown/     # 论文 .docx → Markdown 转换
│   └── hello-world/        # 示例技能
└── README.md               # 本文件
```

## 开发流程

### 1. 开发环境准备

| 工具 | 用途 | 安装 |
|------|------|------|
| Node.js / Python | 脚本执行环境 | 系统包管理器或官网 |
| [dotenvx](https://dotenvx.com/) | 加载 `.env.local` 环境变量到 CLI | `npm install -g dotenvx` |
| [skills CLI](https://github.com/vercel-labs/skills) | 技能的安装、卸载、管理 | `npm install -g skills` |
| skill-creator | 创建和更新技能的辅助技能 | `skills add anthropics/skills --skill skill-creator -a opencode` |
| Docker（可选） | 隔离开发环境 | `yarn ddev` |

**dotenvx 使用示例：**
```bash
dotenvx run -o -f .env -- opencode
```

### 2. 创建技能

```
yarn init-skill your-skill
```

### 3. 开发技能

可以使用`skill-creator`来创建、更新skill。

详情查看`.agents/skills/skill-creator/SKILL.md`

### 4. 发布

推送到github仓库

## 使用技能

```bash
# 安装单个技能
npx skills add kit101z/skillz --skill markdown2docx

```


## 许可证

[MIT](LICENSE)
