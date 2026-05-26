# Gmail Cleaner

一键清空 Gmail 邮箱所有邮件的命令行工具，基于 Gmail API。

## 功能

- 批量永久删除 Gmail 中所有邮件（1000 封/批次）
- 支持 HTTP/SOCKS5 代理（中国大陆用户友好）
- 自动重试 + 速率限制处理
- Token 缓存，一次登录多次使用
- 支持 `--dry-run` 预览模式
- 支持 `--force` 脚本模式

## 快速开始

### 1. Google Cloud 配置

1. 打开 [Google Cloud Console](https://console.cloud.google.com/)
2. 新建项目 → 启用 **Gmail API**
3. **API 和服务** → **OAuth 同意屏幕** → External → 填写应用名和邮箱 → 添加测试用户（你自己的 Gmail）
4. **凭据** → 创建凭据 → **OAuth 客户端 ID** → 桌面应用 → 下载 JSON
5. 将下载的文件重命名为 `credentials.json`，放到项目目录

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 运行

```bash
# 预览邮件数量（不删除）
python gmail_cleaner.py --dry-run

# 删除所有邮件（会要求确认）
python gmail_cleaner.py

# 无需交互确认（脚本模式）
python gmail_cleaner.py --force

# 使用代理访问 Google API
python gmail_cleaner.py --proxy http://127.0.0.1:7890
```

## 注意事项

- **删除不可逆**，运行前建议先用 `--dry-run` 确认
- 首次运行会弹出浏览器进行 OAuth 授权
- 授权后会生成 `token.pickle` 缓存凭据，后续运行无需重新登录
- 不要在公开环境分享 `credentials.json` 和 `token.pickle`

## License

MIT
