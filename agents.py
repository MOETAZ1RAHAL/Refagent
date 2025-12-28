from refAgent.OpenaiLLM import OpenAILLM
from refAgent.prompt import REFACTORING_GENERATOR_PROMPT, PLANNER_PROMPT, COMPILER_PROMPT, TEST_SUMMARY_PROMPT, MULTI_TEST_SUMMARY_PROMPT
from refAgent.utilities import compile_project_with_maven, run_maven_test
from typing import Optional
from settings import Settings

# Load settings once for default token limits
_config = Settings()


class BaseAgent:
    """Minimal base agent that wraps an LLM instance and provides a send helper.

    Subclasses can reuse `send` to call the LLM and get a cleaned text reply.
    """

    def __init__(self, api_key: str, model: str = "gpt-4", max_tokens: Optional[int] = None):
        self.llm = OpenAILLM(api_key)
        self.model = model
        # per-agent max tokens (fallback to global default)
        self.max_tokens = max_tokens if max_tokens is not None else _config.DEFAULT_MAX_TOKENS

    def send(self, system_prompt: Optional[str], user_query: str, max_tokens: Optional[int] = None) -> str:
        """Call the underlying LLM and return a cleaned string reply.

        This method strips surrounding triple-backtick code fences if present.
        """
        # prefer explicit call-time max_tokens, otherwise use agent default
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        reply = self.llm.query_llm(system_prompt, user_query, model=self.model, max_tokens=tokens)

        if not isinstance(reply, str):
            return reply

        text = reply.strip()
        if text.startswith("```") and text.endswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                return "\n".join(lines[1:-1])
            return ""

        return text


class RefactoringGeneratorAgent(BaseAgent):
    """Agent that executes the strict executor prompt workflow.

    By default it uses `EXECUTOR_PROMPT` as the system prompt; a prompt override
    can be provided per-call.
    """

    def __init__(self, api_key: str, model: str = "gpt-4", max_tokens: Optional[int] = None):
        # default to configured refactoring generator max tokens
        default = _config.REFRACTORING_GENERATOR_MAX_TOKENS if max_tokens is None else max_tokens
        super().__init__(api_key, model=model, max_tokens=default)

    def run(self, user_query: str, use_refactoring_generator_prompt: bool = True, prompt_override: Optional[str] = None, max_tokens: Optional[int] = None):
        system_prompt = prompt_override if prompt_override is not None else (REFACTORING_GENERATOR_PROMPT if use_refactoring_generator_prompt else None)
        return self.send(system_prompt, user_query, max_tokens=max_tokens)



class PlannerAgent(BaseAgent):
    """Planner agent that analyzes a Java class and returns a JSON-like plan
    indicating which methods need refactoring and short improvement instructions.

    This agent follows the planner prompt pattern used in `RefAgent_main.py`.
    """

    def __init__(self, api_key: str, model: str = "gpt-4", max_tokens: Optional[int] = None):
        default = _config.PLANNER_MAX_TOKENS if max_tokens is None else max_tokens
        super().__init__(api_key, model=model, max_tokens=default)

    def analyze_methods(self, java_code: str, cko_metrics: str, max_tokens: Optional[int] = None) -> str:
        """Return the planner instruction JSON as produced by the LLM.

        Args:
            java_code: Full Java class source to analyze.
            cko_metrics: String representation of the class CKO metrics.
            max_tokens: Max tokens to request from the LLM.

        Returns:
            The raw string reply from the LLM (expected JSON-like). The caller
            can parse this string into a Python dict if desired.
        """
        system_prompt = PLANNER_PROMPT

        query = f"""
                For each method in the provided Java class :
                {java_code}

                Class CKO metrics :
                {cko_metrics}

                Provide your response in a json format as follow :
                {{
                Method1: (yes, improvement instruction),
                Method2: No,
                Method3: (yes, improvement instruction)
                }}

                Avoid using natural lanquage explanation
                """

        return self.send(system_prompt, query, max_tokens=max_tokens)


