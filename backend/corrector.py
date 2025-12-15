import requests
import json
import re
import os
import configparser
import sys

# --- Load Configuration from INI file ---
config = configparser.ConfigParser()
# Determine config file path
if getattr(sys, 'frozen', False):
    config_path = os.path.join(os.path.dirname(sys.executable), 'config.ini')
else:
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')

print(f"[corrector.py] Loading config from: {config_path}")
print(f"[corrector.py] sys.frozen = {getattr(sys, 'frozen', False)}")
print(f"[corrector.py] Config file exists: {os.path.exists(config_path)}")

if not os.path.exists(config_path):
    raise FileNotFoundError(f"请创建配置文件: {config_path}\n可以复制 config.ini.example 并填入你的API密钥")

config.read(config_path, encoding='utf-8')
CHATGPT_ENDPOINT = config.get('API', 'chatgpt_endpoint')
API_KEY = config.get('API', 'api_key')

print(f"[corrector.py] Loaded endpoint: {CHATGPT_ENDPOINT}")
print(f"[corrector.py] API key loaded: {API_KEY[:10]}..." if API_KEY else "[corrector.py] API key is empty!")

# --- Spanish articles and object pronouns for line splitting ---
ARTICLES = {
    'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'del', 'al'
}
OBJECT_PRONOUNS = {
    'lo', 'la', 'los', 'las', 'le', 'les', 'me', 'te', 'se', 'nos', 'os'
}

def count_srt_blocks(content):
    """Count the number of subtitle blocks in SRT content."""
    srt_block_pattern = re.compile(
        r'^\d+\s*[\r\n]+'
        r'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\s*[\r\n]+'
        r'.+?(?=\s*[\r\n]{2,}\d+|\s*$)',
        re.DOTALL | re.MULTILINE
    )
    return len(srt_block_pattern.findall(content))

def is_valid_srt(content):
    """Validates the basic structure of SRT content."""
    # Regex to match a single SRT block
    srt_block_pattern = re.compile(
        r'^\d+\s*[\r\n]+'
        r'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\s*[\r\n]+'
        r'(.+?)\s*([\r\n]{2,}|$)',
        re.DOTALL | re.MULTILINE
    )
    
    content = content.strip()
    if not content:
        return True
    
    last_pos = 0
    for match in srt_block_pattern.finditer(content):
        if match.start() != last_pos:
            return False
        last_pos = match.end()

    return last_pos == len(content)

def split_long_line(text, threshold=40):
    """Split long subtitle lines intelligently, avoiding breaks at articles/pronouns"""
    text = text.strip()
    if len(text) <= threshold:
        return text
    words = text.split()
    best_split = {'diff': float('inf'), 'first': '', 'second': ''}
    for i in range(1, len(words)):
        first_line = ' '.join(words[:i])
        second_line = ' '.join(words[i:])
        if len(first_line) <= threshold and len(second_line) <= threshold:
            last_word = words[i - 1].lower()
            # Avoid splitting after articles or object pronouns
            if last_word in ARTICLES or last_word in OBJECT_PRONOUNS:
                continue
            diff = abs(len(second_line) - len(first_line))
            if diff < best_split['diff']:
                best_split = {
                    'diff': diff,
                    'first': first_line.rstrip(),
                    'second': second_line.rstrip()
                }
    if best_split['diff'] == float('inf'):
        return text
    return f"{best_split['first']}\n{best_split['second']}"

def apply_line_split_to_srt(srt_content, threshold=40):
    """Apply split logic to all subtitle blocks"""
    srt_block_pattern = re.compile(
        r'(\d+\s*[\r\n]+\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\s*[\r\n]+)(.+?)(?=\s*[\r\n]{2,}\d+|\s*$)',
        re.DOTALL
    )
    blocks = srt_block_pattern.findall(srt_content)
    new_blocks = []
    for header, text in blocks:
        lines = text.strip().splitlines()
        split_lines = [split_long_line(line, threshold) for line in lines]
        new_text = '\n'.join(split_lines)
        new_blocks.append(f"{header.strip()}\n{new_text}")
    return '\n\n'.join(new_blocks) + '\n\n'

