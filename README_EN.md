# Stardew Valley MOD Translation Tool

[中文版](README.md) | **English**

Automatically translate i18n files for Stardew Valley MODs

## Requirements

- Ollama + qwen2.5 model

## Installation Guide

### 1. Install Ollama

#### Windows
1. Visit [Ollama Official Website](https://ollama.ai/)
2. Click "Download for Windows" to download the installer
3. Run the downloaded `.exe` file and follow the installation prompts
4. After installation, Ollama will automatically start the service

### 2. Install qwen2.5 Model

After installing Ollama, you need to download the qwen2.5 model:

```bash
# Install qwen2.5:7b model (recommended, balanced performance and quality)
ollama pull qwen2.5:7b

# If your computer has lower specs, choose a smaller model
ollama pull qwen2.5:3b

# If your computer has high specs, choose a larger model for better results
ollama pull qwen2.5:14b
```

### 3. Verify Installation

Run the following commands in the command line to verify installation:

```bash
# Check if Ollama is running properly
ollama list

# Test qwen2.5 model
ollama run qwen2.5:7b "Hello"
```

If you see the model list and normal responses, the installation is successful.

### 4. Start Ollama Service

- **Windows**: Ollama usually starts automatically. If not, search for "Ollama" in the start menu (a llama icon)

By default, Ollama service runs on `http://localhost:11434`.

## How to Use

1. Open stardew_ai_auto_translator.exe
2. Import MOD zip file
3. Extract MOD zip file
4. Extract text
5. Auto translate
6. Package complete

## Notes

- Translation speed depends on your computer's performance
- If your computer has powerful specs, you can adjust translation speed in settings

## FAQ

- Translation incomplete? : Because the author didn't extract some text to i18n, so only i18n text was translated. Future tools will add automatic extraction
- Can't connect to Ollama: Check if the service is running, usually requires port 11434. If port is occupied, please manually kill the port
- Translation failed: File format might be problematic
- Slow speed: Switch to a smaller model