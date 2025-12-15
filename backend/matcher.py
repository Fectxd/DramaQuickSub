import requests
import json
import re
import os
import sys
import configparser

# Load configuration from INI file
config = configparser.ConfigParser()
if getattr(sys, 'frozen', False):
    config_path = os.path.join(os.path.dirname(sys.executable), 'config.ini')
else:
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')

print(f"[matcher.py] Loading config from: {config_path}")
print(f"[matcher.py] sys.frozen = {getattr(sys, 'frozen', False)}")
print(f"[matcher.py] sys.executable = {getattr(sys, 'executable', 'N/A')}")
print(f"[matcher.py] __file__ = {__file__}")
print(f"[matcher.py] Config file exists: {os.path.exists(config_path)}")

if not os.path.exists(config_path):
    raise FileNotFoundError(f"请创建配置文件: {config_path}\n可以复制 config.ini.example 并填入你的API密钥")

config.read(config_path, encoding='utf-8')
CHATGPT_ENDPOINT = config.get('API', 'chatgpt_endpoint')
API_KEY = config.get('API', 'api_key')

print(f"[matcher.py] Loaded endpoint: {CHATGPT_ENDPOINT}")
print(f"[matcher.py] API key loaded: {API_KEY[:10]}..." if API_KEY else "[matcher.py] API key is empty!")

