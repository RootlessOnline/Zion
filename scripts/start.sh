#!/bin/bash
# Start Zion

echo ""
echo "🟢 Starting Zion at http://localhost:5000"
echo ""

# Start Ollama if not running
if ! pgrep -x "ollama" > /dev/null; then
  echo "▶ Starting Ollama..."
  ollama serve &>/dev/null &
  sleep 2
  echo "✓ Ollama started"
fi

# Check model is available
if ! ollama list | grep -q "deepseek-r1:8b"; then
  echo "⚠ deepseek-r1:8b not found. Run: ollama pull deepseek-r1:8b"
fi

# Start Flask app
cd "$(dirname "$0")/.."
source venv/bin/activate 2>/dev/null || true
python3 app.py
