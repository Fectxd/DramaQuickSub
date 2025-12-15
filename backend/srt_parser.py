import re
from typing import List, Dict

def parse_srt(content: str) -> List[Dict]:
    """Parse SRT content into a list of subtitle blocks"""
    blocks = []
    
    # Split by double newlines
    parts = re.split(r'\n\s*\n', content.strip())
    
    for part in parts:
        lines = part.strip().split('\n')
        if len(lines) < 3:
            continue
            
        try:
            # First line is index
            index = int(lines[0].strip())
            
            # Second line is timestamp
            timestamp = lines[1].strip()
            
            # Remaining lines are text
            text = '\n'.join(lines[2:])
            
            # Parse timestamp
            time_match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', timestamp)
            if time_match:
                start_time = time_match.group(1)
                end_time = time_match.group(2)
                
                blocks.append({
                    'index': index,
                    'start': start_time,
                    'end': end_time,
                    'text': text
                })
        except (ValueError, IndexError):
            continue
    
    return blocks

def parse_ass(content: str) -> List[Dict]:
    """Parse ASS/SSA content into a list of subtitle blocks"""
    blocks = []
    lines = content.split('\n')
    
    # Find the Events section
    in_events = False
    format_line = None
    
    for line in lines:
        line = line.strip()
        
        if line.startswith('[Events]'):
            in_events = True
            continue
        
        if in_events:
            if line.startswith('Format:'):
                format_line = line[7:].strip()
                continue
            
            if line.startswith('Dialogue:'):
                # Parse dialogue line
                # Format: Dialogue: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
                parts = line[9:].split(',', 9)
                if len(parts) >= 10:
                    start = parts[1].strip()
                    end = parts[2].strip()
                    text = parts[9].strip()
                    
                    # Convert ASS time format (0:00:09.96) to SRT format (00:00:09,960)
                    start_srt = ass_time_to_srt(start)
                    end_srt = ass_time_to_srt(end)
                    
                    blocks.append({
                        'index': len(blocks) + 1,
                        'start': start_srt,
                        'end': end_srt,
                        'text': text
                    })
    
    return blocks

def ass_time_to_srt(ass_time: str) -> str:
    """Convert ASS time format to SRT format"""
    # ASS: 0:00:09.96 -> SRT: 00:00:09,960
    parts = ass_time.split(':')
    if len(parts) == 3:
        h = parts[0].zfill(2)
        m = parts[1].zfill(2)
        s_ms = parts[2].split('.')
        s = s_ms[0].zfill(2)
        ms = s_ms[1].ljust(3, '0')[:3] if len(s_ms) > 1 else '000'
        return f"{h}:{m}:{s},{ms}"
    return ass_time

def blocks_to_srt(blocks: List[Dict]) -> str:
    """Convert subtitle blocks back to SRT format"""
    srt_parts = []
    
    for block in blocks:
        srt_parts.append(f"{block['index']}\n{block['start']} --> {block['end']}\n{block['text']}\n")
    
    return '\n'.join(srt_parts)

def srt_time_to_ass(srt_time: str) -> str:
    """Convert SRT time format to ASS format"""
    # SRT: 00:00:09,960 -> ASS: 0:00:09.96
    time_part, ms_part = srt_time.split(',')
    h, m, s = time_part.split(':')
    # Remove leading zeros from hours
    h = str(int(h))
    # Convert milliseconds (3 digits) to centiseconds (2 digits)
    cs = ms_part[:2]
    return f"{h}:{m}:{s}.{cs}"

