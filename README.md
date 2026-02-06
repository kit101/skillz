# Skills Repository

技能库，用于 qwen-code/qodercli/opencode/codex/trae 等 AI Agent。

## 目录结构

```
.
├── skills/              # 技能目录
│   ├── skill1/         # 单个技能
│   │   ├── SKILL.md    # 技能定义（必需）
│   │   ├── scripts/    # 可执行脚本（可选）
│   │   ├── references/ # 参考文档（可选）
│   │   └── assets/     # 资源文件（可选）
│   └── skill2/
└── README.md           # 本文件
```

## 开发流程

### 1. 开发工准备

#### node、yarn/npm 或者 python、uvx

用于安装一些工具和作为脚本的执行语言。

#### dotenvx

基于node的cli环境变量工具，将.env.local的环境变量加载到cli中。
```bash
npm install -g dotenvx
dotenvx run -o -f .env -- opencode
```
#### [skills](https://github.com/vercel-labs/skills)

skill cli工具，用于创建、安装、卸载等。

#### skill creator

skill creator 是一个用于创建、更新skill的skill。

```bash
skills add anthropics/skills --skill skill-creator -a opencode
```

#### （可选）docker

使用隔离环境开发skill。
yarn ddev

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
skills add kit101z/skillz --skill hello-world
```

## 技能清单

| 技能名称 | 描述 | 状态 |
|---------|------|------|
| hello-world | 示例技能 | ✅ 已创建 |
| session-pretty-replay | 会话回放技能 | ✅ 已创建 |
| ssl-checker | SSL证书检查技能 | ✅ 已创建 |

## 许可证

[MIT](LICENSE)
