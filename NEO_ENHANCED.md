# Neo Enhanced - Complete Feature Set

Neo has been transformed from a simple coding assistant into a sophisticated multi-agent system with Claude Code-level capabilities.

---

## 1. Multi-Agent System

### Architecture
```
AgentOrchestrator (Routes tasks intelligently)
├── GeneralAgent      - Default coding tasks
├── ExploreAgent      - Fast codebase exploration
├── PlanAgent         - Implementation planning
└── CodeReviewAgent   - Code quality analysis
```

### Intelligent Routing
- **Heuristic routing** - Fast keyword-based routing
- **LLM routing** - Complex task analysis for routing
- **Confidence scoring** - Routes only when confident

### Parallel Execution
- Multiple tools execute concurrently
- Dependency graph for tool ordering
- Async throughout for responsiveness

---

## 2. Vector Memory System

### Semantic Code Search
- **ChromaDB** for vector storage
- **Sentence Transformers** for embeddings
- **Multi-language support** (Python, JS/TS, Go, Rust, Java, etc.)

### Code Indexing
- Automatic AST parsing for Python
- Pattern matching for JS/TS
- Fallback to semantic chunking

### Context Retrieval
```python
from neo.memory import ContextRetriever

retriever = ContextRetriever(project_path)
context = retriever.get_context_for_query(
    "How does authentication work?",
    max_chunks=5,
    max_files=3
)
```

---

## 3. Transaction System

### Atomic File Operations
```python
from neo.utils.transaction import FileTransaction

with FileTransaction(project_path) as txn:
    txn.write_file("new_file.py", content)
    txn.edit_file("existing.py", old_str, new_str)
    txn.delete_file("old_file.py")

    # Preview changes
    preview = txn.preview_changes()

    # Apply atomically
    result = txn.apply()
```

### Features
- Automatic backups before changes
- Diff preview
- Rollback on failure
- Batch operations
- Undo/redo stack

---

## 4. Textual TUI

### Layout
```
┌─────────────────────────────────────────────────────────┐
│  Neo v0.2.0 | gpt-4o-mini | 2,341 tokens | main        │
├──────────┬──────────────────────────────────────┬───────┤
│ File     │ Chat Area                            │       │
│ Tree     │                                      │       │
│          │ User: How does this work?            │       │
│ 📁 neo/  │                                      │       │
│ 📄 agent │ Neo: (typing...)                     │       │
│ 📄 cli   │ The agent system...                  │       │
│          │                                      │       │
│ 📁 mem   │                                      │       │
│          │                                      │       │
├──────────┴──────────────────────────────────────┴───────┤
│ > Type your message...                         [Send] │
└─────────────────────────────────────────────────────────┘
```

### Features
- **Streaming responses** - Real-time token display
- **File tree** - Interactive with git status
- **Syntax highlighting** - Code blocks highlighted
- **Diff viewer** - Side-by-side diff display
- **Command palette** - Ctrl+K for quick access
- **Multi-line input** - Full markdown support

---

## 5. Streaming Support

### True OpenAI Streaming
```python
async def callback(token: str) -> None:
    print(token, end="")

result = await llm.complete(
    messages=messages,
    stream=True,
    streaming_callback=callback,
)
```

### Benefits
- Immediate feedback
- Cancel mid-generation
- Better UX for long responses
- Token count updates in real-time

---

## Usage Examples

### Launch Enhanced TUI
```bash
# Install dependencies
pip install -r requirements.txt

# Set OpenAI key
export OPENAI_API_KEY="sk-..."

# Launch TUI
neo tui
```

### Use Specific Agent
```bash
# Query will be automatically routed
neo ask "find all authentication functions"
# -> Routes to ExploreAgent

neo ask "plan a refactor of the user module"
# -> Routes to PlanAgent

neo ask "add error handling to main.py"
# -> Routes to GeneralAgent
```

### Index Project for Semantic Search
```python
from neo.memory import CodeIndexer

indexer = CodeIndexer("/path/to/project")
indexer.index_project()  # Creates vector index

# Search
results = indexer.search("how to handle errors")
for chunk in results:
    print(f"{chunk.file_path}:{chunk.start_line}")
    print(chunk.content)
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+K` | Command Palette |
| `Ctrl+R` | Refresh File Tree |
| `Ctrl+D` | Show Git Diff |
| `Ctrl+G` | Git Status |
| `Ctrl+/` | Focus Input |
| `Enter`  | Send Message |
| `/status`| Show agent status |
| `/reset` | Clear memory |
| `/exit`  | Quit |

---

## Architecture Comparison

| Feature | Old Neo | Enhanced Neo | Claude Code |
|---------|---------|--------------|-------------|
| **Agent System** | Single | Multi-agent | Multi-agent |
| **Routing** | None | Heuristic + LLM | LLM-based |
| **Tool Parallelism** | Sequential | Parallel | Parallel |
| **Memory** | Basic | Vector + Semantic | Vector + Code Index |
| **UI** | Basic CLI | Rich TUI | Rich CLI |
| **Streaming** | No | Yes | Yes |
| **File Tree** | No | Yes | Limited |
| **Diff Viewer** | No | Yes | Yes |
| **Command Palette** | No | Yes | No |
| **Code Review** | No | Dedicated agent | Limited |
| **Transaction System** | Basic | Full atomic | Partial |
| **Semantic Search** | No | Yes | Yes |

---

## File Structure

```
neo/
├── agents/               # Multi-agent system
│   ├── base.py          # Base agent class
│   ├── general.py       # General coding agent
│   ├── explore.py       # Fast exploration agent
│   ├── plan.py          # Implementation planning
│   ├── code_review.py   # Code review agent
│   └── orchestrator.py  # Task routing
├── tui/                  # Textual interface
│   ├── widgets.py       # Custom widgets
│   └── app.py           # Main app
├── memory/               # Memory system
│   ├── vector.py        # Vector store
│   ├── code_indexer.py  # Code indexing
│   ├── context_retriever.py # Context retrieval
│   ├── project.py       # Project memory
│   └── session.py       # Session memory
├── utils/                # Utilities
│   └── transaction.py   # File transactions
├── llm/                  # LLM client
│   └── client.py        # OpenAI with streaming
├── agent.py              # Main agent (uses orchestrator)
├── cli.py                # CLI entry points
└── requirements.txt      # Dependencies
```

---

## Installation

```bash
# Clone and setup
cd Neo
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env and add OPENAI_API_KEY

# Run
neo tui
```

---

## Status

All major features have been implemented:
- [x] Multi-agent system with intelligent routing
- [x] Vector memory with semantic search
- [x] Textual TUI with streaming
- [x] Transaction system for file edits
- [x] True OpenAI streaming
- [x] Parallel tool execution

Neo is now a **Claude Code competitor** with a unique visual interface and superior context awareness through semantic search.
