#!/usr/bin/env bash
# Run every test in the repository:
#   - tests/*.sh                      repository-level content checks
#   - skills/*/test_*.py              Python unit tests bundled with a skill (stdlib unittest)
#   - skills/brave-web/test/*.test.js Node tests (installs deps from the lockfile if missing)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for t in tests/*.sh; do
    echo "• $t"
    bash "$t"
done

for dir in skills/*/; do
    if compgen -G "$dir/test_*.py" >/dev/null; then
        echo "• ${dir%/} (python unittest)"
        (cd "$dir" && python3 -m unittest discover -s . -p 'test_*.py')
    fi
done

if [ -d skills/brave-web/test ]; then
    echo "• skills/brave-web (node --test)"
    (
        cd skills/brave-web
        [ -d node_modules ] || npm ci --no-audit --no-fund --silent
        node --test test/*.test.js
    )
fi

echo "all tests passed"
