# Neo - Local Coding Agent

## Design Specification & Implementation Requirements

---

## 1. Project Overview

### 1.1 Vision
Neo is a **coding-only local AI agent** designed specifically for software development tasks. Unlike general-purpose assistants, Neo focuses exclusively on:
- Code reading, writing, and editing
- Codebase navigation and understanding
- Git operations
- Shell command execution
- Project-specific context awareness

### 1.2 Key Differentiators from EDITH

| Aspect | EDITH | Neo |
|--------|-------|-----|
| Primary Use | General-purpose assistant | Coding-only agent |
| LLM Backend | Ollama (local/cloud) | OpenAI API |
| Memory System | 4-tier (STM, LTM, Project, Global) | 2-tier (Session, Project) |
| Tools | 30+ (web, apps, music, etc.) | 15-20 (code-focused only) |
| Multi-Agent | Yes (6 agent types) | No (single agent loop) |
| Telegram Bot | Yes | No |
| MCP Support | Yes | Optional/Future |
| Architecture | Complex orchestrator | Simple agent loop |
| Dependencies | Heavy (ChromaDB, transformers) | Light (OpenAI, tree-sitter) |

### 1.3 Core Philosophy
- **Minimal dependencies** - Fast to install, easy to run
- **Code-first design** - Every feature optimized for coding workflows
- **Fast iteration** - No heavy model loading, instant start
- **Project-aware** - Deep understanding of current codebase
- **Simple mental model** - Easy to understand and extend

---

## 2. Architecture

### 2.1 System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI Layer                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   Interactive │  │ Single Query │  │  Tool Direct     │  │
│  │   Mode        │  │ Mode (ask)   │  │  Mode (--tool)   │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      Agent Loop                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. Build Context (system + project + history)      │  │
│  │  2. Call OpenAI API (with function definitions)     │  │
│  │  3. Parse response (content vs function calls)      │  │
│  │  4. Execute tools                                   │  │
│  │  5. Return results to LLM (continue or finalize)   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────┬───────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
┌───────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐
│  LLM Client  │  │  Tool System │  │  Memory    │
│              │  │              │  │  System    │
│ • OpenAI API │  │ • File ops   │  │            │
│ • Streaming  │  │ • Git tools  │  │ • Session  │
│ • Function   │  │ • Search     │  │ • Project  │
│   calling    │  │ • Shell      │  │ • Code map │
└──────────────┘  └──────────────┘  └──────────────┘
```

### 2.2 Directory Structure

```
neo/
├── pyproject.toml           # Package config, dependencies
├── README.md                # Quick start guide
├── DESIGN.md               # This document
├── neo/
│   ├── __init__.py         # Version info
│   ├── __main__.py         # Entry point
│   ├── cli.py              # CLI interface (Click)
│   ├── config.py           # Settings management
│   ├── agent.py            # Main agent loop
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py       # OpenAI API client
│   │   └── streaming.py    # Response streaming
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py         # BaseTool class
│   │   ├── registry.py     # Tool registration
│   │   ├── file.py         # File operations
│   │   ├── code.py         # Code analysis tools
│   │   ├── git.py          # Git operations
│   │   ├── shell.py        # Shell execution
│   │   └── search.py       # Search tools
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── session.py      # Conversation history
│   │   └── project.py      # Project context
│   └── utils/
│       ├── __init__.py
│       ├── diff.py         # Diff utilities
│       ├── parser.py       # Code parsing
│       └── path.py         # Path utilities
├── tests/
│   ├── __init__.py
│   ├── test_tools.py
│   └── test_agent.py
└── examples/
    └── sample_prompts.md
```

---

## 3. Core Components

### 3.1 LLM Client (`neo/llm/client.py`)

**Responsibilities:**
- OpenAI API communication
- Function calling format conversion
- Response streaming
- Token tracking (simple)

**Key Classes:**
```python
class OpenAIClient:
    """OpenAI API client with function calling support."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        stream: bool = False,
    ) -> CompletionResult:
        """Send completion request to OpenAI."""
        pass

    def format_tools(self, tools: List[BaseTool]) -> List[Dict]:
        """Convert tools to OpenAI function format."""
        pass
```

**Supported Models:**
- `gpt-4o-mini` (default) - Fast, cheap, good for coding
- `gpt-4o` - More capable, higher cost
- `o1-mini` - Reasoning model (future)

**OpenAI Function Format:**
```python
{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read contents of a file",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"}
            },
            "required": ["file_path"]
        }
    }
}
```

### 3.2 Agent Loop (`neo/agent.py`)

**Simplified Design (vs EDITH's complex orchestrator):**

```python
class Agent:
    """Simple agent loop for coding tasks."""

    SYSTEM_PROMPT = """You are Neo, a coding assistant.

