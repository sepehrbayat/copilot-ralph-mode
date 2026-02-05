---
name: code-analysis
description: Techniques for quickly understanding unfamiliar codebases. Use this when exploring a new codebase, finding definitions, or understanding project architecture.
---

# Code Analysis Skill

This skill provides techniques for quickly understanding unfamiliar code.

## Quick Analysis

### Project Structure
```bash
# List top-level structure
ls -la

# Find all source files
find src -name "*.ts" -o -name "*.py" -o -name "*.js" | head -20

# Count lines of code
find src -name "*.ts" | xargs wc -l | tail -1
```

### Entry Points
```bash
# Find main entry points
grep -rn "main\|entry\|index" --include="*.json" .
cat package.json | grep -A5 '"main"'
cat package.json | grep -A5 '"scripts"'
```

### Dependencies
```bash
# List dependencies
cat package.json | grep -A50 '"dependencies"'
cat requirements.txt
cat go.mod
```

## Code Navigation

### Find Definitions
```bash
# Find function definition
grep -rn "function functionName\|def functionName\|func functionName"

# Find class definition
grep -rn "class ClassName"

# Find interface/type
grep -rn "interface TypeName\|type TypeName"
```

### Find Usages
```bash
# Find all usages
grep -rn "functionName" src/

# Find imports
grep -rn "import.*functionName\|from.*import.*functionName"
```

### Trace Execution
```bash
# Find entry point
grep -rn "main\|start\|run" src/

# Find API routes
grep -rn "app.get\|app.post\|@app.route" src/

# Find event handlers
grep -rn "addEventListener\|on\(" src/
```

## Architecture Patterns

### Identify Patterns
- **MVC**: Look for models/, views/, controllers/
- **Clean Architecture**: Look for domain/, use-cases/, adapters/
- **Feature-based**: Look for features/ or modules/

### Common Folder Structures
- `src/` or `lib/` - Main source code
- `tests/` or `__tests__/` - Test files
- `config/` - Configuration files
- `docs/` - Documentation
- `scripts/` - Build/utility scripts