class CompilerAgent(BaseAgent):
    """Agent that compiles a Maven project and summarizes compilation errors using the LLM.

    Usage:
        compiler = CompilerAgent(api_key)
        is_compiled, summary = compiler.compile_and_summarize(project_directory, original_code)

    Returns:
        (is_compiled: bool, summary: str) - when compilation fails, `summary` contains the
        LLM-produced summary/suggestions; when compilation succeeds, `summary` is an empty string.
    """

    def __init__(self, api_key: str, model: str = "gpt-4", max_tokens: Optional[int] = None):
        default = _config.COMPILER_MAX_TOKENS if max_tokens is None else max_tokens
        super().__init__(api_key, model=model, max_tokens=default)

    def compile_and_summarize(self, project_dir: str, original_code: str, refactored_code: str, max_tokens: Optional[int] = None) -> tuple[bool, str]:
        """
        Compile the project using Maven.
        On success: return (True, "")
        On failure: generate LLM summary of errors and return (False, summary)
        """
        from refAgent.utilities import compile_project_with_maven  # Safe import

        process = compile_project_with_maven(project_dir=project_dir)

        if process.returncode == 0:
            return True, ""  # Compilation succeeded

        # Compilation failed → use local model to summarize errors
        user_query = f"""
Compilation failed:

STDOUT:
{process.stdout.strip()}

STDERR:
{process.stderr.strip()}

Original code:
{original_code}

Refactored code:
{refactored_code}

Summarize the main errors and suggest 3-5 concrete fixes.
"""

        summary = self.send(
            system_prompt=COMPILER_PROMPT,  # From prompt.py
            user_query=user_query,
            max_tokens=max_tokens or self.max_tokens
        )

        return False, summary.strip()
class TestAgent(BaseAgent):
    """Agent that runs Maven tests and summarizes failures using the LLM.

    Usage:
        tester = TestAgent(api_key)
        process, summary = tester.run_test_and_summarize(class_name, project_dir, original_code)

    Returns:
        (process: subprocess.CompletedProcess, summary: str) - when test fails, `summary` contains the
        LLM-produced JSON summary/suggestions; when test passes, `summary` is an empty string.
    """

    def __init__(self, api_key: str, model: str = "gpt-4", max_tokens: Optional[int] = None):
        default = _config.TEST_MAX_TOKENS if max_tokens is None else max_tokens
        super().__init__(api_key, model=model, max_tokens=default)

    def run_test_and_summarize(self, class_name: str, project_dir: str = '.', method_name: str = None, original_code: str = '',refactored_code:str = '', verify: bool = False, max_tokens: Optional[int] = None):
        """Run `mvn test` (optionally for a single class/method). If the test process fails, ask the LLM to summarize the failure.

        Returns:
            (process: CompletedProcess, summary: str)
        """
        process = run_maven_test(class_name, method_name=method_name, project_dir=project_dir, verify=verify)

        if process.returncode == 0:
            return process, ""

        # Build prompt and call LLM to summarize the test failure
        # Include both original and refactored code in the prompt when available to help diagnose regressions
        code_block = ""
        if original_code:
            code_block += f"Original Java code:\n{original_code}\n\n"
        if refactored_code:
            code_block += f"Refactored Java code:\n{refactored_code}\n\n"

        user_query = f"Test stderr:\n{process.stderr}\n\n{code_block}Respond in JSON as described."

        system_prompt = TEST_SUMMARY_PROMPT

        summary = self.send(system_prompt, user_query, max_tokens=max_tokens)
        return process, summary

    def combine_summaries(self, summaries: list, original_code: str = '', refactored_code: str = '', max_tokens: Optional[int] = None) -> str:
        """Combine multiple test failure summaries into one using the LLM.

        Args:
            summaries: List of strings (individual summaries or stderr snippets).
            original_code: Optional original Java source for context.
            refactored_code: Optional refactored Java source for context.

        Returns:
            A single LLM-produced summary string (JSON-like) combining the inputs.
        """
        system_prompt = MULTI_TEST_SUMMARY_PROMPT

        joined = "\n---\n".join([s for s in summaries if s])

        code_block = ""
        if original_code:
            code_block += f"Original Java code:\n{original_code}\n\n"
        if refactored_code:
            code_block += f"Refactored Java code:\n{refactored_code}\n\n"

        user_query = f"Multiple test failure reports:\n{joined}\n\n{code_block}Respond in JSON as described."

        combined = self.send(system_prompt, user_query, max_tokens=max_tokens)
        return combined
