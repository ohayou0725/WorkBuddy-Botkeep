# WorkBuddy-Daily · Botkeep.cloud 部署套件 (双版本通用)

本套件适配 **Botkeep.cloud**（及类似 24/7 常驻容器云平台），同时原生支持 **腾讯 WorkBuddy 国内版** 与 **WorkBuddy AI 国际版**。
脚本会根据配置的环境变量自动智能识别并调度对应的自动化任务。

---

## 📂 文件清单

```text
workbuddy-botkeep/
├── main.py                  # 24/7 守护进程（支持国内版+国际版自动识别、北京时间调度、流式日志、HTTP探针）
├── workbuddy_daily.py       # 国内版核心脚本（33项自动化：云端17+小程序7+互动8+签到1）
├── workbuddy_login.py       # 国内版登录工具（手机短信验证码）
├── workbuddy_intl_daily.py  # 国际版核心脚本（探测领奖+连登活跃上报+免费模型保活+网页会话）
├── workbuddy_intl_login.py  # 国际版登录工具（免手机号，纯邮箱/Google/GitHub 浏览器设备授权）
├── requirements.txt         # 依赖声明（仅需 requests）
├── workbuddy-botkeep.zip    # 已打包好的 ZIP，直接上传 Botkeep 即可使用
└── README.md                # 本指南
```

---

## 🚀 部署步骤（Botkeep.cloud）

### 第一步：获取你的账号凭据（二选一或两者兼顾）

#### 选项 A：我是国际版用户（只有邮箱，无大陆手机号）
在本地终端执行：
```bash
python workbuddy_intl_login.py
```
1. 终端会打印并在浏览器打开 `https://www.workbuddy.ai/...` 授权链接；
2. 在浏览器中用你的**邮箱/Google/GitHub**登录并点击授权；
3. 终端自动捕获并输出凭据：
   ```text
   workbuddy-ai|eyJhbGciOi...|用户UID|eyJhbGciOi...
   ```
4. 复制该行，用于后续填入 `WORKBUDDY_INTL_TOKENS`。

#### 选项 B：我是国内版用户（使用手机号）
在本地终端执行：
```bash
python workbuddy_login.py
```
输入手机号及短信验证码，终端输出形如：
```text
13800000000:eyJhbGciOiJSUzI1NiIs...:eyJhbGciOiJIUzUxMiIs...
```
复制该行，用于后续填入 `WORKBUDDY_REFRESH_TOKEN`。

---

### 第二步：在 Botkeep.cloud 创建服务

1. 打开 [https://botkeep.cloud/](https://botkeep.cloud/) 登录控制台，点击 **Create**。
2. **Runtime / 语言环境**：选择 **Python**。
3. **Source / 代码上传**：
   - 选择 **ZIP upload**，上传本套件生成的 `workbuddy-botkeep.zip`。
   - 或推送到你的 GitHub 私有仓库后关联导入。
4. **Start Command（启动命令）**：
   ```bash
   python main.py
   ```
5. **Environment / Secrets（环境变量配置）**：
   - **如果用国际版（邮箱）**：
     - **Name**: `WORKBUDDY_INTL_TOKENS`
     - **Value**: 填入选项 A 拿到的 `workbuddy-ai|AT|uid|RT`（多账号换行隔开）
   - **如果用国内版（手机号）**：
     - **Name**: `WORKBUDDY_REFRESH_TOKEN`
     - **Value**: 填入选项 B 拿到的 `手机号:AT:RT`（多账号换行隔开）
   - *(两者可同时配置，脚本会全部自动执行！)*
   - *(可选推送密钥)*：`BARK_URL`、`PUSHPLUS_TOKEN`、`WECOM_WEBHOOK`、`DINGTALK_WEBHOOK`。
6. 点击 **Start** 启动服务。

---

## 🕒 默认定时策略（北京时间 UTC+8）

| 时间 | 任务 | 说明 |
| :---: | :---: | :--- |
| **07:00** | 早间日常 | 签到、成长中心云端与小程序任务、活跃上报、模型保活 |
| **12:00** | 午间补漏 | 检查缺口并自动补齐 |
| **23:30** | 夜猫子窗口 | 官方夜猫子活动（23:00~08:00）有效真实对话推进 |

---

## 🌐 内置 HTTP 探针与保活

服务启动后自动在后台监听分配的 Web 端口（默认 `8080`），直接访问控制台给出的公网 URL 即可查看运行状态：
```json
{
  "app": "WorkBuddy-Daily Botkeep Multi-Version Daemon",
  "boot_time": "2026-10-17 11:30:00",
  "domestic_configured": false,
  "intl_configured": true,
  "intl_last_status": "Success (8.2s)",
  "last_run_time": "2026-10-17 11:30:15",
  "runs_count": 1,
  "next_schedule": ["07:00", "12:00", "23:30"],
  "current_time": "2026-10-17 11:35:00"
}
```
也可以接入 Uptime Kuma 等外部探针做健康保活。
