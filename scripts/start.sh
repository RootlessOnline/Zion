#!/bin/bash
cd "$(dirname "$0")/.."
source venv/bin/activate
echo ""
echo "🟢 Starting Zion at http://localhost:5000"
echo ""
python3 app.py
