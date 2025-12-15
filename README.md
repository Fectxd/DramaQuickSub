<div align=center>
<img width="180" height="180" alt="image" src="https://github.com/user-attachments/assets/5de6b3c5-e047-4078-8097-99508715beb7" />
</div>

# DramaQuickSub 字幕编辑器

一个快速高效的影视剧双语字幕编辑工具，支持中英文字幕对齐、智能纠错和批量处理。
<img width="2126" height="1304" alt="image" src="https://github.com/user-attachments/assets/a053e3f0-0ffc-4169-ba83-3b50bd8f807c" />


## 💡 项目背景

随着短剧产品的海外出口，字幕翻译已成为译员们的日常工作。然而，大多数公司仅提供全集字幕压缩包和视频文件，缺乏专用的编辑工具。传统使用 Aegisub 的工作流需要逐个导入字幕和视频，操作繁琐且界面陈旧，却占据了翻译工作的大部分时间。

**DramaQuickSub 正是为解决这一痛点而生**，让译员能够专注于翻译本身，而非被工具流程所困扰。

## 📥 快速下载

**无需配置开发环境，直接使用！**

前往 [Releases](https://github.com/Fectxd/DramaQuickSub/releases) 页面下载编译好的程序，开箱即用。

- 需要配置 `config.ini` 及 `rules.txt` 文件以启用 AI 功能，详见下方配置

## 功能特点

- 🎯 **智能匹配**: 自动匹配中外文字幕文件与视频
- 🤖 **AI纠错**: 集成AI进行字幕智能纠错
- 📝 **可视化编辑**: 直观的字幕块编辑界面
- 📦 **批量处理**: 支持多集字幕同时处理
- 💾 **多格式支持**: 支持SRT和ASS字幕格式
- 🎬 **视频同步预览**: 边看边改，实时预览效果

### ⚡ 一键智能匹配 - 核心功能

上传中文和外语字幕压缩包后，只需指定视频文件夹路径，系统将：

1. **自动识别剧名**：AI 分析字幕文件名，智能提取剧集名称
2. **自动查找视频**：在指定目录中递归搜索匹配的视频文件
3. **自动关联集数**：准确匹配每集字幕与对应视频文件

**让原本需要逐个导入的繁琐操作变为一键完成！**

> **⚠️ 隐私提示**：智能匹配功能会将字幕压缩包和视频文件夹的**文件名和目录结构**（不包含文件内容）上传至 Gemini 2.0 Flash API 进行分析。作者认为这是安全操作，但如果您有安全顾虑，请谨慎使用该功能。

## 快速开始

### 方式一：下载可执行程序（推荐）

1. 从 [Releases](https://github.com/Fectxd/DramaQuickSub/releases) 下载最新版本
2. 解压到任意目录
3. 在程序目录下创建 `config.ini` 文件（参考 `config.ini.example`）
4. 双击运行 `字幕编辑器.exe`

### 方式二：开发环境运行

1. 克隆本仓库
2. 安装依赖：`pip install -r requirements.txt`
3. 运行：`python app_desktop.py`

### 配置

1. 复制 `config.ini.example` 为 `config.ini`，填入你的API密钥：
```ini
[API]
chatgpt_endpoint = https://chatapi.onechats.ai/v1/chat/completions
api_key = YOUR_API_KEY_HERE
```

2. 复制 `rules.txt.example` 为 `rules.txt`，根据需要修改纠错规则（支持多语言）：
   - 示例为西班牙语字幕纠错规则
   - 可根据实际语言自定义规则
   - 用于AI纠错时的prompt指导

### 开发运行

```bash
pip install -r requirements.txt
python app_desktop.py
```

### 打包exe

```bash
build.bat
```

生成的exe在 `dist/字幕编辑器/` 目录，需在exe旁创建：
- `config.ini` - API配置文件
- `rules.txt` - 字幕纠错规则（可选）

## 项目结构
  # 前端界面
├── backend/             # 后端逻辑
├── config.ini.example   # API配置模板
├── rules.txt.example    # 纠错规则示例（西班牙语）
└── app_desktop.py  mple # 配置模板
├── rules.txt          # 纠错规则
└── app_desktop.py     # 主程序入口
```

## 许可证

MIT License
