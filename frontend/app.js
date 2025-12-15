const API_BASE = "http://localhost:8000/api";
let currentEpisodeIndex = -1;
let allMatches = [];
let currentBlocks = [];
let videoPlayer = null;
let currentTime = 0;
let currentPrimary = 'union'; // 'zh', 'en', or 'union'

// 自定义确认对话框
function customConfirm(message, title = '确认') {
    return new Promise((resolve) => {
        const modal = document.getElementById('custom-confirm-modal');
        const titleEl = document.getElementById('confirm-title');
        const messageEl = document.getElementById('confirm-message');
        const okBtn = document.getElementById('confirm-ok-btn');
        const cancelBtn = document.getElementById('confirm-cancel-btn');
        
        titleEl.textContent = title;
        messageEl.textContent = message;
        modal.classList.add('active');
        
        const cleanup = (result) => {
            modal.classList.remove('active');
            okBtn.onclick = null;
            cancelBtn.onclick = null;
            resolve(result);
        };
        
        okBtn.onclick = () => cleanup(true);
        cancelBtn.onclick = () => cleanup(false);
    });
}

// 自定义提示对话框
function customAlert(message, title = '提示') {
    return new Promise((resolve) => {
        const modal = document.getElementById('custom-alert-modal');
        const titleEl = document.getElementById('alert-title');
        const messageEl = document.getElementById('alert-message');
        const okBtn = document.getElementById('alert-ok-btn');
        
        titleEl.textContent = title;
        messageEl.textContent = message;
        modal.classList.add('active');
        
        const cleanup = () => {
            modal.classList.remove('active');
            okBtn.onclick = null;
            resolve();
        };
        
        okBtn.onclick = cleanup;
    });
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    videoPlayer = document.getElementById('player');
    videoPlayer.addEventListener('timeupdate', onVideoTimeUpdate);
    videoPlayer.addEventListener('loadedmetadata', () => {
        console.log('Video loaded, duration:', videoPlayer.duration);
    });
});

// File uploads
document.getElementById('zh-zip').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) {
        console.log('No file selected for Chinese subtitles');
        return;
    }
    console.log('Uploading Chinese subtitles:', file.name);
    const formData = new FormData();
    formData.append('file', file);
    try {
        const res = await fetch(`${API_BASE}/upload/zh`, { method: 'POST', body: formData });
        console.log('Upload response:', res.status);
        const data = await res.json();
        console.log('Upload result:', data);
        await customAlert('中文字幕上传成功');
    } catch (e) {
        console.error('Upload failed:', e);
        await customAlert('上传失败: ' + e.message, '错误');
    } finally {
        // Reset file input to allow re-upload of the same file
        e.target.value = '';
    }
});

document.getElementById('en-zip').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) {
        console.log('No file selected for foreign subtitles');
        return;
    }
    console.log('Uploading Foreign subtitles:', file.name);
    const formData = new FormData();
    formData.append('file', file);
    try {
        const res = await fetch(`${API_BASE}/upload/en`, { method: 'POST', body: formData });
        console.log('Upload response:', res.status);
        const data = await res.json();
        console.log('Upload result:', data);
        await customAlert('外语字幕上传成功');
    } catch (e) {
        console.error('Upload failed:', e);
        await customAlert('上传失败: ' + e.message, '错误');
    } finally {
        // Reset file input to allow re-upload of the same file
        e.target.value = '';
    }
});

async function matchFiles() {
    const videoPath = document.getElementById('video-path').value;
    if (!videoPath) {
        await customAlert('请输入视频文件夹路径', '提示');
        return;
    }
    
    const btn = document.querySelector('button[onclick="matchFiles()"]');
    btn.disabled = true;
    btn.textContent = "匹配中...";
    
    try {
        console.log('Sending match request with video path:', videoPath);
        const res = await fetch(`${API_BASE}/match`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_path: videoPath })
        });
        console.log('Response status:', res.status);
        
        if (!res.ok) {
            const error = await res.text();
            console.error('Error response:', error);
            throw new Error(`HTTP ${res.status}: ${error}`);
        }
        
        const matches = await res.json();
        console.log('Matched episodes:', matches);
        
        if (!matches || matches.length === 0) {
            await customAlert('未找到匹配的剧集，请检查文件是否上传成功', '提示');
            return;
        }
        
        allMatches = matches;
        renderList(matches);
        await customAlert(`文件匹配完成！找到 ${matches.length} 集`);
    } catch (e) {
        console.error('Match failed:', e);
        await customAlert('匹配失败: ' + e.message, '错误');
    } finally {
        btn.disabled = false;
        btn.textContent = "匹配文件";
    }
}

