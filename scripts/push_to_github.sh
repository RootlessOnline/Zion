#!/bin/bash
# Push Zion to GitHub
# Usage: ./scripts/push_to_github.sh "commit message"
# Requires GITHUB_TOKEN in .env

set -e

cd "$(dirname "$0")/.."

if [ ! -f ".env" ]; then
  echo "✗ .env not found. Create it with GITHUB_TOKEN=your_token"
  exit 1
fi

source .env

if [ -z "$GITHUB_TOKEN" ]; then
  echo "✗ GITHUB_TOKEN not set in .env"
  exit 1
fi

REPO="RootlessOnline/Zion"
MSG="${1:-Zion sync $(date +%Y-%m-%d)}"

git remote set-url origin https://$GITHUB_TOKEN@github.com/$REPO.git
git add -A
git commit -m "$MSG" || echo "Nothing to commit"
git push origin main

echo ""
echo "✓ Pushed to https://github.com/$REPO"
echo ""
