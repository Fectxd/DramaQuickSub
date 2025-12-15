from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
import uvicorn
import shutil
import os
import zipfile
from typing import List, Optional, Dict
from pydantic import BaseModel
import json

# Import local modules
# Assuming the script is run from the root directory
try:
    from backend.matcher import match_files
    from backend.corrector import correct_text_with_gpt
    from backend.srt_parser import parse_srt, parse_ass, blocks_to_srt, blocks_to_ass, time_to_seconds, merge_blocks_by_time
except ImportError:
    # Fallback if run from backend directory
    from matcher import match_files
    from corrector import correct_text_with_gpt
    from srt_parser import parse_srt, parse_ass, blocks_to_srt, blocks_to_ass, time_to_seconds, merge_blocks_by_time

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories - 使用当前工作目录（exe 所在目录）
import sys
if getattr(sys, 'frozen', False):
    # 打包后：在 exe 所在目录创建 uploads
    BASE_PATH = os.path.dirname(sys.executable)
else:
    # 开发环境：在项目根目录
    BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UPLOAD_DIR = os.path.join(BASE_PATH, "uploads")
ZH_DIR = os.path.join(UPLOAD_DIR, "zh")
EN_DIR = os.path.join(UPLOAD_DIR, "en")
os.makedirs(ZH_DIR, exist_ok=True)
os.makedirs(EN_DIR, exist_ok=True)

# Frontend 静态文件目录
if getattr(sys, 'frozen', False):
    FRONTEND_DIR = os.path.join(sys._MEIPASS, "frontend")
else:
    FRONTEND_DIR = os.path.join(BASE_PATH, "frontend")

# Global state
current_matches = []
video_base_path = ""

class MatchRequest(BaseModel):
    video_path: str

class SaveRequest(BaseModel):
    filename: str
    content: str
    type: str # 'zh' or 'en'

class CorrectRequest(BaseModel):
    content: str
    rules: str

class UpdateBlockRequest(BaseModel):
    episode_index: int
    block_index: int
    text: str
    type: str  # 'zh' or 'en'
    start: Optional[str] = None  # Optional: update start time
    end: Optional[str] = None    # Optional: update end time

class SaveAllBlocksRequest(BaseModel):
    episode_index: int
    blocks: List[Dict]
    type: str  # 'zh' or 'en'

@app.post("/api/upload/zh")
async def upload_zh(file: UploadFile = File(...)):
    print(f"\n=== Uploading Chinese subtitles ===")
    print(f"Filename: {file.filename}")
    
    if os.path.exists(ZH_DIR):
        shutil.rmtree(ZH_DIR)
    os.makedirs(ZH_DIR)
    
    file_path = os.path.join(UPLOAD_DIR, "zh.zip")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    print(f"Saved to: {file_path}")
    
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(ZH_DIR)
        print(f"Extracted to: {ZH_DIR}")
        
        # List extracted files
        for root, dirs, files in os.walk(ZH_DIR):
            for f in files:
                print(f"  - {f}")
    except zipfile.BadZipFile:
        print("ERROR: Invalid zip file")
        return {"error": "Invalid zip file"}
    
    return {"message": "Chinese subtitles uploaded"}

@app.post("/api/upload/en")
async def upload_en(file: UploadFile = File(...)):
    print(f"\n=== Uploading Foreign subtitles ===")
    print(f"Filename: {file.filename}")
    
    if os.path.exists(EN_DIR):
        shutil.rmtree(EN_DIR)
    os.makedirs(EN_DIR)
    
    file_path = os.path.join(UPLOAD_DIR, "en.zip")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    print(f"Saved to: {file_path}")
    
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(EN_DIR)
        print(f"Extracted to: {EN_DIR}")
        
        # List extracted files
        for root, dirs, files in os.walk(EN_DIR):
            for f in files:
                print(f"  - {f}")
    except zipfile.BadZipFile:
        print("ERROR: Invalid zip file")
        return {"error": "Invalid zip file"}
        
    return {"message": "English subtitles uploaded"}