You help users write, read, and modify code. You have access to tools for:
- Reading and writing files
- Running shell commands
- Git operations
- Searching code

Guidelines:
1. Use tools to explore before making changes
2. Show diffs before editing files
3. Write clean, documented code
4. Run tests or checks when available
5. Be concise - focus on code, not explanations

Project Context:
{project_context}
"""

    def __init__(self, llm: OpenAIClient, tools: ToolRegistry, project_path: Path):
        self.llm = llm
        self.tools = tools
        self.memory = SessionMemory()
        self.project = ProjectMemory(project_path)
        self.max_iterations = 10

    async def run(self, user_input: str) -> str:
        """Execute user request."""
        # Build context
        messages = [
            {"role": "system", "content": self.build_context()},
            *self.memory.get_messages(),
            {"role": "user", "content": user_input}
        ]

        for iteration in range(self.max_iterations):
            # Call LLM
            result = await self.llm.complete(
                messages=messages,
                tools=self.tools.to_openai_format()
            )

            if result.has_function_calls():
                # Execute tools
                tool_results = await self.execute_tools(result.function_calls)
                messages.extend(tool_results)
            else:
                # Final response
                self.memory.add_turn(user_input, result.content)
                return result.content

        return "Max iterations reached."

    def build_context(self) -> str:
        """Build system context with project info."""
        return self.SYSTEM_PROMPT.format(
            project_context=self.project.get_context()
        )
```

### 3.3 Tool System

**Base Class (`neo/tools/base.py`):**
```python
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class ToolResult:
    success: bool
    output: str
    error: Optional[str] = None
    data: Optional[Dict] = None

class BaseTool(ABC):
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass

    def to_openai_format(self) -> Dict:
        """Convert to OpenAI function format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }
```

**Core Tools (15 tools):**

| Category | Tool | Description |
|----------|------|-------------|
| **File** | `read_file` | Read file with offset/limit |
| | `write_file` | Write file (atomic) |
| | `edit_file` | String replacement |
| | `list_dir` | List directory contents |
| | `glob` | Pattern matching |
| **Code** | `view` | View file with line numbers |
| | `search_code` | Regex search |
| | `find_symbol` | Find class/function defs |
| | `analyze_file` | Get imports, structure |
| **Git** | `git_status` | Repository status |
| | `git_diff` | Show changes |
| | `git_add` | Stage files |
| | `git_commit` | Commit changes |
| | `git_log` | View history |
| **Shell** | `run_shell` | Execute commands |
| **System** | `get_system_info` | OS, time, env |

### 3.4 Memory System

**Simplified 2-Tier Approach:**

#### Session Memory (`neo/memory/session.py`)
```python
class SessionMemory:
    """In-memory conversation history."""

    def __init__(self, max_turns: int = 20):
        self.turns: List[Turn] = []
        self.max_turns = max_turns

    def add_turn(self, role: str, content: str):
        self.turns.append(Turn(role, content))
        if len(self.turns) > self.max_turns:
            # Keep first system message, remove oldest user/assistant
            self.turns = [self.turns[0]] + self.turns[-(self.max_turns-1):]

    def get_messages(self) -> List[Dict]:
        return [{"role": t.role, "content": t.content} for t in self.turns]
```

#### Project Memory (`neo/memory/project.py`)
```python
class ProjectMemory:
    """Project-specific context stored in .neo/project.json."""

    def __init__(self, project_path: Path):
        self.path = project_path
        self.config_file = project_path / ".neo" / "project.json"
        self.code_map: Dict[str, FileInfo] = {}
        self.load()

    def scan_project(self):
        """Build code map of the project."""
        # Index: files, symbols, imports
        # Use tree-sitter for parsing
        pass

    def get_context(self) -> str:
        """Generate project context for system prompt."""
        lines = [
            f"Project: {self.path.name}",
            f"Languages: {', '.join(self.languages)}",
            f"Key files: {', '.join(self.key_files)}",
            # Recent changes, TODOs, etc.
        ]
        return "\n".join(lines)
