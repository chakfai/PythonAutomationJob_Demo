import smtplib
import subprocess
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import socket
import datetime
import requests

# === 設定區 ===
services_to_check = ["LanmanServer", "Spooler", "wuauserv"]  # 要檢查的服務
websites_to_check = ["hk.yahoo.com", "google.com", "microsoft.com"]  # 要檢查的網站

smtp_server = "smtp.gmail.com"
smtp_port = 587
smtp_user = "abcabc@gmail.com"
smtp_password = "sadsassadsadasd"  # 建議改用安全方式存放

from_addr = "abcabc@gmail.com"
to_addr = "abcabc@gmail.com"

# === 檢查服務狀態 ===
def check_service(service_name):
    try:
        result = subprocess.run(
            ["sc", "query", service_name],
            capture_output=True, text=True, timeout=5
        )
        return "RUNNING" in result.stdout
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False

# === 檢查網站 (Ping) ===
def check_website_ping(hostname):
    try:
        result = subprocess.run(
            ["ping", "-n", "2", hostname],
            capture_output=True, text=True, timeout=5
        )
        return "TTL=" in result.stdout
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False

# === 檢查網站 (HTTP) ===
def check_website_http(hostname):
    try:
        response = requests.get(f"http://{hostname}", timeout=5)
        return response.status_code == 200
    except Exception:
        return False

# === 產生完整服務狀態報告 ===
def get_all_service_status(services):
    status_report = []
    for svc in services:
        if check_service(svc):
            status_report.append(f"✅ Service {svc} is running")
        else:
            status_report.append(f"❌ Service {svc} is NOT running")
    return "\n".join(status_report)

# === 產生完整網站狀態報告 ===
def get_all_website_status(websites):
    status_report = []
    for site in websites:
        if check_website_ping(site):
            status_report.append(f"✅ Website {site} is reachable via Ping")
        else:
            status_report.append(f"⚠️ Ping failed for {site}, trying HTTP...")
            if check_website_http(site):
                status_report.append(f"✅ Website {site} is reachable via HTTP")
            else:
                status_report.append(f"❌ Website {site} is NOT responding")
    return "\n".join(status_report)

# === 發送 Email ===
def send_email(subject, body):
    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_addr, to_addr, msg.as_string())
        print(f"✅ Email sent: {subject}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

# === 主程式 ===
if __name__ == "__main__":
    hostname = socket.gethostname()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 建立完整報告
    full_service_report = get_all_service_status(services_to_check)
    full_website_report = get_all_website_status(websites_to_check)

    # 檢查服務 (失敗時寄送警告)
    for svc in services_to_check:
        if not check_service(svc):
            subject = f"⚠️ Service Failure Alert: {svc}"
            body = f"Alert: Service {svc} is NOT running.\nServer: {hostname}\nTime: {timestamp}\n\n=== Full Service Status Report ===\n{full_service_report}\n\n=== Full Website Status Report ===\n{full_website_report}"
            send_email(subject, body)

    # 檢查網站 (失敗時寄送警告)
    for site in websites_to_check:
        if not check_website_ping(site) and not check_website_http(site):
            subject = f"⚠️ Website Failure Alert: {site}"
            body = f"Alert: Website {site} is NOT responding.\nServer: {hostname}\nTime: {timestamp}\n\n=== Full Service Status Report ===\n{full_service_report}\n\n=== Full Website Status Report ===\n{full_website_report}"
            send_email(subject, body)

    # 永遠寄送完整報告 (每日快照)
    subject = f"✅ Daily Status Report ({timestamp})"
    body = f"Server: {hostname}\nTime: {timestamp}\n\n=== Full Service Status Report ===\n{full_service_report}\n\n=== Full Website Status Report ===\n{full_website_report}"
    send_email(subject, body)
