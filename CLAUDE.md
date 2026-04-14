# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is an open-source Chinese tutorial project about Harness Engineering ("self-harness" / "dive-into-context-engineering"). It contains two distinct parts:

1. **Documentation site** (`docs/`): A VitePress-based site (Chinese) explaining Prompt Engineering, Context Engineering, and Harness Engineering concepts.
2. **miniMaster implementation** (`code/miniMaster2.0/`): A minimal Python harness system demonstrating a three-layer agent architecture.

## Commands

### Documentation (VitePress)

```bash
# Install dependencies
npm install

# Start local dev server
npm run docs:dev

# Build for production
npm run docs:build

# Preview production build
npm run docs:preview
```

The docs deploy automatically to GitHub Pages via `.github/workflows/deploy.yml` on every push to `main`. The VitePress base path auto-switches between `/` (EdgeOne, when `EDGEONE` env var is set) and `/dive-into-context-engineering/` (GitHub Pages).

### miniMaster

There is no formal test runner or build step. To run the agent:

```bash
cd code/miniMaster2.0
python main_agent.py
```

Note: `requirements.txt` only lists `python-dotenv`, but the code also imports `openai`, `langsmith`, and `tqdm` at runtime.

## Architecture

### Documentation Structure (`docs/`)

- Config lives in `docs/.vitepress/config.mts`.
- Content is organized into 6 chapters under `docs/chapter{1..6}/`.
- Static assets (images, GIFs) live in `docs/public/`.
- Math rendering is enabled via VitePress's built-in math feature.

### miniMaster Architecture (`code/miniMaster2.0/`)

The system is built around a **three-layer nested loop** with dynamic memory management:

1. **Plan-Agent** (outer loop): Decomposes the user's query into a task list (`ToDoList`), then dispatches tasks one-by-one to sub-agents via `subagent_tool`.
2. **Generator-Agent** (middle loop): Executes a single task step-by-step using available tools. It maintains a `WorkingMemory` of tool calls and results. When it considers the task done, it calls `update_task_conclusion` and hands off to validation.
3. **Validate-Agent** (inner loop): Independently verifies whether the task was completed correctly. If validation fails, it injects feedback back into the Generator's `WorkingMemory` and the Generator retries.

**Dynamic Working Memory**

- `WorkingMemory` stores tool execution history.
- When the total prompt context exceeds a character threshold (`max_chars`, default ~45k), it summarizes old memories (keeping the last `keep_latest_n` steps uncompressed) to stay within context limits.

**Tool Registry**

- `utils/get_tools.py` provides a `ToolRegistry` that auto-discovers and registers tools from the `tools/` directory at runtime.
- Tools are grouped by module: `base_tool/` (bash, read, write, edit) and `search_tool/` (glob, grep).
- Each tool class exposes `name`, `description`, `run(parameters)`, and `prompt_block()` for LLM prompt generation.

**Environment**

miniMaster reads from a `.env` file in `code/miniMaster2.0/`:

- `API_KEY` (required)
- `BASE_URL` (required)
- `MODEL_NAME` (optional, defaults to `deepseek-chat`)

The client is wrapped with `langsmith.wrappers.wrap_openai` and all three agent brain functions (`call_plan_agent`, `call_generator_agent`, `call_validate_agent`) are decorated with `@traceable` for LangSmith tracing.

**Model Output Parsing**

All agents output XML-like tags that are parsed by `parse_model_output()`:

- `<think>...</think>`
- `<tool>...</tool>`
- `<parameter>...</parameter>` (JSON payload)
