import urllib.request
import json
import csv
import ssl

url = "https://jsonplaceholder.typicode.com/posts"
context = ssl._create_unverified_context()  # 忽略SSL憑證驗證

with urllib.request.urlopen(url, context=context) as response:
    data = json.loads(response.read().decode())

with open("posts.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["id", "title"])
    for item in data[:50]:
        writer.writerow([item["id"], item["title"]])

print("✅ 已成功匯出 posts.csv")