async function rematchVideos() {
    if (!allMatches || allMatches.length === 0) {
        await customAlert('请先进行初始文件匹配', '提示');
        return;
    }
    
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = "🔄 重新匹配中...";
    
    try {
        console.log('Sending rematch videos request...');
        const res = await fetch(`${API_BASE}/rematch-videos`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        console.log('Response status:', res.status);
        
        if (!res.ok) {
            const error = await res.text();
            console.error('Error response:', error);
            throw new Error(`HTTP ${res.status}: ${error}`);
        }
        
        const matches = await res.json();
        console.log('Rematched episodes:', matches);
        
        allMatches = matches;
        renderList(matches);
        
        // 如果当前正在查看某集，刷新视频（保留字幕）
        if (currentEpisodeIndex >= 0 && currentEpisodeIndex < matches.length) {
            const match = matches[currentEpisodeIndex];
            if (match.video) {
                const videoPath = `/video/stream?file=${encodeURIComponent(match.video)}`;
                videoPlayer.src = videoPath;
                console.log('Updated video for current episode:', match.video);
            }
        }
        
        await customAlert(`视频重新匹配完成！共 ${matches.length} 集`);
    } catch (e) {
        console.error('Rematch failed:', e);
        await customAlert('重新匹配失败: ' + e.message, '错误');
    } finally {
        btn.disabled = false;
        btn.textContent = "刷新视频";
    }
}

function renderList(matches) {
    const list = document.getElementById('episode-list');
    list.innerHTML = '';
    matches.forEach((m, index) => {
        const div = document.createElement('div');
        div.className = 'episode-item';
        div.textContent = `第${m.episode}集`;
        div.onclick = () => loadEpisode(index);
        
        // Add status indicator - check for truthy values (not null, undefined, or empty string)
        const hasZh = m.zh_sub && m.zh_sub.trim();
        const hasEn = m.en_sub && m.en_sub.trim();
        const hasVideo = m.video && m.video.trim();
        
        if (hasZh && hasEn && hasVideo) {
            div.style.borderLeft = '4px solid #4caf50';
        } else if (!hasZh && !hasEn) {
            div.style.borderLeft = '4px solid #f44336';
        } else {
            div.style.borderLeft = '4px solid #ff9800';
        }
        
        list.appendChild(div);
    });
}

async function loadEpisode(index) {
    // Check if there are unsaved changes
    if (currentEpisodeIndex !== -1 && currentEpisodeIndex !== index && hasUnsavedChanges) {
        const confirmed = await customConfirm('当前剧集有未保存的修改，是否先保存？', '未保存的修改');
        if (confirmed) {
            try {
                await saveAll();
            } catch (e) {
                // 如果保存失败，不继续加载新剧集
                console.error('Save failed, not switching episode:', e);
                return;
            }
        }
        // 无论是否保存，都清除未保存标记，避免bug
        hasUnsavedChanges = false;
    }
    
    currentEpisodeIndex = index;
    try {
        const res = await fetch(`${API_BASE}/episode/${index}?primary=${currentPrimary}`);
        if (!res.ok) throw new Error('Failed to load episode');
        const data = await res.json();
        
        currentBlocks = data.blocks || [];
        renderBlocks(currentBlocks);
        
        // Update info and show primary switch
        const info = document.getElementById('current-episode-info');
        info.textContent = `第${allMatches[index].episode}集 - 共 ${currentBlocks.length} 条字幕`;
        
        document.getElementById('primary-switch').style.display = 'flex';
        document.getElementById('primary-lang').value = currentPrimary;
        
        // Load video
        const placeholder = document.getElementById('video-placeholder');
        if (data.video_path) {
            videoPlayer.src = `http://localhost:8000/video/stream?path=${encodeURIComponent(data.video_path)}`;
            placeholder.style.display = 'none';
        } else {
            videoPlayer.removeAttribute('src');
            placeholder.style.display = 'block';
        }
        
        // Highlight active episode
        document.querySelectorAll('.episode-item').forEach((el, i) => {
            el.classList.toggle('active', i === index);
        });
    } catch (e) {
        await customAlert('加载失败: ' + e, '错误');
    }
}

async function switchPrimary() {
    const select = document.getElementById('primary-lang');
    currentPrimary = select.value;
    console.log('Switching primary to:', currentPrimary);
    
    // Reload current episode with new primary
    if (currentEpisodeIndex !== -1) {
        await loadEpisode(currentEpisodeIndex);
    }
}

function renderBlocks(blocks) {
    const container = document.getElementById('subtitle-blocks');
    container.innerHTML = '';
    
    blocks.forEach((block, index) => {
        const blockDiv = document.createElement('div');
        blockDiv.className = 'subtitle-block';
        blockDiv.id = `block-${index}`;
        
        // Calculate duration and chars per second
        const duration = calculateDuration(block.start, block.end);
        const zhChars = block.zh_text ? block.zh_text.length : 0;
        const enChars = block.en_text ? block.en_text.length : 0;
        const zhLines = block.zh_text ? block.zh_text.split('\n').length : 0;
        const enLines = block.en_text ? block.en_text.split('\n').length : 0;
        const zhCps = duration > 0 ? (zhChars / duration) : 0;
        const enCps = duration > 0 ? (enChars / duration) : 0;
        
        // Check for long lines
        const zhHasLongLine = block.zh_text ? block.zh_text.split('\n').some(line => line.length > 40) : false;
        const enHasLongLine = block.en_text ? block.en_text.split('\n').some(line => line.length > 40) : false;
        
        // Get CPS colors
        const zhCpsColor = getCpsColor(zhCps);
        const enCpsColor = getCpsColor(enCps);
        const zhLineColor = zhHasLongLine ? '#ff0000' : '#666';
        const enLineColor = enHasLongLine ? '#ff0000' : '#666';
        
        blockDiv.innerHTML = `
            <div class="block-header">
                <div class="block-index">${block.index}</div>
                <div class="block-info">
                    <div class="block-time">${block.start} - ${block.end}</div>
                </div>
                <div class="block-controls">
                    <button onclick="jumpToTime('${block.start}')" title="跳转">⏱</button>
                    <button onclick="playBlock('${block.start}', '${block.end}')" title="播放">▶</button>
                    <button onclick="openSplitModal(${index})" title="手动分轴">✂</button>
                    <button onclick="deleteBlock(${index})" title="删除" class="btn-delete">🗑</button>
                </div>
            </div>
            <div class="subtitle-input zh">
                <div class="subtitle-header">
                    <label>中文字幕</label>
                    <div class="subtitle-stats">
                        <span class="char-count">${zhChars} 字符</span>
                        <span class="line-count" style="color: ${zhLineColor}">${zhLines} 行</span>
                        <span class="cps-count" style="color: ${zhCpsColor}">CPS: ${zhCps.toFixed(1)}</span>
                    </div>
                </div>
                <textarea readonly>${escapeHtml(block.zh_text)}</textarea>
            </div>
            <div class="subtitle-input en">
                <div class="subtitle-header">
                    <label>外语字幕</label>
                    <div class="subtitle-stats">
                        <span class="char-count">${enChars} 字符</span>
                        <span class="line-count" style="color: ${enLineColor}">${enLines} 行</span>
                        <span class="cps-count" style="color: ${enCpsColor}">CPS: ${enCps.toFixed(1)}</span>
                    </div>
                </div>
                <textarea id="en-${index}" oninput="onBlockEdit(${index})">${escapeHtml(block.en_text)}</textarea>
            </div>
        `;
        
        container.appendChild(blockDiv);
        
        // Auto-resize textareas
        const zhTextarea = blockDiv.querySelector('.subtitle-input.zh textarea');
        const enTextarea = blockDiv.querySelector('.subtitle-input.en textarea');
        autoResizeTextarea(zhTextarea);
        autoResizeTextarea(enTextarea);
    });
}

function calculateDuration(start, end) {
    const startSec = timeToSeconds(start);
    const endSec = timeToSeconds(end);
    return endSec - startSec;
}

function timeToSeconds(timeStr) {
    // Format: 00:00:01,160
    const [time, ms] = timeStr.split(',');
    const [h, m, s] = time.split(':').map(Number);
    return h * 3600 + m * 60 + s + parseInt(ms) / 1000;
}

function secondsToTime(seconds) {
    // 确保输入是有效数字
    if (isNaN(seconds) || seconds < 0) seconds = 0;
    
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    // 精确计算毫秒部分，避免浮点误差
    const ms = Math.round((seconds - Math.floor(seconds)) * 1000);
    return `${pad(h)}:${pad(m)}:${pad(s)},${pad(ms, 3)}`;
}

function pad(num, size = 2) {
    let s = num + "";
    while (s.length < size) s = "0" + s;
    return s;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function jumpToTime(timeStr) {
    if (videoPlayer.src) {
        videoPlayer.currentTime = timeToSeconds(timeStr);
        videoPlayer.play();
    }
}

function playBlock(startStr, endStr) {
    if (!videoPlayer.src) return;
    
    const start = timeToSeconds(startStr);
    const end = timeToSeconds(endStr);
    
    videoPlayer.currentTime = start;
    videoPlayer.play();
    
    // Stop at end time
    const checkTime = setInterval(() => {
        if (videoPlayer.currentTime >= end) {
            videoPlayer.pause();
            clearInterval(checkTime);
        }
    }, 100);
}

function onVideoTimeUpdate() {
    currentTime = videoPlayer.currentTime;
    highlightCurrentBlock();
    updateSubtitleOverlay();
}

function updateSubtitleOverlay() {
    const overlay = document.getElementById('subtitle-overlay');
    if (!overlay) return;
    
    // Find current subtitle block
    let currentBlock = null;
    for (let i = 0; i < currentBlocks.length; i++) {
        const block = currentBlocks[i];
        const start = timeToSeconds(block.start);
        const end = timeToSeconds(block.end);
        
        if (currentTime >= start && currentTime <= end) {
            currentBlock = block;
            break;
        }
    }
    
    if (currentBlock && currentBlock.en_text) {
        overlay.textContent = currentBlock.en_text;
        overlay.style.display = 'block';
    } else {
        overlay.style.display = 'none';
    }
}

function highlightCurrentBlock() {
    currentBlocks.forEach((block, index) => {
        const start = timeToSeconds(block.start);
        const end = timeToSeconds(block.end);
        const blockEl = document.getElementById(`block-${index}`);
        
        if (blockEl) {
            if (currentTime >= start && currentTime <= end) {
                blockEl.classList.add('active');
                // Scroll into view
                if (!isInViewport(blockEl)) {
                    blockEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            } else {
                blockEl.classList.remove('active');
            }
        }
    });
}

function isInViewport(element) {
    const rect = element.getBoundingClientRect();
    const container = document.getElementById('subtitle-blocks');
    const containerRect = container.getBoundingClientRect();
    return (
        rect.top >= containerRect.top &&
        rect.bottom <= containerRect.bottom
    );
}

let saveTimeout = null;
let hasUnsavedChanges = false;

function onBlockEdit(index) {
    const textarea = document.getElementById(`en-${index}`);
    const newText = textarea.value;
    
    // Update local data
    currentBlocks[index].en_text = newText;
    
    // Mark as having unsaved changes
    hasUnsavedChanges = true;
    
    // Auto-resize textarea
    autoResizeTextarea(textarea);
    
    // Update stats
    updateBlockStats(index, 'en');
    
    // Update video subtitle overlay if this is the current playing block
    updateSubtitleOverlay();
    
    // Note: Auto-save removed - user must click "保存当前集" to save changes
    // This ensures we save complete subtitle files, not partial updates
}

function updateBlockStats(index, type) {
    const block = currentBlocks[index];
    const blockDiv = document.getElementById(`block-${index}`);
    if (!blockDiv) return;
    
    const duration = calculateDuration(block.start, block.end);
    const text = type === 'zh' ? block.zh_text : block.en_text;
    const chars = text ? text.length : 0;
    const lines = text ? text.split('\n').length : 0;
    const cps = duration > 0 ? (chars / duration) : 0;
    
    // Check for long lines
    const hasLongLine = text ? text.split('\n').some(line => line.length > 40) : false;
    
    // Get colors
    const cpsColor = getCpsColor(cps);
    const lineColor = hasLongLine ? '#ff0000' : '#666';
    
    // Update the stats display
    const inputDiv = blockDiv.querySelector(`.subtitle-input.${type}`);
    if (inputDiv) {
        const statsDiv = inputDiv.querySelector('.subtitle-stats');
        if (statsDiv) {
            statsDiv.innerHTML = `
                <span class="char-count">${chars} 字符</span>
                <span class="line-count" style="color: ${lineColor}">${lines} 行</span>
                <span class="cps-count" style="color: ${cpsColor}">CPS: ${cps.toFixed(1)}</span>
            `;
        }
    }
}

function getCpsColor(cps) {
    if (cps < 15) return '#666';  // Normal gray
    if (cps >= 27) return '#ff0000';  // Full red
    
    // Gradient from yellow to red (15-27)
    const ratio = (cps - 15) / (27 - 15);  // 0 to 1
    const red = 255;
    const green = Math.round(255 * (1 - ratio));  // 255 to 0
    return `rgb(${red}, ${green}, 0)`;
}

function autoResizeTextarea(textarea) {
    if (!textarea) return;
    
    // Reset height to auto to get the correct scrollHeight
    textarea.style.height = 'auto';
    
    // Set height to scrollHeight (content height)
    const newHeight = Math.max(24, textarea.scrollHeight);
    textarea.style.height = newHeight + 'px';
}

function checkForUnsavedChanges() {
    return hasUnsavedChanges;
}

async function saveBlock(index) {
    if (currentEpisodeIndex === -1) return;
    
    try {
        const block = currentBlocks[index];
        await fetch(`${API_BASE}/update-block`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                episode_index: currentEpisodeIndex,
                block_index: index,
                text: block.en_text,
                type: 'en',
                start: block.start,
                end: block.end
            })
        });
        // Silent save
    } catch (e) {
        console.error('自动保存失败:', e);
    }
}