def extract_episode_number(filename):
    """Extract episode number from filename"""
    # Try various patterns: 01, E01, EP01, 第01集, etc.
    patterns = [
        r'[Ee][Pp]?(\d{1,3})',  # E01, EP01, e01, ep01
        r'第(\d{1,3})[集话話]',  # 第01集
        r'[^\d](\d{2,3})[^\d]', # isolated 2-3 digit numbers
        r'^(\d{2,3})[^\d]',     # start with 2-3 digits
        r'[^\d](\d{2,3})$',     # end with 2-3 digits
        r'[^\d](\d{2,3})\.',    # digits before extension
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            return match.group(1).zfill(2)  # Pad to 2 digits
    return None

def match_files(zh_files, en_files, video_files):
    print(f"\n=== Starting smart file matching ===")
    print(f"Total: {len(zh_files)} Chinese, {len(en_files)} Foreign, {len(video_files)} videos")
    
    if not zh_files and not en_files:
        print("No subtitle files found!")
        return []
    
    # ===== STEP 1: AI识别剧名（只返回剧名） =====
    zh_sample = zh_files[:3] if len(zh_files) > 0 else []
    en_sample = en_files[:3] if len(en_files) > 0 else []
    
    print(f"\n[STEP 1] Using AI to detect series name...")
    print(f"Chinese sample: {zh_sample}")
    print(f"Foreign sample: {en_sample}")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    # 第一次AI调用：只返回剧名
    prompt = f"""从以下字幕文件名提取剧名。只返回剧名本身，不要任何其他内容。

中文字幕: {json.dumps(zh_sample, ensure_ascii=False)}
外语字幕: {json.dumps(en_sample, ensure_ascii=False)}

只返回剧名，例如：惊鸿掠野"""
    
    data = {
        "model": "gemini-2.5-flash",
        "messages": [{"role": "user", "content": prompt}]
    }
    
    series_name = ""
    try:
        print("→ Sending request to AI...")
        response = requests.post(CHATGPT_ENDPOINT, headers=headers, data=json.dumps(data), timeout=30)
        print(f"← Response status: {response.status_code}")
        response.raise_for_status()
        result = response.json()
        content = result['choices'][0]['message']['content'].strip()
        
        # 清理可能的markdown或多余内容，只保留剧名
        content = content.replace('```', '').replace('json', '').strip()
        # 尝试解析JSON
        try:
            json_data = json.loads(content)
            if isinstance(json_data, dict):
                series_name = json_data.get('series_name', '')
            else:
                series_name = content
        except:
            # 不是JSON，直接当作剧名
            series_name = content.split('\n')[0].strip()  # 取第一行
        
        print(f"✓ Detected series: '{series_name}'")
        
    except Exception as e:
        print(f"✗ AI detection failed: {e}")
        # Fallback: 从中文字幕提取
        if zh_files:
            first = zh_files[0]
            series_name = re.sub(r'[Ee][Pp]?\d+.*', '', first)
            series_name = re.sub(r'\d{2,3}.*', '', series_name)
            series_name = re.sub(r'[_\-]*(中文|西班牙语|英语).*', '', series_name)
            series_name = series_name.strip('-_')
        print(f"→ Fallback series name: '{series_name}'")
    
    if not series_name:
        print("⚠ WARNING: Could not detect series name, using all videos")
    
    # ===== STEP 2: 本地筛选包含剧名的文件 =====
    print(f"\n[STEP 2] Filtering files containing '{series_name}'...")
    
    filtered_videos = []
    if series_name:
        for v in video_files:
            if series_name in v:
                filtered_videos.append(v)
    else:
        filtered_videos = video_files
    
    print(f"→ Filtered: {len(filtered_videos)} videos (from {len(video_files)} total)")
    
    # ===== STEP 3: AI匹配所有文件 =====
    print(f"\n[STEP 3] Sending all files to AI for matching...")
    
    # 第二次AI调用：发送所有字幕和筛选后的视频
    if zh_files or en_files or filtered_videos:
        match_prompt = f"""匹配以下文件的对应关系，返回JSON数组。

中文字幕 ({len(zh_files)}个):
{json.dumps(zh_files, ensure_ascii=False)}

外语字幕 ({len(en_files)}个):
{json.dumps(en_files, ensure_ascii=False)}

视频文件 ({len(filtered_videos)}个):
{json.dumps(filtered_videos, ensure_ascii=False)}

返回格式（只返回JSON数组，不要其他内容）:
[{{"episode": "01", "zh_sub": "file1.srt", "en_sub": "file2.srt", "video": "file3.mp4"}}]

注意：如果某集缺少某个文件，对应字段设为null。"""
        
        match_data = {
            "model": "gemini-2.5-flash",
            "messages": [{"role": "user", "content": match_prompt}]
        }
        
        try:
            print(f"→ Sending to AI: {len(zh_files)} zh + {len(en_files)} en + {len(filtered_videos)} videos")
            response = requests.post(CHATGPT_ENDPOINT, headers=headers, data=json.dumps(match_data), timeout=60)
            print(f"← Response status: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            
            # 清理markdown
            content = content.replace('```json', '').replace('```', '').strip()
            
            matched = json.loads(content)
            print(f"✓ AI matched {len(matched)} episodes")
            
            # 显示结果
            for item in matched:
                ep = item.get('episode', '??')
                status = []
                if item.get('zh_sub'): status.append('中文✓')
                if item.get('en_sub'): status.append('外语✓')
                if item.get('video'): status.append('视频✓')
                print(f"  Episode {ep}: {' '.join(status) if status else '(empty)'}")
            
            print(f"=== AI matching completed: {len(matched)} episodes ===\n")
            return matched
            
        except Exception as e:
            print(f"✗ AI matching failed: {e}")
            print("→ Falling back to local regex matching...")
    
    # ===== FALLBACK: 本地正则匹配 =====
    print(f"\n[FALLBACK] Using local regex matching...")
    
    zh_map = {}
    for f in zh_files:
        ep_num = extract_episode_number(f)
        if ep_num:
            zh_map[ep_num] = f
            print(f"  Chinese E{ep_num}: {f}")
    
    en_map = {}
    for f in en_files:
        ep_num = extract_episode_number(f)
        if ep_num:
            en_map[ep_num] = f
            print(f"  Foreign E{ep_num}: {f}")
    
    video_map = {}
    for f in filtered_videos:
        ep_num = extract_episode_number(f)
        if ep_num:
            video_map[ep_num] = f
            print(f"  Video E{ep_num}: {f}")
    
    all_episodes = sorted(set(list(zh_map.keys()) + list(en_map.keys()) + list(video_map.keys())))
    
    matched = []
    for ep in all_episodes:
        matched.append({
            'episode': ep,
            'zh_sub': zh_map.get(ep),
            'en_sub': en_map.get(ep),
            'video': video_map.get(ep)
        })
        status = []
        if zh_map.get(ep): status.append('中文✓')
        if en_map.get(ep): status.append('外语✓')
        if video_map.get(ep): status.append('视频✓')
        print(f"  Episode {ep}: {' '.join(status)}")
    
    print(f"=== Local matching completed: {len(matched)} episodes ===\n")
    return matched