```

**No Long-Term Memory** - Unlike EDITH, Neo doesn't persist user facts or have vector search. Keeps things simple.

---

## 4. Implementation Details

### 4.1 OpenAI Function Calling Flow

```python
# 1. Define tools in OpenAI format
tools = [tool.to_openai_format() for tool in registry.get_tools()]

# 2. Send request with tools
response = await client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages,
    tools=tools,
    tool_choice="auto"
)

# 3. Check for function calls
message = response.choices[0].message

if message.tool_calls:
    # Execute each tool call
    for tool_call in message.tool_calls:
        result = await registry.execute(
            tool_call.function.name,
            json.loads(tool_call.function.arguments)
        )
        # Add result to messages
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": result.output
        })

    # Send results back to LLM
    final_response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )
```

### 4.2 Code Analysis with Tree-sitter

**Parser Integration:**
```python
# Use tree-sitter for fast, accurate parsing
from tree_sitter import Language, Parser

class CodeAnalyzer:
    """Analyze code structure using tree-sitter."""

    SUPPORTED_LANGS = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.go': 'go',
        '.rs': 'rust',
        '.java': 'java',
        '.c': 'c',
        '.cpp': 'cpp',
    }

    def parse_file(self, file_path: str) -> FileStructure:
        """Parse file and extract symbols."""
        # Parse AST
        # Extract: classes, functions, imports
        # Return structured data
        pass

    def find_symbol(self, name: str) -> List[SymbolLocation]:
        """Find symbol definition in codebase."""
        # Search indexed code map
        pass
```

### 4.3 File Operations

**Atomic Writes with Backup:**
```python
class FileTool(BaseTool):
    async def write_file(self, path: str, content: str) -> ToolResult:
        try:
            filepath = Path(path).expanduser().resolve()

            # Create backup if file exists
            if filepath.exists():
                backup = filepath.with_suffix(filepath.suffix + ".neo.bak")
                shutil.copy2(filepath, backup)

            # Atomic write
            temp = filepath.with_suffix(filepath.suffix + ".neo.tmp")
            temp.write_text(content, encoding='utf-8')
            temp.rename(filepath)

            return ToolResult(success=True, output=f"Wrote {filepath}")

        except Exception as e:
            return ToolResult(success=False, error=str(e))
```

### 4.4 Diff Preview

**Before every edit, show diff:**
```python
def preview_edit(file_path: str, old: str, new: str) -> str:
    """Generate unified diff for preview."""
    import difflib

    original = Path(file_path).read_text()
    modified = original.replace(old, new, 1)

    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        modified.splitlines(keepends=True),
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}"
    )
    return ''.join(diff)
```

---

## 5. CLI Design

### 5.1 Commands

```bash
# Interactive mode (default)
neo

# Single query
neo ask "refactor this function to use async"

# Direct tool execution
neo --tool read_file file_path=main.py

# With specific model
neo --model gpt-4o

# Initialize project
neo init

# Show version
neo --version
```

### 5.2 Interactive Mode Features

```
$ neo

Neo v0.1.0 - Coding Assistant (gpt-4o-mini)
Working: /home/user/myproject

> read the main file
[Reading main.py...]

23 | def main():
24 |     """Entry point."""
25 |     parser = argparse.ArgumentParser()
...

> refactor main() to use click instead of argparse
[Viewing changes...]

--- a/main.py
+++ b/main.py
@@ -20,10 +20,9 @@
-import argparse
+import click

-def main():
-    parser = argparse.ArgumentParser()
-    args = parser.parse_args()
+@click.command()
+def main():
+    pass

Apply changes? [Y/n]: y
[Changes applied]

> /status
Model: gpt-4o-mini
Tokens: 2,341
Files modified: 1

