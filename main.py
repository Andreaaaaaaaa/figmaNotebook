import os
import json
import time
import requests
import yaml
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator

# Configuration
WEBHOOK_URL = os.environ.get("WECOM_WEBHOOK_URL")
STATE_FILE = "state.json"
CONFIG_FILE = "config.yaml"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(f"Config file {CONFIG_FILE} not found.")
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f)

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
    full_content = f"# 资讯监控日报 ({date_str})\n\n"
    
    for i, update in enumerate(updates, 1):
        # Translate title and content
        title_cn = translate_text(update['title'])
        # Summarize content to first sentence or 100 chars before translating
        content_summary = update['content'].split('.')[0] if '.' in update['content'] else update['content'][:100]
        content_cn = translate_text(content_summary)
        
        source_name = update['source']
        
        full_content += f"### {i}. 【{source_name}】 {title_cn}\n\n"
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

# --- Scraper Logic ---

def fetch_figma_generic(url, source_name):
    # Preserving the original robust logic for Figma
    print(f"Fetching {source_name} from {url}...")
    updates = []
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        
        processed_parents = set()
        
        for time_tag in soup.find_all("time"):
            parent = time_tag.parent
            if parent in processed_parents:
                continue
            processed_parents.add(parent)
            
            date_str = time_tag.get_text(strip=True)
            title_tag = parent.find(["h2", "h3"])
            
            if not title_tag and "Blog" in source_name:
                curr = parent
                while curr and curr.name != 'a' and curr.name != 'body':
                    curr = curr.parent
                if curr and curr.name == 'a':
                    title_tag = curr.find(["h2", "h3", "div"]) 
                    if not title_tag:
                         full_text = curr.get_text(" ", strip=True)
                         title = full_text.replace(date_str, "").strip()
                         if "By " in title:
                             title = title.split("By ")[0].strip()
                         title_tag = None 
            
            if title_tag:
                title = title_tag.get_text(strip=True)
            elif not title and "Blog" not in source_name: 
                title = "No Title"
                
            if (not title or title == "No Title") and "Blog" in source_name:
                 full_text = parent.get_text(" ", strip=True)
                 title = full_text.replace(date_str, "").strip()

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
            
            content = ""
            if "Release Notes" in source_name:
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

def fetch_generic_html(source_config):
    # Generic scraper for future sources
    # This is a placeholder for now, can be expanded based on 'selectors' in config
    url = source_config['url']
    name = source_config['name']
    print(f"Fetching {name} (Generic) from {url}...")
    return []

def main():
    try:
        config = load_config()
    except Exception as e:
        print(f"Failed to load config: {e}")
        return

    state = load_state()
    processed_ids = set(state.get("processed_ids", []))
    new_processed_ids = list(processed_ids)
    
    all_updates = []
    
    for source in config.get('sources', []):
        if not source.get('enabled', True):
            print(f"Skipping disabled source: {source['name']}")
            continue
            
        source_type = source.get('type')
        if source_type in ['figma_release_notes', 'figma_blog']:
            updates = fetch_figma_generic(source['url'], source['name'])
            all_updates.extend(updates)
        elif source_type == 'html_generic':
            updates = fetch_generic_html(source)
            all_updates.extend(updates)
        else:
            print(f"Unknown source type: {source_type}")
    
    # Deduplicate all_updates by ID
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
            
        # Filter logic (Generic filtering could be moved to config too, but keeping hardcoded for now)
        title_lower = update["title"].lower()
        if any(x in title_lower for x in ["pricing", "education", "student", "teacher"]):
            print(f"Skipping filtered update: {update['title']}")
            new_processed_ids.append(update["id"])
            continue
            
        pending_updates.append(update)
    
    # Batching: Take top 5
    batch = pending_updates[:5]
    
    if batch:
        print(f"Sending batch of {len(batch)} updates...")
        send_wechat_batch_notification(batch)
    else:
        print("No new updates to send.")

    # Mark ALL fetched updates as processed
    for u in all_updates:
        new_processed_ids.append(u["id"])
    
    save_state({"processed_ids": list(set(new_processed_ids))})
    print("Monitor finished.")

if __name__ == "__main__":
    main()