@app.post("/api/match")
async def match(req: MatchRequest):
    global current_matches, video_base_path
    video_base_path = req.video_path
    
    print(f"\n=== Match request received ===")
    print(f"Video path: {video_base_path}")
    print(f"ZH_DIR: {ZH_DIR}")
    print(f"EN_DIR: {EN_DIR}")
    
    try:
        zh_files = []
        for root, dirs, files in os.walk(ZH_DIR):
            for file in files:
                if file.endswith(".srt") or file.endswith(".ass"):
                    zh_files.append(file)
                    print(f"Found Chinese subtitle: {file}")
                    
        en_files = []
        for root, dirs, files in os.walk(EN_DIR):
            for file in files:
                if file.endswith(".srt") or file.endswith(".ass"):
                    en_files.append(file)
                    print(f"Found Foreign subtitle: {file}")

        video_files = []
        if os.path.exists(video_base_path):
            print(f"Video path exists, scanning...")
            for root, dirs, files in os.walk(video_base_path):
                for file in files:
                    if file.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                        video_files.append(file)
                        print(f"Found video: {file}")
        else:
            print(f"Video path does not exist: {video_base_path}")
        
        print(f"Total: {len(zh_files)} Chinese, {len(en_files)} Foreign, {len(video_files)} videos")
        
        current_matches = match_files(zh_files, en_files, video_files)
        print(f"Match result: {current_matches}")
        return current_matches
    except Exception as e:
        print(f"ERROR in match endpoint: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/rematch-videos")
async def rematch_videos():
    """重新匹配视频文件，不影响已有字幕"""
    global current_matches, video_base_path
    
    print(f"\n=== Rematch videos request ===")
    
    if not video_base_path:
        raise HTTPException(status_code=400, detail="No video path set. Please run initial match first.")
    
    if not current_matches:
        raise HTTPException(status_code=400, detail="No existing matches. Please run initial match first.")
    
    print(f"Video path: {video_base_path}")
    print(f"Current matches: {len(current_matches)} episodes")
    
    # 重新扫描视频文件夹
    video_files = []
    if os.path.exists(video_base_path):
        print(f"Scanning video folder...")
        for root, dirs, files in os.walk(video_base_path):
            for file in files:
                if file.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                    video_files.append(file)
                    print(f"Found video: {file}")
    else:
        print(f"Video path does not exist: {video_base_path}")
        raise HTTPException(status_code=404, detail="Video path not found")
    
    print(f"Found {len(video_files)} videos")
    
    # 获取字幕文件列表（用于AI识别剧名）
    zh_files = []
    for root, dirs, files in os.walk(ZH_DIR):
        for file in files:
            if file.endswith(".srt") or file.endswith(".ass"):
                zh_files.append(file)
    
    en_files = []
    for root, dirs, files in os.walk(EN_DIR):
        for file in files:
            if file.endswith(".srt") or file.endswith(".ass"):
                en_files.append(file)
    
    # 调用matcher重新匹配
    new_matches = match_files(zh_files, en_files, video_files)
    
    # 更新全局匹配结果（只更新视频字段，保留字幕）
    print(f"\nUpdating video associations...")
    for i, match in enumerate(current_matches):
        # 找到对应集数的新匹配
        episode = match.get('episode')
        for new_match in new_matches:
            if new_match.get('episode') == episode:
                old_video = match.get('video', 'None')
                new_video = new_match.get('video', 'None')
                current_matches[i]['video'] = new_video
                if old_video != new_video:
                    print(f"  Episode {episode}: {old_video} → {new_video}")
                break
    
    # 检查是否有新集数（只在视频中有，字幕中没有）
    existing_episodes = {m.get('episode') for m in current_matches}
    for new_match in new_matches:
        ep = new_match.get('episode')
        if ep not in existing_episodes and new_match.get('video'):
            print(f"  New episode found: {ep} (video only)")
            current_matches.append(new_match)
    
    # 重新排序
    current_matches.sort(key=lambda x: x.get('episode', ''))
    
    print(f"=== Rematch completed: {len(current_matches)} episodes ===\n")
    return current_matches

