# Future Enhancements for Neo

This document tracks potential improvements and features to enhance Neo beyond its current capabilities.

## 1. Persistent Memory (Like Claude Code's Auto-Memory)

- **Project knowledge**: Remember file relationships, architecture decisions, coding patterns
- **Cross-session continuity**: Previous conversations, decisions made, context from last run
- **Incremental indexing**: Build a searchable index of the codebase over time
- **Memory directory**: Store at `~/.neo/projects/{project}/` with semantic organization

## 2. Enhanced Code Understanding

- **Semantic search**: Vector embeddings for code (using ChromaDB mentioned in requirements)
- **Symbol graph**: Track function/class relationships, call graphs, dependencies
- **Code summarization**: Auto-summarize files to include in context without sending full content
- **Tree-sitter integration**: Parse code for accurate symbol extraction (already in requirements)
- **Import analysis**: Understand module dependencies and suggest related files

## 3. Multi-File Edit Operations

- **Batch edits**: Apply changes across multiple files in one operation
- **Refactoring support**: Rename symbols across files, extract functions
- **Edit preview**: Show what will change before applying
- **Undo stack**: Rollback changes if something breaks
- **Atomic transactions**: All edits succeed or none do

## 4. Workflow Automation (Skills)

- **Reusable workflows**:
  - `/commit` - stage, generate message, commit
  - `/test` - run tests, analyze failures, suggest fixes
  - `/pr` - generate PR descriptions from commits
- **Custom macros**: User-defined command sequences
- **Project templates**: Common patterns for different project types

## 5. Better Context Management

- **@mentions**:
  - `@file.py` - include specific files
  - `@symbol` - reference functions/classes
  - `@folder/` - include directories
  - `@commit` - reference git history
- **Smart truncation**: Prioritize relevant code sections when context is full
- **Context budget**: User-configurable token limits per request
- **Auto-context**: Automatically include relevant files based on imports

## 6. IDE Integration

- **LSP client**: Use language servers for accurate code intelligence
- **GitHub Copilot-style completions**: Inline suggestions as you type
- **VS Code extension**: Bridge between TUI and IDE
- **Neovim plugin**: Native editor integration
- **Language-specific optimizations**: Python, JavaScript, Go, Rust modes

## 7. Enhanced TUI Features

- **Split views**: Side-by-side file comparison
- **Search panel**: Live grep results with navigation
- **Git visualization**: Branch graph, blame view
- **Image support**: View diagrams, screenshots
- **Keybinding customization**: User-defined shortcuts
- **Theme support**: Custom color schemes

## 8. Safety & Permissions

- **Destructive action confirmation**: `--yes` flag or prompts for edits
- **Dry-run mode**: Preview changes without applying
- **Backup before edit**: Save original files
- **Sandbox mode**: Test changes in isolated environment
- **Permission levels**: auto-confirm, ask, read-only modes

## 9. Performance Optimizations

- **Response streaming**: Show tokens as they arrive (already implemented)
- **Tool result caching**: Cache file reads, git status
- **Parallel tool execution**: Run independent tools concurrently
- **Incremental file watching**: Auto-refresh tree on file changes
- **Lazy loading**: Load file contents on demand
- **Connection pooling**: Reuse HTTP connections to API

## 10. Developer Experience

- **Better error messages**: Suggest fixes when tools fail
- **Progress indicators**: Show what's happening during long operations
- **Debug mode**: Verbose logging, API request inspection
- **Configuration profiles**: Different settings per project type
- **Onboarding wizard**: First-time setup helper
- **Telemetry**: Optional usage statistics for improvement

## Priority Ranking (High Impact / Low Effort)

1. **Persistent project memory** - Big UX improvement
2. **@file/symbol mentions** - Natural way to provide context
3. **Batch multi-file edits** - Common workflow need
4. **Edit preview/confirmation** - Safety for destructive ops
5. **Vector semantic search** - Better than grep for finding code
6. **Tool result caching** - Performance win

## Comparison: Neo vs Claude Code Features

| Feature | Claude Code | Neo | Gap |
|---------|-------------|-----|-----|
| Auto-memory | ✅ | ❌ | High priority |
| Skills/Workflows | ✅ | ❌ | Medium priority |
| MCP Protocol | ✅ | ❌ | Low priority |
| Web search | ✅ | ❌ | Medium priority |
| Task tracking | ✅ | ❌ | Low priority |
| Multi-agent | ❌ | ✅ | Neo advantage |
| Cost tracking | ✅ | ✅ | Implemented |
| Mock mode | ❌ | ✅ | Neo advantage |
| Custom TUI | ✅ | ❌ | Different approach |

## Implementation Notes

- **Memory storage**: Use `platformdirs` for cross-platform storage locations
- **Vector search**: ChromaDB or similar for local embeddings
- **Tree-sitter**: Already in requirements, leverage for parsing
- **Configuration**: Extend existing `Config` class with new options
- **Backwards compatibility**: Maintain CLI/TUI compatibility as features are added

---

*Last updated: 2026-03-06*
