#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WorkBuddy-Daily - Botkeep.cloud 24/7 常驻守护与定时调度入口 (智能全兼容防呆版)
核心增强：
  1. 自动搜索并加载容器内的 .env / 隐藏环境变量配置文件
  2. 内容级全自动嗅探：不依赖 Key 拼写，直接通过特征识别国际版与国内版 Token
  3. 子进程环境强力透传，彻底解决云平台面板变量读不到的问题
"""

import os
import sys
import glob
import time
import subprocess
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import json

# 强制 Python 标准输出无缓冲，保证在云端控制台能实时看到流式日志
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

# 统一时区：优先使用 zoneinfo (Python 3.9+)，否则使用 UTC+8 偏移
try:
    from zoneinfo import ZoneInfo
    BEIJING_TZ = ZoneInfo("Asia/Shanghai")
except Exception:
    BEIJING_TZ = timezone(timedelta(hours=8))


def get_beijing_now() -> datetime:
    """获取当前北京时间"""
    return datetime.now(timezone.utc).astimezone(BEIJING_TZ)


# 全局状态跟踪
STATUS = {
    "app": "WorkBuddy-Daily Botkeep Multi-Version Daemon",
    "boot_time": get_beijing_now().strftime("%Y-%m-%d %H:%M:%S"),
    "domestic_configured": False,
    "intl_configured": False,
    "domestic_last_status": "Idle",
    "intl_last_status": "Idle",
    "last_run_time": "Never",
    "runs_count": 0,
    "next_schedule": ["07:00", "12:00", "23:30"]
}


def load_all_possible_env_files():
    """扫描当前目录及周边可能存在的 .env 配置文件并加载进 os.environ"""
    candidate_paths = [
        ".env",
        ".env.local",
        ".env.production",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        os.path.join(os.getcwd(), ".env"),
        "environment",
        "/app/.env"
    ]
    
    # 扩展包含当前目录所有 .env 开头的文件
    for f in glob.glob(".*env*"):
        if f not in candidate_paths and os.path.isfile(f):
            candidate_paths.append(f)

    loaded_files = []
    for path in candidate_paths:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fp:
                    for line in fp:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip().replace("export ", "")
                            v = v.strip().strip('"').strip("'")
                            if k:
                                os.environ[k] = v
                loaded_files.append(path)
            except Exception:
                pass
    if loaded_files:
        print(f"[{get_beijing_now().strftime('%H:%M:%S')}] 📂 已自动从配置文件加载环境变量: {loaded_files}", flush=True)


def auto_detect_tokens():
    """
    智能嗅探：不管是环境变量还是隐藏文件，不依赖大小写或格式，
    直接扫描所有变量的 Key 与 Value 特征进行智能捕获！
    """
    domestic_token = os.getenv("WORKBUDDY_REFRESH_TOKEN", "").strip()
    intl_token = os.getenv("WORKBUDDY_INTL_TOKENS", "").strip() or os.getenv("WORKBUDDY_TOKEN", "").strip()

    # 如果标准变量名没拿到，启动“全变量内容嗅探”
    for k, v in list(os.environ.items()):
        v_clean = v.strip().strip('"').strip("'")
        k_clean = k.strip()

        # 1. 检查是不是 Key 拼写有细微偏差（比如带了空格、小写、带有特殊符号）
        if "WORKBUDDY" in k_clean.upper():
            if "INTL" in k_clean.upper() and not intl_token:
                intl_token = v_clean
            elif "REFRESH" in k_clean.upper() and not domestic_token:
                domestic_token = v_clean

        # 2. 内容级特征嗅探（最强兜底）：直接看内容是否是 WorkBuddy 凭据
        if not intl_token:
            # 国际版特征：包含 workbuddy-ai| 或者 (邮箱格式 且 包含 eyJ)
            if "workbuddy-ai|" in v_clean or ("@" in v_clean and "|eyJ" in v_clean):
                intl_token = v_clean
                print(f"[{get_beijing_now().strftime('%H:%M:%S')}] 🔍 智能嗅探：从变量 [{k_clean}] 成功捕获到国际版凭据！", flush=True)

        if not domestic_token:
            # 国内版特征：手机号开头 + 冒号 + eyJ
            if len(v_clean) > 50 and ":eyJ" in v_clean and v_clean[:2] in ("13", "14", "15", "16", "17", "18", "19"):
                domestic_token = v_clean
                print(f"[{get_beijing_now().strftime('%H:%M:%S')}] 🔍 智能嗅探：从变量 [{k_clean}] 成功捕获到国内版凭据！", flush=True)

    # 3. 本地文本文件保底：若同目录下有 tokens.txt，自动读入
    for token_file in ["tokens.txt", "token.txt"]:
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), token_file)
        if os.path.isfile(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as tf:
                    content = tf.read().strip()
                    if "workbuddy-ai|" in content or ("@" in content and "|eyJ" in content):
                        if not intl_token:
                            intl_token = content
                            print(f"[{get_beijing_now().strftime('%H:%M:%S')}] 📄 成功从本地 {token_file} 读取国际版凭据！", flush=True)
                    elif ":eyJ" in content:
                        if not domestic_token:
                            domestic_token = content
                            print(f"[{get_beijing_now().strftime('%H:%M:%S')}] 📄 成功从本地 {token_file} 读取国内版凭据！", flush=True)
            except Exception:
                pass

    # 关键步骤：把识别出来的 Token 强力写回 os.environ，保证后续子脚本 100% 读到！
    if intl_token:
        os.environ["WORKBUDDY_INTL_TOKENS"] = intl_token
        os.environ["WORKBUDDY_TOKEN"] = intl_token.split("|")[1] if "|" in intl_token else intl_token
    if domestic_token:
        os.environ["WORKBUDDY_REFRESH_TOKEN"] = domestic_token

    return domestic_token, intl_token


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP 健康探测服务"""
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        
        info = {
            **STATUS,
            "current_time": get_beijing_now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.wfile.write(json.dumps(info, indent=2, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        return


def start_health_server(port: int = 8080):
    """在后台线程中启动轻量 HTTP 探针"""
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"[{get_beijing_now().strftime('%H:%M:%S')}] 🌐 HTTP 健康探针已在 0.0.0.0:{port} 启动", flush=True)
    except Exception as e:
        print(f"[{get_beijing_now().strftime('%H:%M:%S')}] ⚠️ 启动 HTTP 探针失败: {e}", flush=True)


def execute_script(script_filename: str, task_name: str) -> tuple[int, float]:
    """运行指定子脚本，显式透传当前全部环境变量并流式输出日志"""
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_filename)
    if not os.path.exists(script_path):
        print(f"❌ [错误] 找不到脚本: {script_path}", flush=True)
        return -1, 0.0

    print(f"\n--- [子任务: {task_name}] 开始执行 ({script_filename}) ---", flush=True)
    start_ts = time.time()
    try:
        proc = subprocess.Popen(
            [sys.executable, "-u", script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=os.environ.copy()  # 强力透传环境变量
        )
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()

        proc.wait()
        cost_time = time.time() - start_ts
        return proc.returncode, cost_time
    except Exception as e:
        print(f"❌ [{task_name}] 执行异常: {e}", flush=True)
        return -1, time.time() - start_ts


def run_all_tasks():
    """检测环境变量并执行任务"""
    now_str = get_beijing_now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*65}", flush=True)
    print(f"[{now_str}] 🚀 开始执行 WorkBuddy 定时任务流水线...", flush=True)
    print(f"{'='*65}", flush=True)

    # 1. 尝试加载可能存在的 .env 配置文件
    load_all_possible_env_files()

    # 2. 执行智能嗅探与凭据解析
    domestic_token, intl_token = auto_detect_tokens()

    STATUS["domestic_configured"] = bool(domestic_token)
    STATUS["intl_configured"] = bool(intl_token)
    STATUS["runs_count"] += 1
    STATUS["last_run_time"] = now_str

    if not domestic_token and not intl_token:
        print("❌ [警告] 未能识别到有效的登录凭据！", flush=True)
        print("🔍 [诊断信息] 系统当前检测到的环境变量键名清单:", flush=True)
        safe_keys = [k for k in os.environ.keys() if not k.startswith("npm_")]
        print(f"   {safe_keys}\n", flush=True)
        print(f"🔍 [诊断信息] 当前目录文件清单: {os.listdir('.')}", flush=True)
        print(f"{'='*65}\n", flush=True)
        return

    # 3. 运行国内版任务
    if domestic_token:
        print(f"\n📌 [1/2] 发现国内版配置，开始执行...", flush=True)
        STATUS["domestic_last_status"] = "Running"
        code, cost = execute_script("workbuddy_daily.py", "国内版日常全流程")
        if code == 0:
            STATUS["domestic_last_status"] = f"Success ({cost:.1f}s)"
            print(f"✅ 国内版任务成功完成 (耗时 {cost:.1f}s)", flush=True)
        else:
            STATUS["domestic_last_status"] = f"Finished with code {code} ({cost:.1f}s)"
            print(f"⚠️ 国内版任务结束，返回码: {code} (耗时 {cost:.1f}s)", flush=True)

    # 4. 运行国际版任务
    if intl_token:
        account_hint = intl_token.split("|")[0] if "|" in intl_token else "国际版账号"
        print(f"\n📌 [2/2] 成功识别国际版配置 ({account_hint})，开始执行...", flush=True)
        STATUS["intl_last_status"] = "Running"
        code, cost = execute_script("workbuddy_intl_daily.py", "国际版每日活跃与签到")
        if code == 0:
            STATUS["intl_last_status"] = f"Success ({cost:.1f}s)"
            print(f"✅ 国际版任务成功完成 (耗时 {cost:.1f}s)", flush=True)
        else:
            STATUS["intl_last_status"] = f"Finished with code {code} ({cost:.1f}s)"
            print(f"⚠️ 国际版任务结束，返回码: {code} (耗时 {cost:.1f}s)", flush=True)

    finish_str = get_beijing_now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{finish_str}] 🎉 本轮所有任务已完成！", flush=True)
    print(f"{'='*65}\n", flush=True)


