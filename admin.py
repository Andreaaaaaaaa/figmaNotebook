import streamlit as st
import yaml
import os
import requests
import pandas as pd
from bs4 import BeautifulSoup

# Import scraping logic from main.py
from main import fetch_figma_generic, fetch_generic_html

CONFIG_FILE = "config.yaml"

st.set_page_config(page_title="资讯监控配置后台", page_icon="⚙️", layout="wide")

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"sources": []}
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f)

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, allow_unicode=True)

def test_url(url):
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return True, f"✅ 访问成功 (Status: {resp.status_code})"
        else:
            return False, f"❌ 访问失败 (Status: {resp.status_code})"
    except Exception as e:
        return False, f"❌ 访问出错: {e}"

st.title("⚙️ 资讯监控配置后台")

config = load_config()
sources = config.get("sources", [])

# Sidebar: Add New Source
st.sidebar.header("添加新监控源")
with st.sidebar.form("add_source_form"):
    new_name = st.text_input("名称 (例如: Tableau 更新)")
    new_url = st.text_input("网址 (URL)")
    new_type = st.selectbox("类型", ["html_generic", "figma_release_notes", "figma_blog"])
    
    submitted = st.form_submit_button("添加")
    if submitted:
        if new_name and new_url:
            new_entry = {
                "name": new_name,
                "url": new_url,
                "type": new_type,
                "enabled": True # Default to enabled
            }
            sources.append(new_entry)
            config["sources"] = sources
            save_config(config)
            st.sidebar.success(f"已添加: {new_name}")
            st.rerun()
        else:
            st.sidebar.error("请填写名称和网址")

# Main Area: List Sources
st.header("当前监控列表")

if not sources:
    st.info("暂无监控源，请在左侧添加。")
else:
    for i, source in enumerate(sources):
        with st.expander(f"{source['name']} ({source['type']})"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.text_input("URL", value=source['url'], key=f"url_{i}", disabled=True)
                
                # Action Buttons
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if st.button("测试连接 (Ping)", key=f"ping_{i}"):
                        success, msg = test_url(source['url'])
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
                
                with btn_col2:
                    if st.button("试运行抓取 (Scrape)", key=f"scrape_{i}"):
                        with st.spinner("正在抓取中..."):
                            try:
                                updates = []
                                if source['type'] in ['figma_release_notes', 'figma_blog']:
                                    updates = fetch_figma_generic(source['url'], source['name'])
                                elif source['type'] == 'html_generic':
                                    updates = fetch_generic_html(source)
                                
                                if updates:
                                    st.success(f"成功抓取到 {len(updates)} 条内容！")
                                    df = pd.DataFrame(updates)
                                    # Show relevant columns
                                    st.dataframe(df[['date', 'title', 'link']])
                                    
                                    # Manual Send Button
                                    if st.button("发送到企业微信 (Send)", key=f"send_{i}"):
                                        from main import send_wechat_batch_notification, WEBHOOK_URL
                                        if not WEBHOOK_URL:
                                            st.error("未配置 WECOM_WEBHOOK_URL 环境变量，无法发送。")
                                        else:
                                            with st.spinner("正在发送..."):
                                                # Send top 5 or all? Let's send top 5 to be safe/consistent with daily report
                                                batch_to_send = updates[:5]
                                                send_wechat_batch_notification(batch_to_send)
                                                st.success(f"已发送前 {len(batch_to_send)} 条更新到企业微信！")
                                else:
                                    st.warning("未抓取到任何内容，请检查网址或解析规则。")
                            except Exception as e:
                                st.error(f"抓取发生错误: {e}")

            with col2:
                # Enable/Disable Toggle
                is_enabled = st.toggle("启用监控", value=source.get('enabled', True), key=f"enable_{i}")
                
                # Update config if changed
                if is_enabled != source.get('enabled', True):
                    source['enabled'] = is_enabled
                    config["sources"] = sources
                    save_config(config)
                    # st.rerun() # Optional, but toggle updates visually anyway
                
                st.write("") # Spacer
                
                if st.button("删除", key=f"del_{i}", type="primary"):
                    sources.pop(i)
                    config["sources"] = sources
                    save_config(config)
                    st.rerun()

st.markdown("---")
st.markdown("### 说明")
st.markdown("""
- **figma_release_notes / figma_blog**: 专用于 Figma 的特殊抓取逻辑。
- **html_generic**: 通用抓取模式（目前仅抓取页面标题作为测试，后续可配置选择器）。
- 修改配置后，下一次脚本运行时会自动生效。
""")
