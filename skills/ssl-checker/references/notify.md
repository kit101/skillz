# 通知方式

默认使用邮件通知

## 1. 邮件通知

### 推荐方法使用`mcp-email`发送邮件通知

> `mcp-email`是一个mcp协议的插件，用于发送邮件通知。

1. 请先检查agent是否已经安装并配置了`mcp-email`插件。

2. 若未安装，先尝试安装mcp-email插件。

优先使用agent自带的mcp管理工具进行安装，比如`qwen-code`，其他agent请使用其自己的方式安装:
```bash
# 有EMAIL_USER等环境变量的情况下，可以不要-e EMAIL_USER="email_user"等参数
qwen mcp add mcp-email npx -y mcp-email@1.0.0 \
  -s project -t stdio \
  -e EMAIL_USER=\${EMAIL_USER} \
  -e EMAIL_PASSWORD=\${EMAIL_PASSWORD} \
  -e EMAIL_TYPE=\${EMAIL_TYPE}
```
配置结果：
```json
{
  "mcpServers": {
    "mcp-email": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-email@1.0.0"
      ],
      "env": {
        "EMAIL_USER": "${EMAIL_USER}",
        "EMAIL_PASSWORD": "${EMAIL_PASSWORD}",
        "EMAIL_TYPE": "${EMAIL_TYPE}"
      }
    }
  }
}
```

[mcp-email使用文档](./mcp-email/README.md)
[mcp-email配置文档](./mcp-email/CONFIG_GUIDE.md)，若对email type有疑问时请参考





## 不通知

用户未指定通知方式，email也失败，则不发送通知