# Neo - Local Coding Agent

Neo is a **coding-only local AI agent** designed specifically for software development tasks. Unlike general-purpose assistants, Neo focuses exclusively on code reading, writing, and editing.

## Features

- **Code-focused**: 15 tools specifically designed for coding workflows
- **Fast**: Instant startup with OpenAI API (no model downloads)
- **Lightweight**: Minimal dependencies, fast installation
- **Git integration**: Built-in git operations
- **Shell execution**: Run commands safely
- **Project aware**: Understands your codebase structure

## Installation

```bash
# Clone or download the repository
cd neo

# Install in editable mode
pip install -e .

# Or install from PyPI (when published)
pip install neo-coding-agent
```

## Configuration

**By default, Neo uses OpenAI API.** You only need to configure Ollama if you want to use Ollama instead of OpenAI.

### Quick Start (OpenAI - Default)

```bash
export OPENAI_API_KEY="sk-your-key-here"
neo
```

### Option 1: Environment Variables

**OpenAI (Default):**
```bash
export OPENAI_API_KEY="sk-..."
export NEO_MODEL="gpt-4o-mini"     # Default model
export NEO_AUTO_CONFIRM="false"    # Skip confirmation prompts
```

**Ollama Cloud (optional):**
```bash
export OPENAI_BASE_URL="https://api.ollama.com/v1"
export OPENAI_API_KEY="your-ollama-key"  # from https://ollama.com/settings
export NEO_MODEL="kimi-k2.5"
```

**Local Ollama (optional):**
```bash
export OPENAI_BASE_URL="http://localhost:11434/v1"
export OPENAI_API_KEY="ollama"  # any string works for local Ollama
export NEO_MODEL="kimi-k2.5"
```

### Option 2: .env File

Create a `.env` file in your project root:

```bash
cp .env.example .env
```

**For OpenAI (default, no changes needed):**
```bash
OPENAI_API_KEY=sk-your-key-here
NEO_MODEL=gpt-4o-mini
```

**For Ollama instead of OpenAI:**
```bash
# Add these lines to use Ollama
OPENAI_BASE_URL=https://api.ollama.com/v1  # or http://localhost:11434/v1 for local
OPENAI_API_KEY=your-ollama-api-key         # Get from https://ollama.com/settings (for cloud) or use "ollama" (for local)
NEO_MODEL=kimi-k2.5
```

Neo automatically loads `.env` files from:
- Current directory
- Project root (where `.git` or `.neo` is found)
- Parent directories (up to 5 levels)

### Using Ollama Instead of OpenAI

By default, Neo connects to OpenAI. To use Ollama instead:

**Ollama Cloud:**
```bash
export OPENAI_BASE_URL=https://api.ollama.com/v1
export OPENAI_API_KEY=your-ollama-api-key  # from https://ollama.com/settings
export NEO_MODEL=kimi-k2.5
neo
```

**Local Ollama:**
```bash
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_API_KEY=ollama  # any string works for local Ollama
export NEO_MODEL=kimi-k2.5
neo
```

**Note on API Keys:**
- **Ollama Cloud (api.ollama.com)**: Requires a real API key from https://ollama.com/settings
- **Local/Custom Ollama**: API key can be any string (e.g., "ollama")

## Usage

### Interactive Mode

```bash
neo
```

### Single Query

```bash
neo ask "refactor main.py to use asyncio"
```

### Direct Tool Execution

```bash
neo --tool read_file file_path=main.py
neo --tool git_status
neo --tool search_code pattern="def main"
```

### Initialize Project

```bash
neo init
```

## Available Tools

### File Operations
- `read_file` - Read file with offset/limit
- `write_file` - Write file atomically
- `edit_file` - Edit by string replacement
- `list_dir` - List directory contents
- `glob` - Pattern matching

### Code Analysis
- `analyze_file` - Analyze Python file structure
- `find_symbol` - Find class/function definitions

### Search
- `search_code` - Regex search in files
- `view` - View file with line numbers

### Git
- `git_status` - Repository status
- `git_diff` - Show changes
- `git_add` - Stage files
- `git_commit` - Commit changes
- `git_log` - View history

### Shell
- `run_shell` - Execute commands safely

### System
- `get_system_info` - System information

## Interactive Commands

When in interactive mode, use slash commands:

| Command | Description |
|---------|-------------|
| `/status` | Show model, token usage, session info |
| `/reset` | Clear conversation history |
| `/help` | Show available commands |
| `/exit` | Quit |

## Project Structure

```
neo/
├── pyproject.toml           # Package configuration
├── README.md                # This file
├── DESIGN.md               # Design specification
├── neo/                    # Main package
│   ├── cli.py              # CLI interface
│   ├── config.py           # Configuration
│   ├── agent.py            # Agent loop
│   ├── llm/                # LLM client
│   ├── memory/             # Memory system
│   ├── tools/              # Tool implementations
│   └── utils/              # Utilities
└── tests/                  # Test suite
```

## Architecture

```
CLI -> Agent -> LLM Client -> OpenAI API
      |
      v
Tool Registry -> 15 code-focused tools
      |
      v
Memory (Session + Project)
```

## Comparison with EDITH

| Feature | EDITH | Neo |
|---------|-------|-----|
| Setup Time | 5+ min (download models) | 30 sec (pip install) |
| Memory | 4-tier, complex | 2-tier, simple |
| Startup | Slow (model loading) | Instant |
| Cost | Free (local) | Pay per use (OpenAI) |
| Tools | 30+ (kitchen sink) | 15 (code-focused) |
| Best For | General tasks | Pure coding |

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest
```

### Code Style

```bash
black neo/
ruff check neo/
mypy neo/
```

## Roadmap

### Phase 1: Foundation (Complete)
- [x] Project structure
- [x] OpenAI client
- [x] Tool system
- [x] File operations
- [x] Simple agent loop
- [x] CLI skeleton

### Phase 2: Code Intelligence
- [ ] Tree-sitter integration
- [ ] Multi-language parsing
- [ ] Symbol indexing
- [ ] Project context generation

### Phase 3: Git & Shell
- [x] Git tools
- [x] Shell execution
- [ ] Diff preview confirmation
- [ ] Undo system

### Phase 4: Polish
- [ ] Streaming responses
- [ ] Better error handling
- [ ] Tests
- [ ] PyPI publishing

## License

MIT

## Contributing

Contributions welcome! Please read DESIGN.md for architectural details.
