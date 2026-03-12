#!/bin/bash
# Push Zion to GitHub
# Run this from your terminal after cloning Zion repo

echo ""
echo "╔══════════════════════════════════════╗"
echo "║  Pushing Zion to GitHub              ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Check we're in the right place
if [ ! -f "app.py" ]; then
  echo "✗ Run this script from inside the Zion folder"
  exit 1
fi

# Init git if needed
if [ ! -d ".git" ]; then
  git init
  git remote add origin https://github.com/RootlessOnline/Zion.git
  echo "✓ Git initialised"
fi

chmod +x scripts/setup.sh scripts/start.sh scripts/stop.sh

git add .
git commit -m "Initial Zion commit — cockpit for The Collective"
git branch -M main
git push -u origin main

echo ""
echo "✓ Zion pushed to https://github.com/RootlessOnline/Zion"
echo ""
echo "Next steps:"
echo "  1. git clone https://github.com/RootlessOnline/Zion.git"
echo "  2. cd Zion && chmod +x scripts/setup.sh && ./scripts/setup.sh"
echo "  3. ./scripts/start.sh"
echo "  4. Open http://localhost:5000"
echo ""
