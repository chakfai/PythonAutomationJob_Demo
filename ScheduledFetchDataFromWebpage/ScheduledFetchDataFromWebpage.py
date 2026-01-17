import re
import time
from datetime import datetime
import requests
from xml.etree import ElementTree as ET

# 若你已經有 RSS 原文，直接把它放到 `raw_text` 變數；否則程式會從 RSS_URL 抓取
RSS_URL = "https://rss.weather.gov.hk/rss/CurrentWeather_uc.xml"
OUT_FILE = "hko_saikung_rss.txt"

def normalize_text(s: str) -> str:
    """
    1) 把各種空白（包含全形空格、tab、換行）壓成單一空格
    2) 移除中文（CJK）字元之間的空格（例如 "下 午" -> "下午"）
    3) 移除中文與阿拉伯數字之間不必要的空格（例如 "下午 8 時" -> "下午8時"）
    4) 保留英文單字之間的空格
    """
    if s is None:
        return ""
    # 1) 壓縮所有空白為單一空格
    s = re.sub(r"\s+", " ", s).strip()
    # 2) 移除中文（CJK）字元之間的空格
    s = re.sub(r"(?<=[\u2E80-\u9FFF])\s+(?=[\u2E80-\u9FFF])", "", s)
    # 3) 移除中文與數字之間的空格（雙向）
    s = re.sub(r"(?<=[\u2E80-\u9FFF])\s+(?=\d)", "", s)
    s = re.sub(r"(?<=\d)\s+(?=[\u2E80-\u9FFF])", "", s)
    return s

def parse_from_text(text: str):
    """
    從純文字中擷取：
      - source: 類似 "上午8時天文台錄得..." 或 "下午8時天文台錄得..." 的片段（允許原文有空格）
      - Sai Kung 溫度（支援 "西貢21℃", "西 貢 21 度", "西貢 21" 等）
    回傳 (temp, source)
    """
    txt = normalize_text(text)

    # 支援的時間詞：上午/下 午/早上/晚上 等，允許字間有空白或全形空格（normalize 已處理大部分空白）
    # 這個正則會匹配像「上午8時天文台錄得...」「上 午 8 時 天 文 台 錄 得...」等
    time_keywords = r"(?:上\s*午|下\s*午|早\s*上|早上|晚上|午前|午后|am|pm)"
    # 匹配「時間詞 + 最多 40 個非句號逗號字元 + 天文台 + 最多 40 個非句號逗號字元 + 錄得 + 後續內容」
    src_pattern = re.compile(time_keywords + r"[^\。,\n]{0,40}?天文台[^\。,\n]{0,40}?錄\s*得", re.IGNORECASE)
    src_m = src_pattern.search(txt)
    if not src_m:
        # 備援：找「錄得」附近的上下文
        src_m = re.search(r"[^\。,\n]{0,40}錄\s*得[^\。,\n]{0,40}", txt, re.IGNORECASE)

    source = src_m.group(0) if src_m else None

    # 2) 嘗試擷取「西貢」附近的溫度（容許字間有空格）
    temp = None
    # 支援：西貢 21 度  或 西貢21℃  或 西 貢 21
    pattern = re.compile(r"西\s*貢[^\d\-]{0,12}(-?\d+(?:\.\d+)?)\s*(?:度|℃|°C)?", re.IGNORECASE)
    m = pattern.search(txt)
    if m:
        temp = m.group(1) + "°C"
    else:
        # 備援：找「西貢」出現的上下文，然後在附近找第一個攝氏數字
        idx = txt.find("西貢")
        if idx == -1:
            idx = txt.find("西 貢")
        if idx != -1:
            window = txt[max(0, idx-60): idx+60]
            t2 = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:度|℃|°C)", window)
            if t2:
                temp = t2.group(1) + "°C"

    return temp, source

def fetch_rss_text():
    """
    直接從 RSS 抓取並把 <description> 等合併成純文字
    若沒有 description，回傳原始 XML 文字
    """
    r = requests.get(RSS_URL, timeout=10)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    parts = []
    # 取 item/description 與 channel/description（若有）
    for desc in root.findall(".//item/description"):
        if desc is not None and desc.text:
            parts.append(desc.text)
    ch_desc = root.find(".//channel/description")
    if ch_desc is not None and ch_desc.text:
        parts.append(ch_desc.text)
    return "\n".join(parts) if parts else r.text  # 若沒 description，就回傳原始 XML

def run(times=5, interval=2, use_rss=True, raw_text=None):
    for i in range(times):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            if use_rss:
                text = fetch_rss_text()
            else:
                if raw_text is None:
                    raise ValueError("No raw_text provided while use_rss is False")
                text = raw_text
            temp, source = parse_from_text(text)
            status = "OK"
        except Exception as e:
            temp, source = None, None
            status = f"ERROR: {e}"

        # 寫入檔案（追加）
        with open(OUT_FILE, "a", encoding="utf-8") as f:
            f.write(f"Run {i+1}/{times}  Timestamp: {ts}\n")
            f.write(f"Status: {status}\n")
            f.write(f"Sai Kung temperature: {temp or '未找到'}\n")
            f.write(f"Data source text: {source or '未找到'}\n")
            f.write("-" * 40 + "\n")

        print(f"[{ts}] Run {i+1}/{times}  Sai Kung: {temp or '未找到'}  Source: {source or '未找到'}")
        if i < times - 1:
            time.sleep(interval)

if __name__ == "__main__":
    # 測試用範例（可改成 use_rss=False 並貼上含有「上 午 8 時 天 文 台 錄 得」的 raw_text）
    # raw_example_text = "上 午 8 時 天 文 台 錄 得 西 貢 21 度。"
    # run(times=1, interval=0, use_rss=False, raw_text=raw_example_text)

    # 預設從 RSS 抓取並執行三次
    run(times=3, interval=2, use_rss=True)