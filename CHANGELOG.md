# Neo - Changelog

## [2026-03-04 - Ollama Support]
### Task: OpenAI-Compatible API Support (Ollama Cloud, Local Ollama, vLLM, etc.)
- **Summary**: Added support for OpenAI-compatible APIs as an **optional alternative** to OpenAI. OpenAI remains the default.
- **Default Behavior**: OpenAI API (no configuration needed besides `OPENAI_API_KEY`)
- **Optional**: Set `OPENAI_BASE_URL` to use Ollama Cloud, local Ollama, or any OpenAI-compatible API instead
- **Files Modified**:
  - `neo/config.py` - Added `base_url` setting (default: None = use OpenAI)
  - `neo/llm/client.py` - Updated to accept custom `base_url` for OpenAI client
  - `neo/cli.py` - Pass `base_url` to LLM client
  - `.env.example` - Clear separation: OpenAI (default) vs Ollama (optional)
  - `README.md` - Documented that OpenAI is default, Ollama is optional
- **Design Considerations**:
  - **Default**: OpenAI API with `base_url=None` (standard OpenAI endpoint)
  - **Optional**: Set `OPENAI_BASE_URL` to use Ollama Cloud, local Ollama, vLLM, etc.
  - OpenAI client natively supports custom base URLs via `base_url` parameter
  - Works with Ollama Cloud (api.ollama.com) - requires real API key
  - Works with local Ollama - API key can be any string (e.g., "ollama")
  - No local Ollama installation required - can use remote Ollama server
- **API Key Differences**:
  - **OpenAI (default)**: Real API key from https://platform.openai.com/api-keys
  - **Ollama Cloud (api.ollama.com)**: Real API key from https://ollama.com/settings
  - **Local/Custom Ollama**: API key can be any string (e.g., "ollama")
- **Usage**:
  ```bash
  # Default: OpenAI (just set API key)
  export OPENAI_API_KEY=sk-...
  neo

  # Optional: Ollama Cloud
  export OPENAI_BASE_URL=https://api.ollama.com/v1
  export OPENAI_API_KEY=your-ollama-api-key
  export NEO_MODEL=kimi-k2.5
  neo

  # Optional: Local Ollama
  export OPENAI_BASE_URL=http://localhost:11434/v1
  export OPENAI_API_KEY=ollama
  export NEO_MODEL=kimi-k2.5
  neo
  ```

## [2026-03-04 - Mock Mode & .env Support]
### Task: Testing Support Without API Keys
- **Summary**: Added mock LLM client and .env file support for testing
- **Files Added**:
  - `neo/llm/mock.py` - Mock OpenAI client for testing without API keys
  - `.env.example` - Example environment configuration file
- **Files Modified**:
  - `pyproject.toml` - Added `python-dotenv` dependency
  - `neo/config.py` - Added .env file loading and `mock_mode` setting
  - `neo/cli.py` - Updated to use mock client when no API key available
  - `README.md` - Documented .env configuration options
- **Design Considerations**:
  - Auto-detects missing API key and switches to mock mode with warning
  - Searches for .env files in current directory and up to 5 parent directories
  - Mock client simulates responses based on user input patterns
  - All tools still work in mock mode (agent uses real tools with mock LLM)
- **Usage**:
  ```bash
  # Without API key - runs in mock mode automatically
  neo

  # With .env file
  cp .env.example .env
  # Edit .env with your OPENAI_API_KEY
  neo

  # Force mock mode
  NEO_MOCK=true neo
  ```

## [2026-03-04 - Bug Fixes]
### Task: Tool Parameter Type Fixes
- **Summary**: Fixed type conversion issues when tools are called from CLI with string parameters
- **Files Modified**:
  - `neo/tools/file.py` - Fixed `read_file` tool to handle string offset/limit params
  - `neo/tools/search.py` - Fixed `view` tool to handle string line/context params
  - `neo/tools/git.py` - Fixed `git_log` tool to handle string count/oneline params
  - `neo/tools/shell.py` - Fixed `run_shell` tool to handle string timeout param
- **Issue**: CLI passes all arguments as strings, but tools expected int/bool types
- **Solution**: Added type conversion at the start of execute methods

## [2026-03-04 - Phase 1 Complete]
### Task: Foundation Implementation Complete
- **Summary**: Implemented all Phase 1 components of Neo
- **Files Added**:
  - `pyproject.toml` - Package configuration with dependencies
  - `neo/__init__.py` - Package version info
  - `neo/__main__.py` - Entry point
  - `neo/cli.py` - CLI interface with Click and Rich
  - `neo/config.py` - Configuration management
  - `neo/agent.py` - Main agent loop with OpenAI function calling
  - `neo/llm/client.py` - OpenAI API client
  - `neo/llm/__init__.py` - LLM package
  - `neo/memory/session.py` - Conversation history
  - `neo/memory/project.py` - Project context
  - `neo/memory/__init__.py` - Memory package
  - `neo/tools/base.py` - Base tool class
  - `neo/tools/registry.py` - Tool registration system
  - `neo/tools/file.py` - File operations (read, write, edit, list, glob)
  - `neo/tools/shell.py` - Shell command execution
  - `neo/tools/git.py` - Git operations (status, diff, add, commit, log)
  - `neo/tools/search.py` - Code search and view tools
  - `neo/tools/code.py` - Code analysis (analyze_file, find_symbol)
  - `neo/tools/system.py` - System information
  - `neo/utils/diff.py` - Diff utilities
  - `neo/utils/path.py` - Path utilities
  - `README.md` - Project documentation
- **Design Considerations**:
  - 15 tools implemented as per DESIGN.md specification
  - 2-tier memory system (Session + Project)
  - Simple agent loop with max 10 iterations
  - Atomic file writes with backup
  - Safety checks for shell commands
- **Architecture**:
  ```
  CLI -> Agent -> LLM Client -> OpenAI API
            |
            v
  Tool Registry -> 15 code-focused tools
            |
            v
  Memory (Session + Project)
  ```

## [2026-03-04 - Initial Setup]
### Task: Project Structure Setup - Phase 1 Foundation
- **Summary**: Initial project scaffolding and repository setup
- **Files Added**:
  - `CHANGELOG.md` - This file, tracking all project changes
  - `DEVLOG.md` - Developer diary for architectural decisions
- **Design Considerations**:
  - Following semantic versioning approach
  - Chronological logging with task-based grouping
  - Tracking design decisions and their justifications
- **Notes for Future Developers**:
  - Update this file with every significant change
  - Include rationale for architectural decisions
  - Link to relevant design documents when applicable