> exit
```

### 5.3 Slash Commands

| Command | Description |
|---------|-------------|
| `/status` | Show model, token usage, session info |
| `/model <name>` | Switch model |
| `/reset` | Clear conversation history |
| `/project` | Show project info |
| `/diff` | Show git diff |
| `/undo` | Undo last file change |
| `/help` | Show commands |
| `/exit` | Quit |

---

## 6. Configuration

### 6.1 Settings Location

```
~/.neo/config.json          # Global config
./.neo/project.json          # Project-specific
```

### 6.2 Configuration Schema

```python
@dataclass
class Config:
    # OpenAI
    openai_api_key: str
    model: str = "gpt-4o-mini"

    # Behavior
    max_iterations: int = 10
    auto_confirm_edits: bool = False
    show_diffs: bool = True

    # Context
    max_session_turns: int = 20
    include_project_context: bool = True

    # UI
    theme: str = "monokai"
    streaming: bool = True

    # Safety
    shell_blocked_commands: List[str] = field(default_factory=lambda: [
        "rm -rf /",
        "format",
    ])

    @classmethod
    def load(cls) -> "Config":
        # Load from ~/.neo/config.json
        # Fallback to env vars
        pass
```

### 6.3 Environment Variables

```bash
export OPENAI_API_KEY="sk-..."
export NEO_MODEL="gpt-4o"
export NEO_AUTO_CONFIRM="false"
```

---

## 7. Dependencies

### 7.1 Core Dependencies

```toml
[project]
name = "neo"
version = "0.1.0"
description = "Local coding agent powered by OpenAI"
requires-python = ">=3.10"