async function saveAll() {
    if (currentEpisodeIndex === -1) return;
    
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = "保存中...";
    
    try {
        // Collect all blocks with updated content from textarea
        const updatedBlocks = currentBlocks.map((block, index) => {
            const textarea = document.getElementById(`en-${index}`);
            if (textarea) {
                block.en_text = textarea.value;
            }
            return block;
        });
        
        // Save Chinese subtitles (extract only Chinese blocks)
        const zhBlocks = updatedBlocks.filter(b => b.zh_text && b.zh_text.trim());
        if (zhBlocks.length > 0) {
            await fetch(`${API_BASE}/save-all-blocks`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    episode_index: currentEpisodeIndex,
                    blocks: zhBlocks,
                    type: 'zh'
                })
            });
        }
        
        // Save Foreign subtitles (extract only Foreign blocks)
        const enBlocks = updatedBlocks.filter(b => b.en_text && b.en_text.trim());
        if (enBlocks.length > 0) {
            await fetch(`${API_BASE}/save-all-blocks`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    episode_index: currentEpisodeIndex,
                    blocks: enBlocks,
                    type: 'en'
                })
            });
        }
        
        hasUnsavedChanges = false;
        await customAlert('保存成功！');
    } catch (e) {
        console.error('保存失败:', e);
        await customAlert('保存失败: ' + e.message, '错误');
        throw e;
    } finally {
        btn.disabled = false;
        btn.textContent = "保存当前集";
    }
}