def find_file(name, search_dir):
    for root, dirs, files in os.walk(search_dir):
        if name in files:
            return os.path.join(root, name)
    return None

@app.get("/api/episode/{index}")
async def get_episode(index: int, primary: str = 'zh'):
    """
    Get episode data with merged subtitles
    
    Args:
        index: Episode index
        primary: 'zh' or 'en' - which language to use as primary ordering
    """
    if index >= len(current_matches):
        raise HTTPException(status_code=404, detail="Episode not found")
    
    match = current_matches[index]
    
    print(f"\n=== Loading episode {index} with primary={primary} ===")
    
    zh_blocks = []
    if match.get('zh_sub'):
        path = find_file(match['zh_sub'], ZH_DIR)
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if path.endswith('.ass'):
                        zh_blocks = parse_ass(content)
                    else:
                        zh_blocks = parse_srt(content)
                    print(f"Loaded {len(zh_blocks)} Chinese blocks")
            except UnicodeDecodeError:
                try:
                    with open(path, 'r', encoding='gbk', errors='ignore') as f:
                        content = f.read()
                        if path.endswith('.ass'):
                            zh_blocks = parse_ass(content)
                        else:
                            zh_blocks = parse_srt(content)
                except:
                    pass

    en_blocks = []
    if match.get('en_sub'):
        path = find_file(match['en_sub'], EN_DIR)
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if path.endswith('.ass'):
                        en_blocks = parse_ass(content)
                    else:
                        en_blocks = parse_srt(content)
                    print(f"Loaded {len(en_blocks)} Foreign blocks")
            except UnicodeDecodeError:
                try:
                    with open(path, 'r', encoding='gbk', errors='ignore') as f:
                        content = f.read()
                        if path.endswith('.ass'):
                            en_blocks = parse_ass(content)
                        else:
                            en_blocks = parse_srt(content)
                except:
                    pass
    
    # Merge blocks by time instead of index
    merged_blocks = merge_blocks_by_time(zh_blocks, en_blocks, primary=primary)
    print(f"Merged to {len(merged_blocks)} blocks")
                    
    return {
        "blocks": merged_blocks,
        "video_path": match.get('video'),
        "zh_file": match.get('zh_sub'),
        "en_file": match.get('en_sub')
    }

@app.post("/api/save")
async def save_subtitle(req: SaveRequest):
    search_dir = ZH_DIR if req.type == 'zh' else EN_DIR
    path = find_file(req.filename, search_dir)
    
    if not path:
        path = os.path.join(search_dir, req.filename)
        
    with open(path, 'w', encoding='utf-8') as f:
        f.write(req.content)
        
    return {"message": "Saved"}

@app.post("/api/update-block")
async def update_block(req: UpdateBlockRequest):
    """Update a single subtitle block"""
    if req.episode_index >= len(current_matches):
        raise HTTPException(status_code=404, detail="Episode not found")
    
    match = current_matches[req.episode_index]
    file_key = 'zh_sub' if req.type == 'zh' else 'en_sub'
    
    if not match.get(file_key):
        raise HTTPException(status_code=404, detail="Subtitle file not found")
    
    search_dir = ZH_DIR if req.type == 'zh' else EN_DIR
    path = find_file(match[file_key], search_dir)
    
    if not path:
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    # Read existing content
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(path, 'r', encoding='gbk', errors='ignore') as f:
            content = f.read()
    
    blocks = parse_srt(content)
    
    # Update the specific block
    if req.block_index < len(blocks):
        blocks[req.block_index]['text'] = req.text
        # Update time if provided
        if req.start is not None:
            blocks[req.block_index]['start'] = req.start
        if req.end is not None:
            blocks[req.block_index]['end'] = req.end
        
        # Write back
        new_content = blocks_to_srt(blocks)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return {"message": "Block updated"}
    else:
        raise HTTPException(status_code=404, detail="Block index out of range")