dependencies = [
    # LLM
    "openai>=1.0.0",

    # CLI
    "click>=8.0.0",
    "rich>=13.0.0",

    # Code parsing
    "tree-sitter>=0.20.0",
    "tree-sitter-python>=0.20.0",
    "tree-sitter-javascript>=0.20.0",
    # ... language parsers as needed

    # Utilities
    "pydantic>=2.0.0",
    "platformdirs>=4.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]

[project.scripts]
neo = "neo.cli:main"
```

### 7.2 Why These Dependencies?

| Package | Purpose | Why |
|---------|---------|-----|
| `openai` | API client | Official, supports streaming & functions |
| `click` | CLI framework | Simple, well-documented |
| `rich` | Terminal UI | Syntax highlighting, panels, progress |
| `tree-sitter` | Parsing | Fast, accurate, multi-language |
| `pydantic` | Validation | Type safety, JSON handling |
| `platformdirs` | Paths | Cross-platform config locations |

### 7.3 What's NOT Included

- ❌ No ChromaDB (no vector search)
- ❌ No sentence-transformers (no embeddings)
- ❌ No ollama (OpenAI only)
- ❌ No telegram-bot
- ❌ No httpx (use aiohttp or stdlib)
- ❌ No beautifulsoup4 (code focus, no web)

---

## 8. Implementation Phases

### Phase 1: Foundation (Week 1)

**Goal:** Basic working agent

- [ ] Project structure setup
- [ ] OpenAI client with function calling
- [ ] Base tool class + registry
- [ ] File tools (read, write, edit)
- [ ] Simple agent loop
- [ ] CLI skeleton

**Deliverable:** Can read/write files via prompts

### Phase 2: Code Intelligence (Week 2)

**Goal:** Understand codebases

- [ ] Tree-sitter integration
- [ ] Code parsing for Python, JS, TS
- [ ] Symbol indexing
- [ ] Search tools (code search, symbol lookup)
- [ ] Project context generation

**Deliverable:** "Find where X is defined", "Search for Y"

### Phase 3: Git & Shell (Week 3)

**Goal:** Full development workflow

- [ ] Git tools (status, diff, add, commit)
- [ ] Shell execution
- [ ] Diff preview for edits
- [ ] Undo system
- [ ] Safety checks

**Deliverable:** Can make changes and commit them

### Phase 4: Polish (Week 4)

**Goal:** Production-ready

- [ ] Streaming responses
- [ ] Better error handling
- [ ] Configuration system
- [ ] Documentation
- [ ] Tests
- [ ] PyPI packaging

**Deliverable:** Publish to PyPI, usable by others

---

## 9. Testing Strategy

### 9.1 Unit Tests

```python
# test_tools_file.py
async def test_read_file():
    tool = ReadFileTool()
    result = await tool.execute(file_path="test.py")
    assert result.success
    assert "content" in result.data

async def test_edit_file():
    tool = EditFileTool()
    # Create temp file
    # Apply edit
    # Verify result
    # Check backup created
```

### 9.2 Integration Tests

```python
# test_agent.py
async def test_agent_file_operations():
    agent = Agent(llm=mock_llm, tools=tools)
    response = await agent.run("read main.py and add a docstring")
    assert "docstring added" in response
```

### 9.3 E2E Tests

```bash
# Test actual CLI
neo ask "create a hello world Python script"
[verify hello.py exists]
```

---

## 10. Future Enhancements

### 10.1 Phase 2 Ideas (Post-Launch)

- [ ] More languages (Go, Rust, Java, C++)
- [ ] Refactoring tools (rename symbol, extract function)
- [ ] Test runner integration
- [ ] LSP integration for richer code intel
- [ ] Multi-file editing with planning
- [ ] Code review mode

### 10.2 MCP Support (Optional)

Add MCP client for external tools:
```python
# Future MCP integration
async def connect_mcp_server(name: str, command: str):
    """Connect to MCP server for additional tools."""
    pass
```

---

## 11. Comparison: EDITH vs Neo

| Feature | EDITH | Neo |
|---------|-------|-----|
| **Setup Time** | 5+ min (download models) | 30 sec (pip install) |
| **Memory** | 4-tier, complex | 2-tier, simple |
| **Startup** | Slow (model loading) | Instant |
| **Cost** | Free (local) | Pay per use (OpenAI) |
| **Tools** | 30+ (kitchen sink) | 15 (code-focused) |
| **Dependencies** | 20+ heavy packages | 10 light packages |
| **Multi-Agent** | Yes | No |
| **Web Tools** | Yes | No |
| **App Control** | Yes | No |
| **Best For** | General tasks | Pure coding |

---

## 12. Success Metrics

Neo is successful if:

1. **Installs in < 1 minute** (excluding API key setup)
2. **Starts instantly** (no model download)
3. **Handles 90% of coding tasks** without reaching for editor
4. **Code quality matches** careful human coding
5. **Users prefer it** over EDITH for coding tasks

---

## 13. Appendix

### 13.1 Example Session

```
$ neo

Neo v0.1.0 (gpt-4o-mini)
Project: myproject (Python)

> what's the structure of this project?
Analyzing project...

myproject/
├── src/
│   ├── __init__.py
│   ├── main.py          (Entry point)
│   ├── utils/
│   │   └── helpers.py
├── tests/
│   └── test_main.py
└── pyproject.toml

Key symbols:
- main.run() in src/main.py
- utils.process_data() in src/utils/helpers.py

> add error handling to run()
Reading src/main.py...

[Proposed changes to add try/except in run()]

Apply? [Y/n/diff]: diff

--- a/src/main.py
+++ b/src/main.py
@@ -10,5 +10,11 @@
 def run():
-    data = load_data()
-    process_data(data)
+    try:
+        data = load_data()
+        process_data(data)
+    except FileNotFoundError as e:
+        print(f"Error: {e}")
+        sys.exit(1)

Apply? [Y/n]: y
[Changes applied]

> commit these changes
Running: git add src/main.py && git commit -m "Add error handling to run()"

[main 3a2f1b9] Add error handling to run()
 1 file changed, 6 insertions(+), 2 deletions(-)

> exit
```

### 13.2 File Templates

**New Project Structure:**
```
neo-new-project/
├── pyproject.toml
├── README.md
├── .gitignore
├── .neo/
│   └── project.json
├── src/
│   └── __init__.py
└── tests/
    └── __init__.py
```

---

## 14. Conclusion

Neo is designed to be a **lean, fast, coding-focused agent** that leverages OpenAI's API for intelligent code operations. By removing the complexity of local model management, multi-agent orchestration, and general-purpose features, Neo can deliver a superior coding experience with minimal setup and maintenance.

**Key Principles:**
1. **Do one thing well** - Coding assistance only
2. **Fast and light** - Minimal dependencies, instant startup
3. **Simple mental model** - Easy to understand and extend
4. **Pay for quality** - Use best-in-class models via API
5. **Code-first UX** - Every interaction optimized for developers
