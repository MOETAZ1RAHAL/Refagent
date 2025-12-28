# Multi-agent LLM-based Framework for Automatic Software Refactoring

## Overview
This repository provides a **multi-agent LLM-based framework** for **automatic software refactoring**. The framework leverages **Large Language Models (LLMs)** to suggest and apply refactoring techniques, improving code maintainability and readability. The system integrates multiple agents to analyze, recommend, and validate code transformations automatically.

## Features
- Multi-agent architecture for software refactoring
- Utilization of **LLMs** (e.g., OpenAI, StarCoder, DeepSeekCoder, etc.)
- Compatibility with GitHub repositories for code retrieval, version control, and committing improvements

## Requirements
Before running the framework, you need to set up the environment.

### Environment Setup
1. **Create a `.env` file** in the project root and add the following environment variables:
    ```env
    API_KEY=""
    GITHUB_API_KEY=""
    MODEL_NAME="gpt-4o"
    ```
    Fill in the required API keys before running the framework.

    > ✅ If you want to use the framework with **DeepSeek models**, set `MODEL_NAME` to either `deepseek-coder` or `deepseek-chat`.  
    > The endpoint for DeepSeek is:  
    > `https://api.deepseek.com/v1/chat/completions`

2. **Hardware**:
   - Ideally runs on a **GPU** for efficiency
   - If using **open-source LLMs** (e.g., StarCoder, DeepSeek), ensure you are running with GPU support

# RefAgent — Multi-agent LLM-based Refactoring Framework

RefAgent is a multi-agent system that uses Large Language Models (LLMs) to analyze, suggest, and apply refactorings to Java projects. The pipeline can clone a repository tag, apply model-guided refactorings, compile and test, and optionally commit improvements back to the repository.

This README gives a compact, practical guide to set up and run the project.

---

## Quick start

- Run the full pipeline (clone → build → refactor):

```bash
./run_refAgent.sh <org/repo-name> <tag>
# e.g. ./run_refAgent.sh apache/maven v3.8.6
```

- Or run the Python pipeline directly when the project is already present in `projects/after/`:

```bash
python3 refAgent/RefAgent_main.py <project-name>
# e.g. python3 refAgent/RefAgent_main.py jclouds
```

---

## Prerequisites

- Python 3.9+
- Java (JDK) compatible with the target project
- Maven installed and on PATH (or the project's `mvnw` wrapper)
- Git
- LLM API credentials (OpenAI or another adapter supported by `refAgent/OpenaiLLM.py`)

Recommended Java versions
- For best compatibility with the built-in Python parser (`javalang`) and the tooling in this repo,
  we recommend using Java 8, 9, or 12 for projects you plan to analyze and refactor. If your project
  uses newer Java language features (post-Java 12), consider using a Java-based parser (e.g. JavaParser)
  or building with the project's `mvnw` wrapper and double-checking parsing results.

Important note about CompilerAgent & TestAgent
- The `CompilerAgent` and `TestAgent` are agents whose sole purpose is to compile and run
   Maven-based Java projects. They do not modify environment settings or install toolchains.
- It is critical that the Java (JDK) version and the Maven version (or the project's `mvnw` wrapper)
   exactly match what the target project expects. Mismatched Java/Maven versions are the most
   common cause of build and test failures and can produce misleading LLM diagnostics.
- The provided `run_refAgent.sh` performs a basic verification, but you should always confirm the
   JDK and Maven versions locally before running RefAgent. If the project provides `mvnw`,
   prefer using it (see Troubleshooting below).

Optional: GPU when running large local models.

## Configuration (.env)

Create a `.env` file in the repository root (read by `settings.py`):

```env
API_KEY="<your-llm-api-key>"
GITHUB_API_KEY="<your-github-token>"  # optional, used for commits
MODEL_NAME="gpt-4"
```

The `Settings` class (in `settings.py`) reads `.env` automatically.

## Install dependencies

Install Python dependencies into a virtualenv and activate it:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirment.txt
```

Note: the repository currently includes `requirment.txt` (typo preserved). Rename to `requirements.txt` if you prefer standard naming and update commands accordingly.

## How it works (high level)

- The main pipeline (`refAgent/RefAgent_main.py`) iterates over Java files in `projects/before/<project>`.
- Agents:
   - `PlannerAgent`: decides which methods need refactoring based on CKOO metrics.
   - `RefactoringGeneratorAgent`: asks the LLM to produce refactored Java code following the plan.
   - `CompilerAgent`: compiles the Maven project and asks the LLM to summarize compilation errors when compilation fails.
   - `TestAgent`: runs Maven tests, summarizes failing tests per-test, and can combine all failures into a single LLM-produced summary.
- Summaries from compiler/test failures are appended in-memory to `refactoring_generator.llm.message_history` so the `refactoring_generator` includes them as context in subsequent calls.

## Useful scripts

- `run_refAgent.sh <org/repo> <tag>` — clones the repo tag, copies to `projects/after/`, builds, and runs the Python pipeline. The script resolves its own directory so it reliably finds `refAgent/RefAgent_main.py`.

## Troubleshooting

- Can't find `RefAgent_main.py` from the shell script:
   - Ensure the script is executable (`chmod +x run_refAgent.sh`). The script now computes its own directory and runs the Python file by absolute path.
- Maven build issues:
   - Check Java version compatibility with the target project. Prefer using the project's `mvnw` wrapper where available.
   - Reminder: because `CompilerAgent` and `TestAgent` only invoke the build/test tools, they cannot
      recover from an incompatible JDK or Maven version. If you see cryptic compile errors, first verify
      you are using the correct Java and Maven versions that are known to build the project locally.
      The `.sh` script performs a basic check, but you should double-check manually with `java -version`
      and `mvn -v` (or `./mvnw -v`).
- LLM failures or rate limits:
   - Verify `.env` API keys and quotas.

## Development notes & suggestions

- Message history and context:
   - The current design keeps summaries in-memory per-agent (`OpenaiLLM.message_history`). If you want summaries available to multiple agents, either append the summary to each agent's history or use a shared LLM wrapper instance.
   - If you want summaries to persist across runs, save them into `results/<project>/` and reload them when the pipeline starts.


## License

MIT
