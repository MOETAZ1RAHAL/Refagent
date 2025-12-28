
RefAgent-Local: A Local LLM-based Multi-Agent Framework for Automatic Java Refactoring with PMD Integration
License: MIT
Python
Java

RefAgent-Local is a fully local, API-key-free adaptation of the original RefAgent framework. The main contributions of this fork are:

Integration of PMD to automatically detect God Classes and restrict refactoring to only those high-complexity classes.
Replacement of remote LLM APIs (OpenAI, DeepSeek, etc.) with a local model (StarCoder2 3B via Ollama) for complete privacy and zero cost.
Removal of dependency graph generation (javalang incompatibility with modern Java) and other non-essential components to improve reliability on real-world projects.
The core multi-agent architecture is preserved:

PlannerAgent – decides whether a class needs refactoring based on CKO metrics (DesigniteJava).
RefactoringGeneratorAgent – proposes refactored code using the local model.
CompilerAgent – compiles the modified project and summarizes errors (if any).
TestAgent – runs the full Maven test suite and provides feedback.
Refactoring is performed iteratively (up to 20 attempts per class) with self-reflection via compilation and test failures.

Features
PMD-based God Class detection → targeted refactoring
100% local inference (StarCoder2 3B via Ollama) → no API keys required
DesigniteJava for before/after CKO metrics and code smell analysis
Maven-based compilation and testing with automatic feedback loop
Results (original/improved code, metrics, iteration logs) saved per class
Requirements
Linux/WSL (tested on Ubuntu 22.04 under WSL2)
Java JDK 17+
Maven
Python 3.9+
Ollama (with starcoder2:3b model pulled)
PMD 7.19.0
DesigniteJava.jar (community edition)
Git
Quick Start
Start Ollama server
Bash
ollama serve &
ollama pull starcoder2:3b
Clone a target project (example: Apache jclouds)
Bash
mkdir -p ~/projects/before ~/projects/after
git clone https://github.com/apache/jclouds.git ~/projects/before/jclouds --depth 1
cp -r ~/projects/before/jclouds ~/projects/after/jclouds
Activate virtual environment and run
Bash
cd /path/to/RefAgent-Local
source venv_refagent/bin/activate
python -m refAgent.RefAgent_main jclouds
PMD will detect God Classes, and the agents will attempt targeted refactoring using only the local model.

Tested Projects
Project	God Classes Detected	Notes
google/gson	11	Very clean codebase; few improvement opportunities
apache/jclouds	28	Larger codebase; active refactoring iterations observed
Limitations
StarCoder2 3B is smaller than the models used in the original paper → more iterations needed and lower success rate on complex generics-heavy code.
Dependency graph generation disabled due to javalang limitations.
Tested primarily on Maven-based Java projects.