@app.post("/api/save-all-blocks")
async def save_all_blocks(req: SaveAllBlocksRequest):
    """Save all blocks for an episode (used when splitting/reorganizing)"""
    if req.episode_index >= len(current_matches):
        raise HTTPException(status_code=404, detail="Episode not found")
    
    match = current_matches[req.episode_index]
    file_key = 'zh_sub' if req.type == 'zh' else 'en_sub'
    
    if not match.get(file_key):
        raise HTTPException(status_code=404, detail="Subtitle file not found")
    
    search_dir = ZH_DIR if req.type == 'zh' else EN_DIR
    path = find_file(match[file_key], search_dir)
    
    if not path:
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    # Ensure output path is .srt format
    if not path.endswith('.srt'):
        # Change extension to .srt
        base_path = os.path.splitext(path)[0]
        path = base_path + '.srt'
    
    # Convert blocks to SRT format
    # The blocks from frontend have: index, start, end, zh_text, en_text
    # We need to extract the appropriate text field and reindex
    srt_blocks = []
    for i, block in enumerate(req.blocks):
        text_field = 'zh_text' if req.type == 'zh' else 'en_text'
        text = block.get(text_field, block.get('text', ''))
        
        # Only include blocks that have content
        if text and text.strip():
            srt_blocks.append({
                'index': len(srt_blocks) + 1,  # Sequential indexing starting from 1
                'start': block['start'],
                'end': block['end'],
                'text': text
            })
    
    # Write to file in SRT format
    new_content = blocks_to_srt(srt_blocks)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"Saved {len(srt_blocks)} blocks to {path}")
    
    return {"message": "All blocks saved", "count": len(srt_blocks), "path": path}
    
    return {"message": "All blocks saved"}


@app.post("/api/correct")
async def correct_subtitle(req: CorrectRequest):
    corrected = correct_text_with_gpt(req.content, req.rules)
    if corrected:
        return {"content": corrected}
    else:
        raise HTTPException(status_code=500, detail="Correction failed")

@app.get("/video/stream")
async def video_stream(path: str, request: Request):
    if not video_base_path:
        raise HTTPException(status_code=400, detail="Video path not set")
        
    full_path = os.path.join(video_base_path, path)
    if not os.path.exists(full_path):
        found = find_file(path, video_base_path)
        if found:
            full_path = found
        else:
            raise HTTPException(status_code=404, detail="Video not found")
            
    file_size = os.path.getsize(full_path)
    range_header = request.headers.get("range")
    
    start = 0
    end = file_size - 1
    
    if range_header:
        range_header = range_header.strip().lower().replace("bytes=", "")
        parts = range_header.split("-")
        try:
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
        except ValueError:
            pass
            
    if start >= file_size:
        start = file_size - 1
    if end >= file_size:
        end = file_size - 1
        
    chunk_size = end - start + 1
    
    # Limit chunk size to avoid memory issues
    MAX_CHUNK = 1024 * 1024 * 5 # 5MB
    if chunk_size > MAX_CHUNK:
        chunk_size = MAX_CHUNK
        end = start + chunk_size - 1
        
    with open(full_path, "rb") as video:
        video.seek(start)
        data = video.read(chunk_size)
        
    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
        "Content-Type": "video/mp4",
    }
    
    return Response(content=data, status_code=206, headers=headers)

@app.get("/api/export/en")
async def export_en():
    # Create a zip of the EN_DIR
    shutil.make_archive("export_en", 'zip', EN_DIR)
    return FileResponse("export_en.zip", filename="export_en.zip")

# Serve frontend
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
