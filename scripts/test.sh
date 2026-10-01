#!/usr/bin/env bash
# Run every test in the repository:
#   - tests/*.sh                      repository-level content checks
#   - skills/*/test_*.py              Python unit tests bundled with a skill (stdlib unittest, run via uv)
#   - skills/brave-web/test/*.test.js Node tests (installs deps from the lockfile if missing)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for t in tests/*.sh; do
    echo "• $t"
    bash "$t"
done

# Python tests run in an isolated uv environment so they never depend on whatever
# happens to be installed globally. A skill's import-time dependencies go here.
python_test_deps() {
    case "$1" in
        skills/grok-research) echo "pydantic" ;;
    esac
}

for dir in skills/*/; do
    if compgen -G "$dir/test_*.py" >/dev/null; then
        echo "• ${dir%/} (python unittest)"
        with_args=()
        for dep in $(python_test_deps "${dir%/}"); do with_args+=(--with "$dep"); done
        (cd "$dir" && uv run --no-project --isolated ${with_args[@]+"${with_args[@]}"} python -m unittest discover -s . -p 'test_*.py')
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