async function correctCurrent() {
    if (currentEpisodeIndex === -1) return;
    
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = "保存中...";
    
    try {
        // Auto-save before correction
        if (hasUnsavedChanges) {
            console.log('Auto-saving before AI correction...');
            await saveAll();
        }
        
        btn.textContent = "AI修正中...";
        
        // Reconstruct full SRT
        let srtContent = '';
        currentBlocks.forEach(block => {
            srtContent += `${block.index}\n${block.start} --> ${block.end}\n${block.en_text}\n\n`;
        });
        
        // Send empty rules - backend will auto-load from rules.txt
        const res = await fetch(`${API_BASE}/correct`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: srtContent, rules: '' })
        });
        
        if (!res.ok) throw new Error('Correction failed');
        
        const data = await res.json();
        
        // Parse corrected content and update blocks
        const lines = data.content.split('\n');
        let blockIndex = 0;
        let i = 0;
        
        while (i < lines.length) {
            if (lines[i].trim() && /^\d+$/.test(lines[i].trim())) {
                // Skip index line
                i++;
                // Skip timestamp line
                if (i < lines.length && lines[i].includes('-->')) {
                    i++;
                }
                // Collect text lines
                let text = '';
                while (i < lines.length && lines[i].trim() && !lines[i].includes('-->')) {
                    text += (text ? '\n' : '') + lines[i];
                    i++;
                }
                
                if (blockIndex < currentBlocks.length) {
                    currentBlocks[blockIndex].en_text = text;
                    const textarea = document.getElementById(`en-${blockIndex}`);
                    if (textarea) {
                        textarea.value = text;
                        // Update char count
                        const charCountEl = textarea.parentElement.querySelector('.char-count');
                        const chars = text.length;
                        const textLines = text.split('\n').length;
                        charCountEl.textContent = `${chars} 字符 | ${textLines} 行`;
                    }
                    blockIndex++;
                }
            }
            i++;
        }
        
        await customAlert('AI修正完成！已应用"rules.txt"中的规则，请检查并保存');
    } catch (e) {
        await customAlert('修正失败: ' + e, '错误');
    } finally {
        btn.disabled = false;
        btn.textContent = "AI修正当前集";
    }
}

