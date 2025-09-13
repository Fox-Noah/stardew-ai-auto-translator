# 星露谷物语MOD翻译工具

**中文** | [English](README_EN.md)

自动翻译星露谷物语MOD的i18n文件

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