# Neo Enhanced CLI - Feature Summary

The traditional CLI mode has been significantly enhanced with the same powerful features as the TUI.

---

## New CLI Commands

### Multi-Agent Commands

| Command | Description | Example |
|---------|-------------|---------|
| `neo explore "query"` | Fast codebase exploration | `neo explore "find auth functions"` |
| `neo plan "task"` | Create implementation plan | `neo plan "refactor user module"` |
| `neo review file.py` | Code quality review | `neo review src/main.py` |
| `neo search "query"` | Semantic code search | `neo search "error handling"` |
| `neo index` | Index codebase for search | `neo index --force` |

### Interactive Mode Commands

| Command | Description |
|---------|-------------|
| `/agent explore "query"` | Use ExploreAgent |
| `/agent plan "task"` | Use PlanAgent |
| `/agent review file.py` | Use CodeReviewAgent |
| `/search "query"` | Semantic code search |
| `/index` | Index codebase |
| `/undo` | Undo last file change |
| `/redo` | Redo last undone change |
| `/history` | Show operation history |
| `/status` | Show detailed status |
| `/reset` | Clear memory |
| `/help` | Show help |
| `/exit` | Quit |

### Enhanced `ask` Command

```bash
# Use specific agent
neo ask "refactor auth" --agent-type plan

# Show context
neo ask "how does error handling work?" --context

# Use specific model
neo ask "question" --model gpt-4o
```

---

## Enhanced Features

### 1. Semantic Code Search

```bash
# Index your codebase
neo index

# Search by meaning, not keywords
neo search "how to handle API errors"
neo search "authentication middleware"

# Force re-index
neo index --force

# Search with context in interactive mode
> /search "database connection"
```

Output:
```
10 results:

1. src/database.py:45-62 (function)
┌─────────────────────────────────────┐
│ def connect_to_db():                │
│     """Create database connection"""│
│     ...                             │
└─────────────────────────────────────┘

2. src/auth.py:12-28 (function)
...
```

### 2. Direct Agent Access

```bash
# Explore agent - fast search
neo explore "find all API endpoints"
neo explore "where is User class defined?"

# Plan agent - create implementation plans
neo plan "add JWT authentication"
neo plan "refactor database layer" --files src/db.py,src/models.py

# Review agent - code quality analysis
neo review src/main.py
neo review tests/test_auth.py
```

### 3. Transaction Management

```bash
# In interactive mode:
> # Make some changes...
> /undo              # Undo last change
> /redo              # Redo last undone change
> /history           # Show operation history
```

### 4. Rich Output Formatting

- **Code blocks** with syntax highlighting
- **Diffs** with color coding
- **Progress spinners** for long operations
- **Status panels** with detailed info

### 5. Context Awareness

```bash
# Automatically shows relevant files
> How does authentication work?
[dim]Context: src/auth.py, src/middleware.py[/dim]

# Manual context display
neo ask "question" --context
```

---

## Example Sessions

### Session 1: Code Exploration

```bash
$ neo

Neo v0.2.0 - Advanced Coding Assistant
...

> /agent explore "find all authentication functions"

Running explore agent...

Found 5 results:

• src/auth/login.py:12 - authenticate_user()
• src/auth/middleware.py:45 - require_auth()
• src/api/users.py:78 - login_endpoint()
• tests/test_auth.py:34 - test_authentication()

> /search "how to handle token expiration"

10 results:
...
```

### Session 2: Implementation Planning

```bash
$ neo plan "add email verification"

Creating plan...

## Implementation Plan

### Approach
Add email verification using JWT tokens sent via email.

### Steps:
1. Create EmailService class
2. Add verification token generation
3. Create verification endpoint
4. Update User model
5. Add email templates

### Files Affected:
- src/services/email.py (create)
- src/models/user.py (modify)
- src/api/auth.py (modify)

Would you like me to implement this plan? (y/n)
```

### Session 3: Code Review

```bash
$ neo review src/main.py

Reviewing code...

## Code Review

### Summary
Well-structured module with good separation of concerns.

### Issues Found:

🔴 Critical: No input validation on line 45
- Problem: User input passed directly to SQL query
- Suggestion: Use parameterized queries
```python
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

🟡 Warning: Missing error handling
...
```

### Session 4: Semantic Search

```bash
$ neo index
Indexing codebase...
Indexed 45 files with 234 chunks

$ neo search "database transaction handling"

5 results:

1. src/db/utils.py:23-45 (function)
   def with_transaction(func):
       """Decorator for database transactions"""
       ...

2. src/services/order.py:67-89 (function)
   def create_order():
       # Uses transactions
       ...
```

---

## Comparison: Old vs Enhanced CLI

| Feature | Old CLI | Enhanced CLI |
|---------|---------|--------------|
| Agents | Single | Multi-agent (4 types) |
| Agent Access | Automatic | Direct commands |
| Code Search | None | Semantic search |
| Indexing | None | `neo index` |
| Undo/Redo | None | `/undo`, `/redo` |
| Context | None | Automatic + `--context` |
| Streaming | No | Yes |
| Rich Output | Basic | Syntax highlighting, panels |
| History | None | `/history` |
| Review | None | `neo review` |
| Planning | None | `neo plan` |

---

## Keyboard Shortcuts (Interactive Mode)

| Shortcut | Action |
|----------|--------|
| `Ctrl+C` | Cancel current operation |
| `Up/Down` | Navigate command history |
| `/` | Start command |

---

## Tips

1. **Use specific agents** for better results:
   - `/agent explore` for finding code
   - `/agent plan` for complex changes
   - `/agent review` before committing

2. **Index your codebase** for semantic search:
   ```bash
   neo index
   ```

3. **Use context** for better responses:
   ```bash
   neo ask "question" --context
   ```

4. **Undo changes** if something goes wrong:
   ```
   > /undo
   ```

5. **Chain commands** in scripts:
   ```bash
   neo index
   neo plan "refactor auth" > plan.md
   neo review src/auth.py
   ```

---

## Quick Reference

```bash
# Multi-agent commands
neo explore "query"                    # Fast exploration
neo plan "task"                        # Create plan
neo review file.py                     # Code review
neo search "query"                     # Semantic search
neo index                              # Index codebase

# Interactive mode commands
/ag explore "find auth"               # Use explore agent
/ag plan "refactor"                    # Use plan agent
/ag review file.py                     # Use review agent
/search "error handling"               # Semantic search
/index                                 # Index
/undo                                  # Undo
/redo                                  # Redo
/history                               # Show history
/status                                # Status
/reset                                 # Clear memory
/help                                  # Help
/exit                                  # Quit

# Ask with options
neo ask "question" --agent-type plan   # Use plan agent
neo ask "question" --context           # Show context
neo ask "question" --model gpt-4o     # Use specific model
```

The traditional CLI now has all the power of the multi-agent system with the convenience of terminal commands!