def main():
    boot_str = get_beijing_now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║   🌱 WorkBuddy-Daily · Botkeep 24/7 守护服务 (智能全兼容版)      ║
╚══════════════════════════════════════════════════════════════════╝
  ⏰ 启动时间: {boot_str} (北京时间 UTC+8)
  📅 计划时刻: 07:00 (日常) | 12:00 (补漏) | 23:30 (夜猫子)
  🌏 支持版本: 国内版 (workbuddy.cn) + 国际版 (workbuddy.ai)
  🐍 Python版本: {sys.version.split()[0]}
════════════════════════════════════════════════════════════════════
    """, flush=True)

    # 1. 尝试启动 HTTP 健康探测服务
    port_env = os.getenv("PORT", "8080")
    try:
        port = int(port_env)
        start_health_server(port)
    except ValueError:
        start_health_server(8080)

    # 2. 开机自检：启动后先跑一次任务
    run_on_boot = os.getenv("RUN_ON_BOOT", "true").lower() in ("true", "1", "yes")
    if run_on_boot:
        print(f"[{get_beijing_now().strftime('%H:%M:%S')}] 🔔 正在执行开机首次自检任务...", flush=True)
        run_all_tasks()

    # 3. 进入 24/7 定时调度死循环
    print(f"[{get_beijing_now().strftime('%H:%M:%S')}] ⏳ 进入定时守护循环，等待预定时刻...", flush=True)
    
    schedule_times_env = os.getenv("SCHEDULE_TIMES", "07:00,12:00,23:30")
    target_times = [t.strip() for t in schedule_times_env.split(",") if t.strip()]
    STATUS["next_schedule"] = target_times

    last_trigger_id = ""

    while True:
        now_bj = get_beijing_now()
        current_minute = now_bj.strftime("%H:%M")
        today = now_bj.strftime("%Y-%m-%d")

        if current_minute in target_times:
            trigger_id = f"{today}_{current_minute}"
            if last_trigger_id != trigger_id:
                last_trigger_id = trigger_id
                print(f"[{now_bj.strftime('%H:%M:%S')}] ⏰ 到达计划时刻 {current_minute}，触发执行！", flush=True)
                run_all_tasks()

        time.sleep(15)


if __name__ == "__main__":
    main()
