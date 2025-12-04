import os
import json
import time
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

from deep_translator import GoogleTranslator

# Configuration
WEBHOOK_URL = os.environ.get("WECOM_WEBHOOK_URL")
STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"processed_ids": []}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def translate_text(text):
    try:
        # Use deep-translator to translate to Simplified Chinese
        translator = GoogleTranslator(source='auto', target='zh-CN')
        return translator.translate(text)
    except Exception as e:
        print(f"Translation failed: {e}")
        return text

def send_wechat_batch_notification(updates):
    if not WEBHOOK_URL:
        print("No Webhook URL configured. Skipping notification.")
        for u in updates:
            print(f"Would send: {u['title']}")
        return

    headers = {"Content-Type": "application/json"}
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    # Header
    full_content = f"# Figma 更新日报 ({date_str})\n\n"
    
    for i, update in enumerate(updates, 1):
        # Translate title and content
        title_cn = translate_text(update['title'])
        # Summarize content to first sentence or 100 chars before translating
        content_summary = update['content'].split('.')[0] if '.' in update['content'] else update['content'][:100]
        content_cn = translate_text(content_summary)
        
        source_tag = "【博客】" if update['source'] == "Blog" else "【更新】"
        
        full_content += f"### {i}. {source_tag} {title_cn}\n\n"
        full_content += f"> 原文: {update['title']}\n"
        full_content += f"> 说明: {content_cn}\n"
        full_content += f"> [查看详情]({update['link']})\n\n"

    data = {
        "msgtype": "markdown",
        "markdown": {
            "content": full_content
        }
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=data)
        print(f"WeCom Response: {response.text}")
        response.raise_for_status()
        print(f"Batch notification sent with {len(updates)} updates.")
    except Exception as e:
        print(f"Failed to send notification: {e}")

def fetch_updates_generic(url, source_name):
    print(f"Fetching {source_name} from {url}...")
    updates = []
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        
        # Strategy: Find all <time> tags. Their parent usually contains the title and content.
        # We use a set to track processed parents to avoid duplicates (if multiple time tags or structure causes overlap)
        processed_parents = set()
        
        for time_tag in soup.find_all("time"):
            parent = time_tag.parent
            if parent in processed_parents:
                continue
            processed_parents.add(parent)
            
            # Extract Date
            date_str = time_tag.get_text(strip=True)
            
            # Extract Title
            # Look for h2 or h3 in the parent
            title_tag = parent.find(["h2", "h3"])
            
            # Special handling for Blog: traverse up if not found
            if not title_tag and source_name == "Blog":
                # Try going up to the anchor tag
                curr = parent
                while curr and curr.name != 'a' and curr.name != 'body':
                    curr = curr.parent
                
                if curr and curr.name == 'a':
                    # We found the anchor. The title might be an h3 inside it, or just text.
                    title_tag = curr.find(["h2", "h3", "div"]) 
                    if not title_tag:
                         # Heuristic: Use the text of the anchor, remove the date
                         full_text = curr.get_text(" ", strip=True)
                         title = full_text.replace(date_str, "").strip()
                         if "By " in title:
                             title = title.split("By ")[0].strip()
                         title_tag = None 
            
            if title_tag:
                title = title_tag.get_text(strip=True)
            elif not title and source_name != "Blog": 
                title = "No Title"
                
            if (not title or title == "No Title") and source_name == "Blog":
                 full_text = parent.get_text(" ", strip=True)
                 title = full_text.replace(date_str, "").strip()

            # Extract Link
            link = url
            if parent.name == 'a':
                link = parent.get('href')
            else:
                a_tag = parent.find("a")
                if not a_tag:
                    curr = parent
                    while curr and curr.name != 'a' and curr.name != 'body':
                        curr = curr.parent
                    if curr and curr.name == 'a':
                        a_tag = curr
                
                if a_tag:
                    link = a_tag.get('href')
            
            if link and not link.startswith('http'):
                link = f"https://www.figma.com{link}"
            
            # Extract Content/Summary
            content = ""
            if source_name == "Release Notes":
                full_text = parent.get_text(" ", strip=True)
                content = full_text.replace(title, "").replace(date_str, "").strip()
                if len(content) > 200:
                    content = content[:200] + "..."
            
            updates.append({
                "source": source_name,
                "title": title,
                "date": date_str,
                "link": link,
                "content": content,
                "id": f"{date_str}-{title}" 
            })
            
    except Exception as e:
        print(f"Error fetching {source_name}: {e}")
        
    return updates

# ... (Previous fetch_updates_generic code is assumed to be above line 60 or so) ...

def main():
    state = load_state()
    processed_ids = set(state.get("processed_ids", []))
    new_processed_ids = list(processed_ids)
    
    all_updates = []
    
    # 1. Fetch Release Notes
    rn_updates = fetch_updates_generic("https://www.figma.com/release-notes/", "Release Notes")
    all_updates.extend(rn_updates)
    
    # 2. Fetch Blog
    blog_updates = fetch_updates_generic("https://www.figma.com/blog/", "Blog")
    all_updates.extend(blog_updates)
    
    # Deduplicate all_updates by ID
    # Use a dictionary to keep the first occurrence of each ID
    unique_updates_map = {}
    for u in all_updates:
        if u["id"] not in unique_updates_map:
            unique_updates_map[u["id"]] = u
    
    all_updates = list(unique_updates_map.values())
    
    print(f"Found {len(all_updates)} unique potential updates.")
    
    pending_updates = []
    
    for update in all_updates:
        if update["id"] in processed_ids:
            continue
            
        # Filter logic
        title_lower = update["title"].lower()
        if any(x in title_lower for x in ["pricing", "education", "student", "teacher"]):
            print(f"Skipping filtered update: {update['title']}")
            new_processed_ids.append(update["id"])
            continue
            
        pending_updates.append(update)
    
    # Batching: Take top 5
    # Assuming the fetch order is roughly chronological (newest first usually for scraped lists), 
    # we take the first 5.
    batch = pending_updates[:5]
    
    if batch:
        print(f"Sending batch of {len(batch)} updates...")
        send_wechat_batch_notification(batch)
    else:
        print("No new updates to send.")

    # Mark ALL fetched updates as processed to prevent sending old history in future runs
    # This ensures we only notify about *newly appeared* items next time.
    for u in all_updates:
        new_processed_ids.append(u["id"])
    
    # 4. Save State
    save_state({"processed_ids": list(set(new_processed_ids))}) # Ensure unique
    print("Figma Monitor finished.")

if __name__ == "__main__":
    main()