function exportEn() {
    window.open(`${API_BASE}/export/en`, '_blank');
}

// ============= 手动分轴功能 =============
let splitModalData = {
    blockIndex: -1,
    startTime: 0,
    endTime: 0,
    duration: 0,
    splitPoints: [], // Array of time points in seconds
    originalText: ''
};

let splitVideoPlayer = null;
let splitUpdateInterval = null;

function openSplitModal(blockIndex) {
    if (blockIndex >= currentBlocks.length) return;
    
    const block = currentBlocks[blockIndex];
    const modal = document.getElementById('split-modal');
    splitVideoPlayer = document.getElementById('split-video');
    
    // Initialize modal data
    splitModalData = {
        blockIndex: blockIndex,
        startTime: timeToSeconds(block.start),
        endTime: timeToSeconds(block.end),
        duration: timeToSeconds(block.end) - timeToSeconds(block.start),
        splitPoints: [],
        originalText: block.en_text,
        originalZhText: block.zh_text
    };
    
    // Set video source and time range
    if (videoPlayer.src) {
        splitVideoPlayer.src = videoPlayer.src;
        splitVideoPlayer.currentTime = splitModalData.startTime;
    }
    
    // Display original texts
    document.getElementById('split-zh-text').textContent = block.zh_text || '(无中文字幕)';
    document.getElementById('split-en-text').textContent = block.en_text || '(无外文字幕)';
    
    // Show modal
    modal.classList.add('active');
    
    // Start time update
    splitVideoPlayer.addEventListener('timeupdate', updateSplitProgress);
    
    // Timeline click handler
    document.getElementById('split-timeline').onclick = seekSplitVideo;
    
    // Initialize display
    renderSplitSegments();
    
    console.log('Split modal opened for block', blockIndex, splitModalData);
}

