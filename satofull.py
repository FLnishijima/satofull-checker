import asyncio
import random
import urllib.parse
from datetime import datetime
import pandas as pd
import requests
from playwright.async_api import async_playwright

WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbz2zDZnU8SVPUSLuK4P-efN2FTKPxIEDH74hWyENd7gbuPNzZK3BMS7N20yT5hLlToYWQ/exec"
SHEET_URL = "https://docs.google.com/spreadsheets/d/178pUB79bFdfBzor2a3-hvXw6R2lcDFplMzvJvTKsWoQ/export?format=csv"

# ==========================================
# 🔔 チャットワーク通知設定
# ==========================================
CHATWORK_API_TOKEN = "cd3cc8c847ce1d1a0cd518d88e289302"
CHATWORK_ROOM_ID = "442326223"

# ==========================================
# ⚙️ スプレッドシートの行ズレ調整設定
# ==========================================
OFFSET = -1

def get_target_a_index(b_row_number):
    if 3 <= b_row_number <= 12: return 3 - 1
    elif 13 <= b_row_number <= 22: return 13 - 1
    elif 23 <= b_row_number <= 32: return 23 - 1
    elif 33 <= b_row_number <= 42: return 33 - 1
    elif 43 <= b_row_number <= 52: return 43 - 1
    return None

async def check_satofull_status(page, keyword, target_product_name):
    print(f"【調査中】: {keyword} （対象: {target_product_name}）")
    encoded_kw = urllib.parse.quote(keyword)
    search_url = f"https://www.satofull.jp/products/list.php?q={encoded_kw}"
    
    try:
        await page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
    except Exception:
        pass
    
    await page.wait_for_timeout(1000)
    await page.evaluate("window.scrollBy(0, 800)")
    await page.wait_for_timeout(1000)
    await page.evaluate("window.scrollBy(0, 800)")
    await page.wait_for_timeout(1000)
    await page.evaluate("window.scrollBy(0, 800)")
    await page.wait_for_timeout(1500)
    
    js_code = r"""
    () => {
        const results = [];
        const seenPr = new Set();
        const seenNormal = new Set();
        
        const links = document.querySelectorAll("a[href*='/products/detail']");
        
        links.forEach(a => {
            const href = a.getAttribute('href');
            if(!href) return;
            
            const match = href.match(/product_id=([a-zA-Z0-9_-]+)/) || href.match(/\/detail\/([a-zA-Z0-9_-]+)/);
            if(!match) return;
            const pId = match[1];
            
            let card = a.closest('li');
            if(!card) card = a.closest('div[class*="product"], div[class*="item"], div.pr-area');
            if(!card) card = a.parentElement.parentElement; 
            
            const html = card.innerHTML;
            
            const isPr = html.includes('ico-pr') || 
                         html.includes('icon-pr') || 
                         html.includes('alt="PR"') || 
                         html.includes('alt="ＰＲ"') || 
                         />\s*PR\s*</i.test(html) || 
                         />\s*ＰＲ\s*</i.test(html);
            
            if (isPr) {
                if(!seenPr.has(pId)) {
                    seenPr.add(pId);
                    results.push({ type: 'PR', text: card.innerText });
                }
            } else {
                if(!seenNormal.has(pId)) {
                    seenNormal.add(pId);
                    results.push({ type: 'NORMAL', text: card.innerText });
                }
            }
        });
        return results;
    }
    """
    
    valid_cards = await page.evaluate(js_code)
    
    pr_count = 0
    normal_count = 0
    target_pr_ranks = []
    target_normal_ranks = []
    
    for card in valid_cards:
        text_clean = card["text"].replace(" ", "").replace(" ", "")
        target_clean = target_product_name.replace(" ", "").replace(" ", "")
        
        if card["type"] == 'PR':
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

async def main():
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

    async with async_playwright() as p:
        # ★ クラウド（画面なし環境）で動かすため headless=True に変更しています
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1400, "height": 900})

        for idx in range(2, total_rows):
            row_num = idx + 1
            kw = str(df.iloc[idx, 1]).strip() if pd.notna(df.iloc[idx, 1]) else ""
            target_a_idx = get_target_a_index(row_num)
            
            if kw and target_a_idx is not None:
                target_product = str(df.iloc[target_a_idx, 0]).strip()
                result_text = await check_satofull_status(page, kw, target_product)
                
                target_write_idx = idx + OFFSET
                if 0 <= target_write_idx < total_rows:
                    results[target_write_idx] = result_text
                
                await asyncio.sleep(random.uniform(1.5, 2.5))

        await browser.close()
        
    print("\n🚀 スプレッドシートに結果を自動送信しています...")
    payload = {"results": results, "use_custom_header_flow": True}
    
    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        if response.status_code == 200:
            print("✨ 調査完了！")
            
            # --- Chatworkに通知を送る処理 ---
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
                
                cw_data = {"body": message_body}
                requests.post(cw_url, headers=cw_headers, data=cw_data)
                print("📩 チャットワークに通知を送信しました！")
                
        else:
            print(f"❌ 送信エラー: {response.status_code}")
    except Exception as e:
        print(f"❌ 送信エラー: {e}")

if __name__ == "__main__":
    asyncio.run(main())