# Neo Enhanced - Quick Start Guide

## What We've Built

Neo has been transformed into a **Claude Code competitor** with:

1. **Multi-Agent System** - Intelligent task routing to specialized agents
2. **Vector Memory** - Semantic code search using embeddings
3. **Textual TUI** - Rich terminal UI with streaming
4. **Transaction System** - Atomic file operations with rollback
5. **True Streaming** - Real-time OpenAI response streaming

---

## Installation

### 1. Install Dependencies

```bash
cd Neo
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Configure API Key

Create `.env` file:

```bash
OPENAI_API_KEY="sk-your-key-here"
```

Or set as environment variable:

```bash
# Windows
set OPENAI_API_KEY=sk-your-key-here

# Linux/Mac
export OPENAI_API_KEY=sk-your-key-here
```

---

## Usage

### Launch Enhanced TUI

```bash
neo tui
```

### Traditional Interactive Mode

```bash
neo
```

### Single Query

```bash
neo ask "refactor the main function to use async"
```

---

## Features

### Multi-Agent System

The orchestrator automatically routes tasks:

- **"Find all authentication functions"** → ExploreAgent
- **"Plan a refactor of the user module"** → PlanAgent
- **"Add error handling to main.py"** → GeneralAgent
- **"Review this code for bugs"** → CodeReviewAgent

### Textual TUI

```
┌─────────────────────────────────────────────────────────┐
│  Neo v0.2.0 | gpt-4o-mini | Ready | main              │
├──────────┬──────────────────────────────────────┬───────┤
│ 📂 Project│                                     │       │
│ 📁 neo/   │ User: What does the agent do?      │       │
│ 📄 agent  │                                    │       │
│ 📄 cli    │ Neo: The agent system uses         │       │
│ 📁 mem    │ orchestration to route tasks...    │       │
│ 📁 tui    │                                    │       │
│           │                                    │       │
├──────────┴──────────────────────────────────────┴───────┤
│ > Type /help for commands...                            │
└─────────────────────────────────────────────────────────┘
```

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+K` | Command Palette |
| `Ctrl+R` | Refresh File Tree |
| `Ctrl+D` | Show Git Diff |
| `Ctrl+G` | Git Status |
| `/status`| Show status |
| `/reset` | Clear memory |
| `/exit`  | Quit |

---

## Architecture

```
User Input
    ↓
AgentOrchestrator
    ↓ (routes based on content)
GeneralAgent / ExploreAgent / PlanAgent / CodeReviewAgent
    ↓ (uses)
LLM + Tools + Vector Memory + Transaction System
    ↓
Response
```

---

## Project Structure

```
neo/
├── agents/           # Multi-agent system
│   ├── base.py
│   ├── general.py
│   ├── explore.py
│   ├── plan.py
│   ├── code_review.py
│   └── orchestrator.py
├── tui/              # Textual interface
│   ├── widgets.py
│   └── app.py
├── memory/           # Vector + context
│   ├── vector.py
│   ├── code_indexer.py
│   ├── context_retriever.py
│   ├── project.py
│   └── session.py
├── utils/            # Utilities
│   └── transaction.py
├── llm/              # OpenAI client
│   └── client.py
├── agent.py          # Main agent
├── cli.py            # CLI
└── tools/            # Tools
```

---

## Comparison

| Feature | Old Neo | Enhanced Neo | Claude Code |
|---------|---------|--------------|-------------|
| Agents | Single | Multi (4 types) | Multi |
| Routing | None | Heuristic + LLM | LLM |
| UI | CLI | Rich TUI | Rich CLI |
| Streaming | No | Yes | Yes |
| Semantic Search | No | Yes | Yes |
| File Tree | No | Yes | Limited |
| Transactions | Basic | Full | Partial |
| Diff Viewer | No | Yes | Yes |
| Command Palette | No | Yes | No |

---

## Next Steps

To complete your setup:

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Set API key**: Add `OPENAI_API_KEY` to `.env`
3. **Launch**: `neo tui`

Optional:
- Add more language parsers (tree-sitter)
- Configure model in `neo init`
- Customize TUI theme

---

## Development

Run tests:
```bash
pytest
```

Check types:
```bash
mypy neo/
```

Lint:
```bash
ruff check .
```

---

Enjoy your enhanced coding assistant!