function closeSplitModal() {
    const modal = document.getElementById('split-modal');
    modal.classList.remove('active');
    
    if (splitVideoPlayer) {
        splitVideoPlayer.pause();
        splitVideoPlayer.removeEventListener('timeupdate', updateSplitProgress);
    }
    
    splitModalData = {
        blockIndex: -1,
        startTime: 0,
        endTime: 0,
        duration: 0,
        splitPoints: [],
        originalText: ''
    };
}

function updateSplitProgress() {
    if (!splitVideoPlayer) return;
    
    const currentTime = splitVideoPlayer.currentTime;
    const relativeTime = currentTime - splitModalData.startTime;
    
    // Keep video in range
    if (currentTime < splitModalData.startTime) {
        splitVideoPlayer.currentTime = splitModalData.startTime;
    } else if (currentTime > splitModalData.endTime) {
        splitVideoPlayer.pause();
        splitVideoPlayer.currentTime = splitModalData.startTime;
    }
    
    // Update progress bar
    const progress = (relativeTime / splitModalData.duration) * 100;
    document.getElementById('split-progress').style.width = Math.max(0, Math.min(100, progress)) + '%';
    
    // Update time display
    const timeInfo = document.getElementById('split-time-info');
    timeInfo.textContent = `${secondsToTime(currentTime)} / ${secondsToTime(splitModalData.endTime)}`;
    
    // Update subtitle display
    updateSplitSubtitleDisplay(relativeTime);
}

