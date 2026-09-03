import os
import io
import time
import requests
import pandas as pd
from google import genai
from google.genai import errors

# 環境変数（GitHub Secrets）から取得
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# 1. みんかぶ手口データの取得
print("手口データを取得中...")
url = "https://fu.minkabu.jp/chart/nikkei225/volume"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}
res = requests.get(url, headers=headers)
tables = pd.read_html(io.StringIO(res.text))

df_buy = tables[0].head(10)
df_sell = tables[1].head(10)
df_oi_buy = tables[2].head(10)
df_oi_sell = tables[3].head(10)
df_sector = tables[6].head(5)

market_data = f"""
【日経225先物 各社別買い手口（上位10社）】
{df_buy.to_string(index=False)}

【日経225先物 各社別売り手口（上位10社）】
{df_sell.to_string(index=False)}

【買い建玉残高（上位10社）】
{df_oi_buy.to_string(index=False)}

【売り建玉残高（上位10社）】
{df_oi_sell.to_string(index=False)}

【投資部門別売買動向（直近5週）】
{df_sector.to_string()}
"""

# 2. Geminiによる分析（リトライ処理付き）
print("Geminiによる相場分析中...")
client = genai.Client(api_key=GEMINI_API_KEY)

prompt = f"""
あなたは日経225先物の手口分析・需給分析を行うプロのクオンツ/トレーダーです。
以下の最新手口データおよび建玉データを精査し、今後の先物動向と値幅予測を日本語で論理的に分析してください。

{market_data}

分析構成:
1. 主要プレイヤー（外資系 vs 国内個人）の動向分析
2. 今後の方向性（上目線/下目線/中立）
3. ボラティリティ・想定値幅の予測
4. 実践的なトレード戦略
"""

response = None
max_retries = 3
models_to_try = ["gemini-3.6-flash", "gemini-3.8-flash"]

for target_model in models_to_try:
    print(f"モデル試行中: {target_model}")
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=target_model,
                contents=prompt,
            )
            print("分析完了！")
            break
        except Exception as e:
            print(f"[{target_model}] 試行 {attempt}/{max_retries} 失敗: {e}")
            if attempt < max_retries:
                print("15秒待機して再試行します...")
                time.sleep(15)
    if response is not None:
        break

if response is None or not hasattr(response, 'text'):
    raise RuntimeError("すべてのモデルと再試行でGeminiの生成に失敗しました。")

report_text = response.text

# 3. Discordへ分割送信
chunk_size = 1900
chunks = [report_text[i:i + chunk_size] for i in range(0, len(report_text), chunk_size)]

print(f"Discordへ送信中（全 {len(chunks)} 通）...")
for idx, chunk in enumerate(chunks, start=1):
    payload = {
        "content": f"**【日経225先物 手口AI分析レポート ({idx}/{len(chunks)})】**\n\n{chunk}"
    }
    r = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    if r.status_code == 204:
        print(f"[{idx}/{len(chunks)}] 送信成功")
    else:
        print(f"[{idx}/{len(chunks)}] 送信失敗: {r.status_code}")
    time.sleep(0.5)

print("完了：Discordへ送信されました！")
