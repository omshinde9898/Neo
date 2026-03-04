# Neo - Developer Log

## 2026-03-04 - Ollama Support (Optional Alternative to OpenAI)

### Default: OpenAI API
Neo **defaults to OpenAI API**. No special configuration needed - just set `OPENAI_API_KEY`.

```bash
export OPENAI_API_KEY=sk-...
neo
```

### Optional: OpenAI-Compatible APIs
Neo now **optionally** supports OpenAI-compatible APIs as an alternative to OpenAI:
- **Ollama Cloud** (api.ollama.com) - requires real API key
- **Local Ollama** (localhost:11434) - any API key string works
- **Remote Ollama** (custom server) - any API key string works
- **vLLM** (self-hosted OpenAI-compatible server)
- Any other OpenAI-compatible API

To use Ollama instead of OpenAI, set `OPENAI_BASE_URL`:

```bash
# Ollama Cloud
export OPENAI_BASE_URL=https://api.ollama.com/v1
export OPENAI_API_KEY=your-ollama-api-key
export NEO_MODEL=kimi-k2.5
neo

# Local Ollama
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_API_KEY=ollama
export NEO_MODEL=kimi-k2.5
neo
```

### Implementation Details
- `base_url` defaults to `None` → uses standard OpenAI API
- Set `base_url` → uses custom OpenAI-compatible API (Ollama, etc.)
- The OpenAI Python client natively supports `base_url` parameter

### API Key Differences

| Provider | API Key Required | Source |
|----------|------------------|--------|
| **OpenAI (default)** | Real key | https://platform.openai.com/api-keys |
| **Ollama Cloud** | Real key | https://ollama.com/settings |
| **Local/Remote Ollama** | Any string | e.g., "ollama" |

### Files Changed
- `neo/config.py` - Added `base_url` setting (default: None)
- `neo/llm/client.py` - Updated to accept optional `base_url`
- `neo/cli.py` - Pass `base_url` when creating client (if set)
- `.env.example` - Clear default (OpenAI) vs optional (Ollama) sections
- `README.md` - Emphasized OpenAI is default, Ollama is optional

## 2026-03-04 - Mock Mode & .env Support

### Added .env File Support
- Used `python-dotenv` to load .env files automatically
- Searches up to 5 parent directories for .env files
- Loads both `.env` and `.env.local` (for local overrides)

### Created Mock LLM Client
- `MockOpenAIClient` simulates LLM responses without API calls
- Auto-activates when no OPENAI_API_KEY is found
- Provides helpful feedback about being in mock mode
- Pattern-matches user input to generate relevant responses

### Configuration Priority
1. Environment variables (highest priority)
2. .env.local file
3. .env file
4. ~/.neo/config.json
5. Default values (lowest priority)

This allows users to:
- Test Neo without an API key
- Keep API keys in .env files (not committed to git)
- Override settings per-project with .env files

## 2026-03-04 - Phase 1 Implementation Complete

### What Was Implemented
1. **Project Structure**: Complete package structure with pyproject.toml
2. **Tool System**: 15 tools across 6 categories:
   - File tools: read_file, write_file, edit_file, list_dir, glob
   - Code tools: analyze_file, find_symbol
   - Search tools: search_code, view
   - Git tools: git_status, git_diff, git_add, git_commit, git_log
   - Shell tools: run_shell
   - System tools: get_system_info

3. **LLM Client**: OpenAI client with function calling support
4. **Memory System**: Session memory (conversation history) + Project memory (codebase context)
5. **Agent Loop**: Simple iteration loop with max 10 iterations
6. **CLI**: Interactive mode, single query mode, and direct tool execution

### Key Decisions Made
1. **Async throughout**: All tools are async to support concurrent operations
2. **OpenAI format**: Tools convert to OpenAI function format directly
3. **Safety first**: File operations create backups, shell has blocked commands
4. **Error handling**: All tools return ToolResult with success/error info
5. **Rich CLI**: Using Rich for syntax highlighting and nice UI

### What Was Deferred to Later Phases
- Tree-sitter integration (Phase 2)
- Streaming responses (Phase 4)
- Diff preview confirmation (Phase 3)
- Undo system (Phase 3)
- Test suite (Phase 4)

### Testing Notes
To test the implementation:
1. Install: `pip install -e .`
2. Set API key: `export OPENAI_API_KEY=...`
3. Run interactive: `neo`
4. Run single query: `neo ask "read the main file"`
5. Run tool directly: `neo --tool read_file file_path=main.py`

## 2026-03-04 - Project Initiation

### Starting Point
- Read DESIGN.md which contains comprehensive specifications for Neo
- Project is a coding-only local AI agent powered by OpenAI
- Goal is to be simpler and lighter than EDITH (which uses local models)

### Architecture Decisions
1. **Language**: Python 3.10+ (specified in DESIGN.md)
2. **LLM Backend**: OpenAI API (GPT-4o-mini as default)
3. **Memory System**: 2-tier (Session + Project) - deliberately simpler than EDITH's 4-tier
4. **Tool System**: 15 code-focused tools only, no general-purpose tools
5. **CLI Framework**: Click (as specified)
6. **UI**: Rich for syntax highlighting and terminal UI

### Implementation Strategy
Following Phase 1 (Foundation) from DESIGN.md:
1. Project structure setup
2. OpenAI client with function calling
3. Base tool class + registry
4. File tools (read, write, edit)
5. Simple agent loop
6. CLI skeleton

### Trade-offs Made
- Using OpenAI API means ongoing costs vs EDITH's free local models
- But we get instant startup, no model download, better code quality
- 2-tier memory is simpler but less powerful than full RAG system
- Single agent loop means no complex orchestration but also no parallel tasks

### Next Steps
Begin implementing the core package structure with pyproject.toml and the neo/ package.