function updateSplitSubtitleDisplay(relativeTime) {
    const segments = getSplitSegments();
    const display = document.getElementById('split-subtitle-display');
    
    for (let i = 0; i < segments.length; i++) {
        const seg = segments[i];
        if (relativeTime >= seg.start && relativeTime < seg.end) {
            display.textContent = seg.text;
            display.style.display = 'block';
            return;
        }
    }
    
    display.style.display = 'none';
}

function seekSplitVideo(e) {
    const timeline = document.getElementById('split-timeline');
    const rect = timeline.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percent = x / rect.width;
    const seekTime = splitModalData.startTime + (percent * splitModalData.duration);
    
    if (splitVideoPlayer) {
        splitVideoPlayer.currentTime = seekTime;
    }
}

async function addSplitPoint() {
    if (!splitVideoPlayer) return;
    
    const currentTime = splitVideoPlayer.currentTime;
    const relativeTime = currentTime - splitModalData.startTime;
    
    // Check if already exists
    if (splitModalData.splitPoints.includes(relativeTime)) {
        await customAlert('此位置已有分割点', '提示');
        return;
    }
    
    splitModalData.splitPoints.push(relativeTime);
    splitModalData.splitPoints.sort((a, b) => a - b);
    
    console.log('Added split point at', relativeTime, 'seconds');
    renderSplitSegments();
}

function removeSplitPoint(index) {
    splitModalData.splitPoints.splice(index, 1);
    renderSplitSegments();
}

function getSplitSegments() {
    const points = [0, ...splitModalData.splitPoints, splitModalData.duration];
    const segments = [];
    
    for (let i = 0; i < points.length - 1; i++) {
        segments.push({
            index: i,
            start: points[i],
            end: points[i + 1],
            text: '' // Will be filled by user
        });
    }
    
    return segments;
}

function renderSplitSegments() {
    const segments = getSplitSegments();
    
    // Render markers
    const markersDiv = document.getElementById('split-markers');
    markersDiv.innerHTML = '';
    
    splitModalData.splitPoints.forEach((point, index) => {
        const percent = (point / splitModalData.duration) * 100;
        const marker = document.createElement('div');
        marker.className = 'split-marker';
        marker.style.left = percent + '%';
        marker.title = `分割点 ${index + 1}: ${secondsToTime(splitModalData.startTime + point)}`;
        marker.onclick = () => removeSplitPoint(index);
        markersDiv.appendChild(marker);
    });
    
    // Render segments
    const segmentsDiv = document.getElementById('split-segments');
    segmentsDiv.innerHTML = '';
    
    segments.forEach((seg, index) => {
        const segDiv = document.createElement('div');
        segDiv.className = 'split-segment';
        
        const startTime = secondsToTime(splitModalData.startTime + seg.start);
        const endTime = secondsToTime(splitModalData.startTime + seg.end);
        const duration = (seg.end - seg.start).toFixed(1);
        
        segDiv.innerHTML = `
            <div class="split-segment-header">
                <span><strong>段落 ${index + 1}</strong> - ${startTime} → ${endTime} (${duration}秒)</span>
                ${index > 0 ? `<button class="btn-remove-marker" onclick="removeSplitPoint(${index - 1})">删除分割点</button>` : ''}
            </div>
            <textarea id="split-text-${index}" placeholder="请输入这段的字幕文本...">${escapeHtml(seg.text)}</textarea>
        `;
        
        segmentsDiv.appendChild(segDiv);
    });
}

