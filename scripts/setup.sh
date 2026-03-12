#!/bin/bash
# Zion Setup Script
# Installs all dependencies for Zion on Linux + NVIDIA

set -e

echo ""
echo "╔══════════════════════════════════════╗"
echo "║         ZION SETUP                   ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── Check NVIDIA ────────────────────────────────────────
echo "▶ Checking GPU..."
if command -v nvidia-smi &> /dev/null; then
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
  echo "✓ NVIDIA GPU found"
else
  echo "⚠ nvidia-smi not found. GPU acceleration may not work."
fi

# ── Install Ollama ──────────────────────────────────────
echo ""
echo "▶ Installing Ollama..."
if command -v ollama &> /dev/null; then
  echo "✓ Ollama already installed: $(ollama --version)"
else
  curl -fsSL https://ollama.ai/install.sh | sh
  echo "✓ Ollama installed"
fi

# ── Start Ollama service ────────────────────────────────
echo ""
echo "▶ Starting Ollama service..."
ollama serve &>/dev/null &
sleep 3
echo "✓ Ollama running"

# ── Pull model ──────────────────────────────────────────
echo ""
echo "▶ Pulling Gemma 3 12B model (this will take a while ~8GB)..."
echo "  You can interrupt with Ctrl+C and run 'ollama pull gemma3:12b' later."
ollama pull gemma3:12b
echo "✓ Model ready"

# ── Python dependencies ─────────────────────────────────
echo ""
echo "▶ Installing Python dependencies..."
if command -v pip3 &> /dev/null; then
  pip3 install -r requirements.txt --user --quiet
  echo "✓ Python packages installed"
else
  echo "✗ pip3 not found. Please install python3-pip first:"
  echo "  sudo apt install python3-pip"
  exit 1
fi

# ── Create data directories ─────────────────────────────
echo ""
echo "▶ Creating data directories..."
mkdir -p data/briefings
touch data/watcher_log.json
echo "{}" > data/watcher_log.json
touch data/error_log.json
echo "{}" > data/error_log.json
touch data/feedback_log.json
echo "{}" > data/feedback_log.json
echo "✓ Data directories ready"

# ── Clone The Collective repo ───────────────────────────
echo ""
echo "▶ Checking for The Collective repo..."
COLLECTIVE_PATH="$HOME/RootlessOnline"
if [ -d "$COLLECTIVE_PATH" ]; then
  echo "✓ Collective repo found at $COLLECTIVE_PATH"
else
  echo "  Cloning The Collective repo..."
  git clone https://github.com/RootlessOnline/RootlessOnline.git "$COLLECTIVE_PATH"
  echo "✓ Collective repo cloned to $COLLECTIVE_PATH"
fi

# ── Update config ───────────────────────────────────────
echo ""
echo "▶ Updating config with repo path..."
sed -i "s|~/RootlessOnline|$COLLECTIVE_PATH|g" config.json
echo "✓ Config updated"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║  Setup complete!                     ║"
echo "║                                      ║"
echo "║  Run:  ./scripts/start.sh            ║"
echo "║  Then: http://localhost:5000         ║"
echo "╚══════════════════════════════════════╝"
echo ""
