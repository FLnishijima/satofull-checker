import time
import random
import urllib.parse
from datetime import datetime
import pandas as pd
import requests
from bs4 import BeautifulSoup

WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbz2zDZnU8SVPUSLuK4P-efN2FTKPxIEDH74hWyENd7gbuPNzZK3BMS7N20yT5hLlToYWQ/exec"
SHEET_URL = "https://docs.google.com/spreadsheets/d/178pUB79bFdfBzor2a3-hvXw6R2lcDFplMzvJvTKsWoQ/export?format=csv"

# ==========================================
# 🔔 チャットワーク通知設定
# ==========================================
CHATWORK_API_TOKEN = "cd3cc8c847ce1d1a0cd518d88e289302"
CHATWORK_ROOM_ID = "442326223"
OFFSET = -1

def get_target_a_index(b_row_number):
    if 3 <= b_row_number <= 12: return 3 - 1
    elif 13 <= b_row_number <= 22: return 13 - 1
    elif 23 <= b_row_number <= 32: return 23 - 1
    elif 33 <= b_row_number <= 42: return 33 - 1
    elif 43 <= b_row_number <= 52: return 43 - 1
    return None

def check_satofull_status(keyword, target_product_name):
    print(f"【調査中】: {keyword} （対象: {target_product_name}）")
    encoded_kw = urllib.parse.quote(keyword)
    # 最大60件まで一度に取得する設定を追加
    search_url = f"https://www.satofull.jp/products/list.php?q={encoded_kw}&cnt=60"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
    }

    try:
        response = requests.get(search_url, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"  ❌ アクセスエラー: {e}")
        return "エラー（取得失敗）"

    soup = BeautifulSoup(response.text, "html.parser")
    
    # 検索結果のカードをすべて探す
    items = soup.find_all("div", class_=["product", "item", "pr-area"])
    if not items:
        # 別のHTML構造も探す
        items = soup.find_all("li", class_="item")
        
    if not items:
        print("  ⚠️ 商品が見つかりませんでした。")
        return "広告なし（圏外）"

    pr_count = 0
    normal_count = 0
    target_pr_ranks = []
    target_normal_ranks = []

    for item in items:
        # 商品名テキストの取得
        title_tag = item.find("h3") or item.find("p", class_="title") or item.find("div", class_="title")
        if not title_tag:
            continue
            
        text_clean = title_tag.text.replace(" ", "").replace(" ", "").strip()
        target_clean = target_product_name.replace(" ", "").replace(" ", "")
        
        # PR判定
        html_str = str(item)
        is_pr = 'ico-pr' in html_str or 'icon-pr' in html_str or 'alt="PR"' in html_str or 'alt="ＰＲ"' in html_str or '>PR<' in html_str or '>ＰＲ<' in html_str
        
        if is_pr:
            pr_count += 1
            if target_clean in text_clean:
                target_pr_ranks.append(f"{pr_count}位")
        else:
            normal_count += 1
            if target_clean in text_clean:
                target_normal_ranks.append(f"{normal_count}位")

    if target_pr_ranks and target_normal_ranks:
        result_text = f"🔴PR({', '.join(target_pr_ranks)}) ＆ 通常({', '.join(target_normal_ranks)})"
    elif target_pr_ranks:
        result_text = f"🔴広告あり({', '.join(target_pr_ranks)})"
    elif target_normal_ranks:
        result_text = f"広告なし({', '.join(target_normal_ranks)})"
    else:
        result_text = "広告なし（圏外）"
        
    print(f"  ➡️ 結果: {result_text}")
    return result_text

def main():
    now = datetime.now()
    date_header = now.strftime("%m/%d") if 7 <= now.hour <= 8 else ""
    time_header = now.strftime("%H:%M")
    
    print(f"--- 調査開始: {now.strftime('%m/%d %H:%M')} ---")
    
    try:
        df = pd.read_csv(SHEET_URL, header=None)
    except Exception as e:
        print("❌ 読み込み失敗。")
        return

    total_rows = len(df)
    results = [""] * total_rows
    
    if 0 <= 0 + OFFSET < total_rows: results[0 + OFFSET] = date_header
    if 0 <= 1 + OFFSET < total_rows: results[1 + OFFSET] = time_header

    for idx in range(2, total_rows):
        row_num = idx + 1
        kw = str(df.iloc[idx, 1]).strip() if pd.notna(df.iloc[idx, 1]) else ""
        target_a_idx = get_target_a_index(row_num)
        
        if kw and target_a_idx is not None:
            target_product = str(df.iloc[target_a_idx, 0]).strip()
            result_text = check_satofull_status(kw, target_product)
            
            target_write_idx = idx + OFFSET
            if 0 <= target_write_idx < total_rows:
                results[target_write_idx] = result_text
            
            time.sleep(random.uniform(2.0, 4.0))

    print("\n🚀 スプレッドシートに結果を自動送信しています...")
    payload = {"results": results, "use_custom_header_flow": True}
    
    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        if response.status_code == 200:
            print("✨ 調査完了！")
            
            if CHATWORK_API_TOKEN and CHATWORK_ROOM_ID:
                cw_url = f"https://api.chatwork.com/v2/rooms/{CHATWORK_ROOM_ID}/messages"
                cw_headers = {"X-ChatWorkToken": CHATWORK_API_TOKEN}
                message_body = (
                    "[To:10184838] [To:5295349]\n"
                    "[info][title]自動通知[/title]"
                    "✨ さとふるの検索順位チェックが完了しました！\n"
                    "スプレッドシートが更新されています。\n"
                    "https://docs.google.com/spreadsheets/d/178pUB79bFdfBzor2a3-hvXw6R2lcDFplMzvJvTKsWoQ/edit"
                    "[/info]"
                )
                requests.post(cw_url, headers=cw_headers, data={"body": message_body})
                print("📩 チャットワークに通知を送信しました！")
        else:
            print(f"❌ 送信エラー: {response.status_code}")
    except Exception as e:
        print(f"❌ 送信エラー: {e}")

if __name__ == "__main__":
    main()