// Copy to clipboard helper
function copyToClipboard(elementId) {
    const element = document.getElementById(elementId);
    const text = element.textContent;
    
    navigator.clipboard.writeText(text).then(() => {
        // Show feedback
        const btn = event.target;
        const originalText = btn.textContent;
        btn.textContent = '✓ 已复制';
        setTimeout(() => {
            btn.textContent = originalText;
        }, 1500);
    }).catch(async (err) => {
        await customAlert('复制失败: ' + err, '错误');
    });
}

// Delete subtitle block
async function deleteBlock(blockIndex) {
    if (currentEpisodeIndex === -1) return;
    if (blockIndex < 0 || blockIndex >= currentBlocks.length) return;
    
    const block = currentBlocks[blockIndex];
    const confirmed = await customConfirm(`确定要删除第 ${block.index} 条字幕吗？\n${block.start} - ${block.end}`, '确认删除');
    if (!confirmed) {
        return;
    }
    
    // Remove block
    currentBlocks.splice(blockIndex, 1);
    
    // Reindex remaining blocks
    currentBlocks.forEach((block, i) => {
        block.index = i + 1;
    });
    
    // Re-render
    renderBlocks(currentBlocks);
    
    // Save to backend using batch save API
    try {
        await fetch(`${API_BASE}/save-all-blocks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                episode_index: currentEpisodeIndex,
                blocks: currentBlocks,
                type: 'en'
            })
        });
        console.log('Block deleted and saved');
    } catch (e) {
        console.error('Failed to save after delete:', e);
        await customAlert('删除后保存失败: ' + e, '错误');
    }
}

async function saveSplit() {
    const segments = getSplitSegments();
    
    // Collect text from textareas
    segments.forEach((seg, index) => {
        const textarea = document.getElementById(`split-text-${index}`);
        seg.text = textarea ? textarea.value.trim() : '';
    });
    
    // Validate
    const emptySegments = segments.filter(s => !s.text);
    if (emptySegments.length > 0) {
        const confirmed = await customConfirm(`有 ${emptySegments.length} 个段落没有填写文本，确定要保存吗？`, '确认保存');
        if (!confirmed) {
            return;
        }
    }
    
    console.log('Saving split segments:', segments);
    
    // Create new blocks
    const originalBlock = currentBlocks[splitModalData.blockIndex];
    const newBlocks = [];
    
    segments.forEach((seg, index) => {
        // 确保计算正确的绝对时间
        const startSeconds = splitModalData.startTime + seg.start;
        const endSeconds = splitModalData.startTime + seg.end;
        
        // 验证时间有效性
        if (endSeconds <= startSeconds) {
            console.error('Invalid time range:', startSeconds, endSeconds);
            return;
        }
        
        const startTime = secondsToTime(startSeconds);
        const endTime = secondsToTime(endSeconds);
        
        newBlocks.push({
            index: originalBlock.index + index,
            start: startTime,
            end: endTime,
            zh_text: index === 0 ? originalBlock.zh_text : '', // Only first keeps Chinese
            en_text: seg.text
        });
    });
    
    // Replace in current blocks
    currentBlocks.splice(splitModalData.blockIndex, 1, ...newBlocks);
    
    // Reindex
    currentBlocks.forEach((block, i) => {
        block.index = i + 1;
    });
    
    // Save all blocks to backend using the new batch save API
    try {
        await fetch(`${API_BASE}/save-all-blocks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                episode_index: currentEpisodeIndex,
                blocks: currentBlocks,
                type: 'en'
            })
        });
        
        await customAlert('分割保存成功！');
        closeSplitModal();
        renderBlocks(currentBlocks);
    } catch (e) {
        await customAlert('保存失败: ' + e, '错误');
    }
}

// About modal functions
function showAbout() {
    const modal = document.getElementById('about-modal');
    modal.classList.add('active');
}

function closeAbout() {
    const modal = document.getElementById('about-modal');
    modal.classList.remove('active');
}