def blocks_to_ass(blocks: List[Dict], original_content: str = None) -> str:
    """Convert subtitle blocks back to ASS format"""
    # If we have original content, preserve the header
    header = ""
    if original_content:
        lines = original_content.split('\n')
        for i, line in enumerate(lines):
            if line.strip().startswith('[Events]'):
                header = '\n'.join(lines[:i+1]) + '\n'
                # Find and add Format line
                for j in range(i+1, len(lines)):
                    if lines[j].strip().startswith('Format:'):
                        header += lines[j] + '\n'
                        break
                break
    
    # Default header if no original content
    if not header:
        header = "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    
    # Add dialogue lines
    dialogue_lines = []
    for block in blocks:
        start_ass = srt_time_to_ass(block['start'])
        end_ass = srt_time_to_ass(block['end'])
        text = block['text']
        dialogue_lines.append(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{text}")
    
    return header + '\n'.join(dialogue_lines) + '\n'

def time_to_seconds(time_str: str) -> float:
    """Convert SRT timestamp to seconds"""
    # Format: 00:00:01,160
    time_part, ms_part = time_str.split(',')
    h, m, s = map(int, time_part.split(':'))
    ms = int(ms_part)
    return h * 3600 + m * 60 + s + ms / 1000.0

def merge_blocks_by_time(zh_blocks: List[Dict], en_blocks: List[Dict], primary: str = 'union', tolerance: float = 0.5) -> List[Dict]:
    """
    Merge subtitle blocks based on time overlap rather than index
    
    Args:
        zh_blocks: Chinese subtitle blocks
        en_blocks: Foreign subtitle blocks
        primary: 'zh', 'en', or 'union' - which language to use as primary for ordering
                 'union' includes all blocks from both languages
        tolerance: Time tolerance in seconds for matching blocks
    
    Returns:
        List of merged blocks with both languages
    """
    merged = []
    
    # Handle union mode - include all blocks from both languages
    if primary == 'union':
        return merge_union(zh_blocks, en_blocks, tolerance)
    
    # Choose primary blocks
    primary_blocks = zh_blocks if primary == 'zh' else en_blocks
    secondary_blocks = en_blocks if primary == 'zh' else zh_blocks
    
    used_secondary = set()
    
    for p_block in primary_blocks:
        p_start = time_to_seconds(p_block['start'])
        p_end = time_to_seconds(p_block['end'])
        p_mid = (p_start + p_end) / 2
        
        # Find matching secondary block
        best_match = None
        best_distance = float('inf')
        
        for i, s_block in enumerate(secondary_blocks):
            if i in used_secondary:
                continue
            
            s_start = time_to_seconds(s_block['start'])
            s_end = time_to_seconds(s_block['end'])
            s_mid = (s_start + s_end) / 2
            
            # Check if time ranges overlap or are very close
            distance = abs(p_mid - s_mid)
            
            # Check overlap
            overlap = min(p_end, s_end) - max(p_start, s_start)
            
            if overlap > 0 or distance < tolerance:
                if distance < best_distance:
                    best_distance = distance
                    best_match = i
        
        # Create merged block
        if primary == 'zh':
            merged_block = {
                'index': len(merged) + 1,
                'start': p_block['start'],
                'end': p_block['end'],
                'zh_text': p_block['text'],
                'en_text': secondary_blocks[best_match]['text'] if best_match is not None else ''
            }
        else:
            merged_block = {
                'index': len(merged) + 1,
                'start': p_block['start'],
                'end': p_block['end'],
                'zh_text': secondary_blocks[best_match]['text'] if best_match is not None else '',
                'en_text': p_block['text']
            }
        
        merged.append(merged_block)
        
        if best_match is not None:
            used_secondary.add(best_match)
    
    # Add unmatched secondary blocks
    for i, s_block in enumerate(secondary_blocks):
        if i not in used_secondary:
            if primary == 'zh':
                merged.append({
                    'index': len(merged) + 1,
                    'start': s_block['start'],
                    'end': s_block['end'],
                    'zh_text': '',
                    'en_text': s_block['text']
                })
            else:
                merged.append({
                    'index': len(merged) + 1,
                    'start': s_block['start'],
                    'end': s_block['end'],
                    'zh_text': s_block['text'],
                    'en_text': ''
                })
    
    # Sort by start time
    merged.sort(key=lambda x: time_to_seconds(x['start']))
    
    # Reindex
    for i, block in enumerate(merged):
        block['index'] = i + 1
    
    return merged

def merge_union(zh_blocks: List[Dict], en_blocks: List[Dict], tolerance: float = 0.5) -> List[Dict]:
    """
    Merge blocks using union mode - include all blocks from both languages
    
    Args:
        zh_blocks: Chinese subtitle blocks
        en_blocks: Foreign subtitle blocks
        tolerance: Time tolerance in seconds for matching blocks
    
    Returns:
        List of merged blocks with all content from both languages
    """
    # Collect all unique time segments from both languages
    all_segments = []
    
    # Add all Chinese blocks as base segments
    for block in zh_blocks:
        all_segments.append({
            'start': block['start'],
            'end': block['end'],
            'start_sec': time_to_seconds(block['start']),
            'end_sec': time_to_seconds(block['end']),
            'zh_text': block['text'],
            'en_text': ''
        })
    
    # Add all Foreign blocks as base segments
    for block in en_blocks:
        all_segments.append({
            'start': block['start'],
            'end': block['end'],
            'start_sec': time_to_seconds(block['start']),
            'end_sec': time_to_seconds(block['end']),
            'zh_text': '',
            'en_text': block['text']
        })
    
    # Sort by start time, then by end time
    all_segments.sort(key=lambda x: (x['start_sec'], x['end_sec']))
    
    # Merge blocks that have exact same time range or significant overlap
    merged = []
    used = set()
    
    for i in range(len(all_segments)):
        if i in used:
            continue
            
        current = all_segments[i].copy()
        used.add(i)
        
        # Look for blocks with same or very similar time range
        for j in range(i + 1, len(all_segments)):
            if j in used:
                continue
            
            other = all_segments[j]
            
            # Calculate overlap
            overlap_start = max(current['start_sec'], other['start_sec'])
            overlap_end = min(current['end_sec'], other['end_sec'])
            overlap = overlap_end - overlap_start
            
            current_duration = current['end_sec'] - current['start_sec']
            other_duration = other['end_sec'] - other['start_sec']
            
            # Check if they represent the same time segment (>80% overlap)
            if overlap > 0 and (overlap / current_duration > 0.8 or overlap / other_duration > 0.8):
                # Merge them - use the earlier start and later end
                if other['start_sec'] < current['start_sec']:
                    current['start'] = other['start']
                    current['start_sec'] = other['start_sec']
                if other['end_sec'] > current['end_sec']:
                    current['end'] = other['end']
                    current['end_sec'] = other['end_sec']
                
                # Merge texts
                if other['zh_text'] and not current['zh_text']:
                    current['zh_text'] = other['zh_text']
                if other['en_text'] and not current['en_text']:
                    current['en_text'] = other['en_text']
                
                used.add(j)
        
        merged.append({
            'index': len(merged) + 1,
            'start': current['start'],
            'end': current['end'],
            'zh_text': current['zh_text'],
            'en_text': current['en_text']
        })
    
    return merged
