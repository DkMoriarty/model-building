#!/usr/bin/env bash
# Spark Studio setup for macOS / Linux.   bash setup.sh
# Checks the tools, installs the project's packages, builds every episode's
# soundtrack, and checks the machine with `npm run doctor`.
set -euo pipefail
cd "$(dirname "$0")/alan_pipeline"

need() {
  if command -v "$1" >/dev/null 2>&1; then echo "  ok  $2"; else
    echo "  !!  $2 missing. Install it: $3"; exit 1; fi
}
echo; echo "Spark Studio setup"; echo
need node "Node.js (>= 18.18)" "https://nodejs.org (or: brew install node)"
need python3 "Python 3" "https://python.org (or: brew install python)"
need ffmpeg "ffmpeg" "brew install ffmpeg  /  sudo apt install ffmpeg"

echo; echo "Installing packages..."
npm ci
python3 -m pip install --user numpy

echo; echo "Building soundtracks..."
python3 tools/build_space_audio.py --episode first_game
python3 tools/build_space_audio.py --episode first_light
python3 tools/build_space_audio.py

echo; echo "Checking the machine..."
npm run doctor || echo "  (if no browser was found: npx playwright install chromium)"

cat <<'EOF'

Done. Try:
  cd alan_pipeline
  npm start                 # live editor in the browser
  npm run render:game       # render FIRST GAME to output_renders/first_game.mp4
EOF
