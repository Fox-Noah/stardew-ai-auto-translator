# 星露谷物语 MOD 翻译工具

**中文** | [English（原版说明）](README_EN.md)

面向 Linux 桌面的《星露谷物语》MOD 翻译工具。支持本地 Ollama 和在线模型 API，翻译 `i18n` 文本或没有 `i18n` 的 MOD 中的 `content.json`，并在覆盖前保留备份。

本项目基于 [Fox-Noah 的原版工具](https://github.com/Fox-Noah/stardew-ai-auto-translator) 开发。首版以 Linux AppImage 为主要分发方式；文末的 Windows 说明仅供参考。

## 快速开始

### 启动 AppImage

从 [Releases](https://github.com/science1009/stardew-ai-auto-translator/releases) 下载 `.AppImage`（如已发布），在下载目录运行。请将示例文件名换成实际名称：

```bash
chmod +x ./stardew-ai-auto-translator-x86_64.AppImage
./stardew-ai-auto-translator-x86_64.AppImage
```

没有可用的发布包，或发行版运行不兼容时，参见[从源码运行与构建](#从源码运行与构建)。

### 配置模型并翻译

1. 点击“供应商 / 术语”，选择协议，填写接口地址和模型名称，再点击“保存全部设置”。
   - **本地 Ollama**：先安装并启动 [Ollama](https://ollama.com/)，例如用 `ollama pull qwen2.5:7b` 下载模型。协议选 `ollama`，默认地址为 `http://localhost:11434`，模型填 `qwen2.5:7b`，密钥留空。
   - **在线 API**：按服务商文档选 `openai`（Chat Completions）或 `anthropic`（Messages），填写地址、模型和 API 密钥，无需安装 Ollama。地址可填根地址、带 `/v1` 的地址或完整端点；请只使用可信服务。在线翻译会向服务商发送待译文本，可能产生费用。
2. 选目标语言，点击“选择 MOD 目录”，可选择单个 MOD 或包含多个 MOD 的目录。初次使用建议选副本。也可以依次导入并解压 MOD 压缩包，再点“提取 i18n”。
3. 选中 MOD 和起始文件，点击“自动翻译”。工具从当前文件开始处理该 MOD 的剩余文件；切换 MOD 后可处理下一组。直接选目录时不需要重新打包。

## 翻译范围与保存

- 有 `i18n` 时优先读取 `default.json`，其次 `en.json`，兼容文件名大小写。中文写入对应 MOD 的 `i18n/zh.json`，其他语言使用各自的语言代码。源文件中没有的文本不会补翻；没有 `i18n` 时才搜索并原位处理 `content.json` 的可翻译文本。
- 已有且通过校验的译文复用，用户额外添加的译文条目保留。支持 JSONC 注释、UTF-8 BOM、尾逗号和常见未加引号的英文键。重复键按最后一个值读取，翻译同名字符串时更新对应的重复位置。
- “供应商 / 术语”可保存多个供应商、自定义提示词和 JSON 术语字典，例如 `{"Abigail": "阿比盖尔"}`。术语区分大小写、按完整词匹配，重叠时取最长项。术语与游戏标记约束优先于提示词；不符合约束时停止当前文件，不自动重试。

### 保存与恢复

翻译过程仅更新预览；当前文件的全部结果通过完整性、占位符、控制符和术语校验后才保存。请求失败、取消、备份失败或文件被外部修改时，不覆盖当前文件。前面已成功保存的文件保留。

覆盖前保留同目录备份：`content.json.bak` 或 `zh.json.bak`；后续版本使用 `.bak.1`、`.bak.2`，不覆盖历史。写入采用同目录临时文件与原子替换。失败留下的 `.pending.*` 文件保留供检查，不作为正式译文。

选中文件后点“恢复备份”，选择同目录对应备份；恢复前仍会备份当前内容。手工编辑后点“保存翻译”，同样经过校验；未完成的预览不能直接覆盖正式文件。`content.json` 的注释、BOM 和非文本内容保留；已有 i18n 文件结构不变时也保留格式，新增键时重新排版。

停止翻译不会中断已发出的 HTTP 请求，但不会保存当前文件；API 服务仍可能计费。

## 从源码运行与构建

以下以 **Ubuntu 22.04、x86_64** 为例。仅从源码运行不需要 PyInstaller、`appimagetool` 或 Docker。AppImage 是 Linux 本机打包，不是 Windows 交叉构建。使用 Ubuntu 22.04 作为打包基线，不保证产物兼容更旧的系统或不同 CPU 架构。

### 1. 准备源码和 Python 环境

下载对应版本的源码并解压，或克隆包含 `packaging/appimage/build-appimage.sh` 的分支，例如 `feature/linux-adaptation`：

```bash
git clone --branch feature/linux-adaptation https://github.com/science1009/stardew-ai-auto-translator.git
cd stardew-ai-auto-translator
```

从仓库根目录执行：

```bash
sudo apt update
sudo apt install python3 python3-venv python3-tk
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 2. 运行源码和离线自检

在桌面会话的终端执行 `python main.py`。若要单独确认 Tk 能打开窗口，可运行 `python -m tkinter`，再关闭验证窗口。下面的离线自检不需要图形会话、Ollama 或 API 密钥，不接触真实 MOD，产物保留在 `.checks/`：

```bash
PYTHONDONTWRITEBYTECODE=1 python scripts/check_translation.py
```

### 3. 构建并启动 AppImage

保持 `.venv` 激活，在同一目录安装打包工具。示例下载的是 [官方 appimagetool](https://github.com/AppImage/appimagetool/releases) 的 x86_64 持续构建版：

```bash
sudo apt install binutils ca-certificates curl file
python -m pip install pyinstaller
mkdir -p .appimage/tools
curl -fL https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage \
  -o .appimage/tools/appimagetool
chmod +x .appimage/tools/appimagetool
export PATH="$PWD/.appimage/tools:$PATH"
APPIMAGE_EXTRACT_AND_RUN=1 bash packaging/appimage/build-appimage.sh ./stardew-ai-auto-translator-x86_64.AppImage
```

脚本先用 PyInstaller 打包 `main.py`，再用 `appimagetool` 生成 AppImage。中间产物默认在 `.appimage/`，可用 `STARDEW_APPIMAGE_BUILD_DIR` 指定其他目录。最后一个参数是输出路径；省略时在仓库根目录生成带时间戳的 `.AppImage`。

在 Linux 桌面终端运行刚生成的 `./stardew-ai-auto-translator-x86_64.AppImage`，确认窗口可打开，再用 MOD 副本试译。打包成功不等于桌面运行和翻译已验证。

## 配置路径与常见问题

- **配置在哪？** 源码运行默认使用仓库下的 `Data/config.json`；AppImage 默认使用 `~/.local/share/stardew-ai-auto-translator/Data/config.json`。AppImage 尊重 `XDG_DATA_HOME`；两种运行方式都可用 `STARDEW_TRANSLATOR_DATA_DIR` 指定工作目录，配置位于其下的 `Data/config.json`。改动路径不会迁移旧配置。
- **如何保管密钥？** 供应商、提示词和术语都保存在配置文件中。密钥是本地明文，POSIX 权限为 `0600`；不要分享或提交该文件。配置损坏时程序保留原件并拒绝覆盖，请先修复或备份后移走。
- **AppImage 报 FUSE 错误？** Ubuntu 22.04 可安装 `libfuse2`。也可在 AppImage 命令前加 `APPIMAGE_EXTRACT_AND_RUN=1`，解包后运行，无需 FUSE。
- **Tk 找不到显示？** 从已登录的 Linux 桌面终端启动。Tk 使用 X11；Wayland 会话需要 Xwayland 和有效的 `DISPLAY`，不支持纯 Wayland。解包运行不能解决显示问题。
- **打包找不到 `appimagetool`、PyInstaller 或 `requests`？** 确认在同一个终端激活 `.venv`，按上面的步骤安装依赖并设置 `PATH`。

<details>
<summary>原仓库 README（Windows 版历史说明）</summary>


## 需要的东西

- Ollama + qwen2.5模型

## 安装教程

### 1. 安装Ollama

#### Windows系统
1. 访问 [Ollama官网](https://ollama.ai/)
2. 点击"Download for Windows"下载安装包
3. 运行下载的`.exe`文件，按照提示完成安装
4. 安装完成后，Ollama会自动启动服务


### 2. 安装qwen2.5模型

安装完Ollama后，需要下载qwen2.5模型：

```bash
# 安装qwen2.5:7b模型（推荐，平衡性能和质量）
ollama pull qwen2.5:7b

# 如果电脑配置较低，可以选择更小的模型
ollama pull qwen2.5:3b

# 如果电脑配置很高，可以选择更大的模型效果更好
ollama pull qwen2.5:14b
```

### 3. 验证安装

在命令行中运行以下命令验证安装：

```bash
# 检查Ollama是否正常运行
ollama list

# 测试qwen2.5模型
ollama run qwen2.5:7b "你好"
```

如果看到模型列表和正常的回复，说明安装成功。

### 4. 启动Ollama服务

- **Windows**: Ollama通常会自动启动，如果没有，可以在开始菜单搜索"Ollama"启动(一个羊驼的图标)

默认情况下，Ollama服务会在 `http://localhost:11434` 运行。

## 怎么用

1. 打开stardew_ai_auto_translator.exe
2. 导入mod压缩包
3. 解压mod压缩包
4. 提取
5. 自动翻译
6. 打包完成

## 注意

- 翻译速度看你电脑性能配置
- 如果你电脑性能强大,可以在设置里设置翻译速度

## 常见问题

- 翻译一半? :因为作者某些文本没有提取到i18n, 所以仅翻译了i18n里的文本,后续工具会增加自动提取
- 连不上Ollama：检查服务是否启动,通常需要端口11434,如端口被占用,请手动杀死端口
- 翻译失败：可能文件格式有问题
- 速度慢：换个小点的模型

</details>
