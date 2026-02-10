```skill
---
name: security-scan
description: Techniques for running CodeQL and other security scans on changed files. Use this when checking code for vulnerabilities, reviewing security after edits, or integrating static analysis into Ralph iterations.
---

# Security Scan Skill

This skill provides techniques for running security scans during Ralph Mode iterations without blocking the workflow.

## Quick Scan (Changed Files Only)

### Check if CodeQL CLI is available
```bash
command -v codeql >/dev/null 2>&1 && echo "CodeQL available" || echo "CodeQL not installed (skip)"
```

### Scan changed files with CodeQL
```bash
# 1. Create database (first time only, cached after)
LANG="python"  # or javascript, go, java, cpp, csharp, ruby, swift, rust
DB_DIR=".ralph-mode/codeql-db"

if [ ! -d "$DB_DIR" ]; then
  codeql database create "$DB_DIR" --language="$LANG" --overwrite 2>/dev/null
fi

# 2. Run security queries on the database
codeql database analyze "$DB_DIR" \
  "codeql/${LANG}-queries:codeql-suites/${LANG}-security-and-quality.qls" \
  --format=sarif-latest \
  --output=".ralph-mode/scan-results.sarif" \
  2>/dev/null

# 3. Quick summary
echo "Scan complete. Results in .ralph-mode/scan-results.sarif"
```

### Lightweight scan (no CodeQL)
```bash
# Grep-based quick checks for common issues
grep -rn "eval(\|exec(\|os\.system\|subprocess\.call" --include="*.py" src/ || echo "No obvious issues"
grep -rn "innerHTML\|document\.write\|eval(" --include="*.js" --include="*.ts" src/ || echo "No obvious issues"
```

## Language Detection

```bash
# Auto-detect primary language
if [ -f "package.json" ]; then LANG="javascript"
elif [ -f "go.mod" ]; then LANG="go"
elif [ -f "pyproject.toml" ] || [ -f "setup.py" ]; then LANG="python"
elif [ -f "Cargo.toml" ]; then LANG="rust"
elif [ -f "*.csproj" ]; then LANG="csharp"
elif [ -f "pom.xml" ] || [ -f "build.gradle" ]; then LANG="java"
else LANG="unknown"
fi
echo "Detected language: $LANG"
```

## Interpreting SARIF Results

### Quick count
```bash
# Count alerts by severity
python3 -c "
import json, sys
try:
    with open('.ralph-mode/scan-results.sarif') as f:
        sarif = json.load(f)
    results = sarif.get('runs', [{}])[0].get('results', [])
    print(f'Total alerts: {len(results)}')
    by_level = {}
    for r in results:
        level = r.get('level', 'warning')
        by_level[level] = by_level.get(level, 0) + 1
    for level, count in sorted(by_level.items()):
        print(f'  {level}: {count}')
except FileNotFoundError:
    print('No SARIF results found')
except Exception as e:
    print(f'Error reading SARIF: {e}')
"
```

### Show top issues
```bash
python3 -c "
import json
try:
    with open('.ralph-mode/scan-results.sarif') as f:
        sarif = json.load(f)
    results = sarif.get('runs', [{}])[0].get('results', [])
    for r in results[:10]:
        rule = r.get('ruleId', 'unknown')
        msg = r.get('message', {}).get('text', '')[:100]
        locs = r.get('locations', [{}])
        loc = locs[0].get('physicalLocation', {}) if locs else {}
        file = loc.get('artifactLocation', {}).get('uri', '?')
        line = loc.get('region', {}).get('startLine', '?')
        level = r.get('level', 'warning')
        print(f'[{level}] {rule} @ {file}:{line}')
        print(f'  {msg}')
except FileNotFoundError:
    print('No SARIF results found')
"
```

## Integration with Ralph Memory

After a scan, save findings to memory:
```bash
python3 ralph_mode.py memory add "Security scan found 3 issues: 1 error, 2 warnings" \
  --category errors --memory-type episodic
```

## Non-Blocking Principles

1. **Never fail the iteration** if CodeQL is not installed
2. **Skip scan** if no source files changed
3. **Cache the database** across iterations
4. **Only scan changed files** when possible
5. **Time-limit** scans to avoid blocking the loop
```