def load_rules():
    """Load correction rules from file"""
    print("\n=== Loading correction rules ===")
    
    # Determine rules file path (same logic as config.ini)
    if getattr(sys, 'frozen', False):
        # 打包后：在 exe 所在目录查找
        base_path = os.path.dirname(sys.executable)
        rules_path = os.path.join(base_path, 'rules.txt')
    else:
        # 开发环境：在项目根目录查找
        base_path = os.path.dirname(os.path.dirname(__file__))
        rules_path = os.path.join(base_path, 'rules.txt')
    
    possible_paths = [rules_path]
    
    print(f"Current working directory: {os.getcwd()}")
    print(f"Base path: {base_path}")
    print(f"Searching for rules.txt in:")
    
    for path in possible_paths:
        abs_path = os.path.abspath(path)
        print(f"  Trying: {abs_path}")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    rules = f.read().strip()
                    print(f"✓ SUCCESS: Loaded rules from: {abs_path}")
                    print(f"Rules length: {len(rules)} characters")
                    print(f"Rules preview (first 200 chars):\n{rules[:200]}...")
                    return rules
            except Exception as e:
                print(f"  Failed to read with UTF-8: {e}")
                try:
                    with open(path, 'r', encoding='gbk') as f:
                        rules = f.read().strip()
                        print(f"✓ SUCCESS: Loaded rules from: {abs_path} (GBK encoding)")
                        print(f"Rules length: {len(rules)} characters")
                        print(f"Rules preview (first 200 chars):\n{rules[:200]}...")
                        return rules
                except Exception as e2:
                    print(f"  Failed to read with GBK: {e2}")
        else:
            print(f"  File not found")
    
    print("✗ WARNING: rules.txt not found in any location, using default rules")
    default_rules = """1. Remove any SDH tags like [MUSIC], (LAUGHS).
2. Fix common OCR errors.
3. Ensure proper capitalization and punctuation.
4. Do not translate, keep original language."""
    return default_rules

def correct_text_with_gpt(text, rules=None):
    """Corrects the entire SRT content using the Gemini API based on the provided rules."""
    print("\n=== Starting subtitle correction ===")
    
    if rules is None or rules == '':
        print("No rules provided, loading from file...")
        rules = load_rules()
    else:
        print(f"Using provided rules ({len(rules)} chars)")
    
    print(f"Text to correct: {len(text)} characters")
    print(f"First 100 chars of text: {text[:100]}...")
    
    # Count original subtitle blocks
    original_block_count = count_srt_blocks(text)
    print(f"Original subtitle blocks: {original_block_count}")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    prompt = (
        "Please correct the subtitle text in the following SRT file content based on these rules. "
        f"IMPORTANT: Do not change the subtitle numbers or timestamps. Only modify the text portions. "
        f"The result MUST contain exactly {original_block_count} subtitle blocks.\n\n"
        f"Rules:\n{rules}\n\n"
        f"SRT Content:\n{text}"
    )
    
    print(f"Prompt length: {len(prompt)} characters")
    
    data = {
        "model": "gemini-2.5-flash",
        "messages": [{"role": "user", "content": prompt}]
    }
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            print(f"Sending request to API (attempt {attempt + 1}/{max_retries})...")
            response = requests.post(CHATGPT_ENDPOINT, headers=headers, data=json.dumps(data), timeout=180)
            print(f"Response status: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            corrected = result['choices'][0]['message']['content'].strip()
            print(f"Received corrected text: {len(corrected)} characters")
            print(f"First 100 chars of corrected: {corrected[:100]}...")
            
            # Clean up markdown code blocks
            print("Cleaning up markdown formatting...")
            if corrected.startswith("```srt"):
                corrected = corrected[6:].strip()
                print("Removed ```srt wrapper")
            if corrected.startswith("```"):
                corrected = corrected[3:].strip()
                print("Removed ``` wrapper")
            if corrected.endswith("```"):
                corrected = corrected[:-3].strip()
                print("Removed trailing ```")
            
            # Apply local line split logic
            print("Applying intelligent line splitting (threshold=40 chars)...")
            corrected = apply_line_split_to_srt(corrected, threshold=40)
            
            # Validate and fix SRT format
            print("Validating SRT format...")
            if not is_valid_srt(corrected):
                if is_valid_srt(corrected + "\n\n"):
                    corrected += "\n\n"
                    print("✓ Auto-fixed: Added trailing newlines")
                else:
                    print("⚠ WARNING: Corrected content may have formatting issues")
            else:
                print("✓ SRT format validation passed")
            
            # Verify subtitle block count
            corrected_block_count = count_srt_blocks(corrected)
            print(f"Corrected subtitle blocks: {corrected_block_count}")
            
            if corrected_block_count != original_block_count:
                print(f"✗ Block count mismatch! Expected {original_block_count}, got {corrected_block_count}")
                if attempt < max_retries - 1:
                    print(f"Retrying... ({attempt + 2}/{max_retries})")
                    # Update prompt to emphasize block count requirement
                    data['messages'].append({
                        "role": "assistant",
                        "content": corrected
                    })
                    data['messages'].append({
                        "role": "user",
                        "content": f"Error: The result has {corrected_block_count} subtitle blocks, but it should have exactly {original_block_count} blocks. Please correct this and ensure all {original_block_count} subtitle blocks are present with their original timestamps."
                    })
                    continue
                else:
                    print(f"✗ Failed after {max_retries} attempts. Returning None.")
                    return None
            else:
                print("✓ Block count matches original!")
            
            print("=== Correction completed successfully ===\n")
            return corrected
            
        except requests.exceptions.RequestException as e:
            print(f"✗ API call failed: {e}")
            import traceback
            traceback.print_exc()
            if attempt < max_retries - 1:
                print(f"Retrying... ({attempt + 2}/{max_retries})")
                continue
            return None
    
    return None
