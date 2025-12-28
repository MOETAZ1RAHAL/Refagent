from refAgent.java_metrics_calculator import JavaMetricsCalculator
# Dependency graph removed due to javalang incompatibility with modern Java
# from refAgent.dependency_graph import JavaClassDependencyAnalyzer, draw_dependency_graph
from refAgent.utilities import *
from settings import Settings
import argparse
from refAgent.agents import PlannerAgent, RefactoringGeneratorAgent, CompilerAgent, TestAgent
import subprocess
import os
import re

# === Parse project name argument ===
parser = argparse.ArgumentParser(description="Refactor Java Project")
parser.add_argument("project_name", type=str, help="Name of the project folder (e.g. gson)")
args = parser.parse_args()
project_name = args.project_name

config = Settings()

if __name__ == "__main__":
    # Prepare needed folders
    results = {}
    os.makedirs(f"results/{project_name}", exist_ok=True)
    os.makedirs(f"data/paths/{project_name}", exist_ok=True)
    os.makedirs("data/pmd", exist_ok=True)

    # PMD Integration: Run PMD to detect god classes first
    pmd_bin_path = os.path.expanduser("~/pmd-bin-7.19.0/bin/pmd")
    project_directory = os.path.expanduser(f"~/projects/before/{project_name}")
    pmd_output_file = f"data/pmd/{project_name}_god_classes.txt"

    pmd_command = [
        pmd_bin_path,
        "check",
        "-d", project_directory,
        "-R", "category/java/design.xml/GodClass",
        "-f", "text"
    ]

    print(f"Running PMD on {project_directory} to detect god classes...")
    with open(pmd_output_file, "w") as output:
        result = subprocess.run(pmd_command, stdout=output, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            print("PMD warning/error:", result.stderr)

    print(f"PMD output saved to {pmd_output_file}")

    # Parse PMD output to extract unique god class file paths
    god_class_files = set()
    with open(pmd_output_file, "r") as f:
        for line in f:
            match = re.match(r"^(.*?):\d+:\s*GodClass:", line)
            if match:
                file_path = match.group(1)
                god_class_files.add(file_path)

    god_class_files = find_non_test_files(list(god_class_files))

    if not god_class_files:
        print(f"No god classes detected in {project_name}. Skipping refactoring.")
    else:
        print(f"Detected {len(god_class_files)} god classes. Proceeding with RefAgent...")

    # Process only god classes
    for file in god_class_files:
        try:
            target_class = extract_class_name(file)
            class_directory = os.path.dirname(file)

            if target_class is None:
                print(f"Could not extract class name from {file}. Skipping.")
                continue

            os.makedirs(f"results/{project_name}/{target_class}", exist_ok=True)

            # === Metrics: Before refactoring ===
            input_path = "code_smells/project/before"
            output_path = "./code_smells/tmp/before"
            designite_jar = "./code_smells/DesigniteJava.jar"

            os.makedirs(input_path, exist_ok=True)
            os.makedirs(output_path, exist_ok=True)

            copy_file(class_directory, input_path, target_class + ".java")

            before_calculator = JavaMetricsCalculator(input_path, output_path, designite_jar)
            before_calculator.parse_java_code(file)
            before_metrics = before_calculator.compute_metrics_for_class()
            before_calculator.clean_repository()

            Before_java_code = before_calculator.java_code
            results["CKO metrics"] = before_metrics

            path_to_java_file = file
            path_to_java_file_after = path_to_java_file.replace("before", "after")

            # === Agents (local model only) ===
            api_key = config.API_KEY  # "unused" for Ollama
            planner = PlannerAgent(api_key, model=config.MODEL_NAME)
            refactoring_generator = RefactoringGeneratorAgent(api_key, model=config.MODEL_NAME)
            compiler = CompilerAgent(api_key, model=config.MODEL_NAME)
            test_agent = TestAgent(api_key, model=config.MODEL_NAME)

            # Planner: Generate improvement instructions
            Instruction = planner.analyze_methods(before_calculator.java_code, before_calculator.as_string())
            results["Instruction"] = Instruction

            # Decide if refactoring is needed
            decision_query = f"""
            From this set of instructions, does at least one method need improvement?
            Instruction: {Instruction}
            Answer only True or False.
            """
            do_refactor = planner.send(None, decision_query)
            if 'true' not in do_refactor.lower():
                print(f"No refactoring needed for {target_class}")
                write_to_java_file(file_path=path_to_java_file_after, java_code=Before_java_code)
                continue

            # === Iterative Refactoring Loop (max 20) ===
            project_dir_after = os.path.expanduser(f"~/projects/after/{project_name}")

            for i in range(20):
                print(f"--- Refactoring iteration {i+1}/20 for {target_class} ---")

                query = f"""
                Instructions: {Instruction}
                CKO Metrics: {before_metrics}
                Improve the following Java class while preserving behavior, syntax, semantics, comments, and annotations.
                Do not alter external method behavior.
                Return only the full improved Java class in a code block.

                Original code:
                {Before_java_code}
                """

                improvement = refactoring_generator.run(query, use_refactoring_generator_prompt=True)

                # Save improved version
                write_to_java_file(file_path=path_to_java_file_after, java_code=improvement)
                write_to_java_file(file_path=f"results/{project_name}/{target_class}/original_java_code.java", java_code=Before_java_code)
                write_to_java_file(file_path=f"results/{project_name}/{target_class}/improved_java_code_iter{i+1}.java", java_code=improvement)

                # === Compile ===
                print("Compiling improved code...")
                is_compiled, compile_summary = compiler.compile_and_summarize(project_dir_after, Before_java_code, improvement)

                if not is_compiled:
                    print("Compilation failed. Feeding back to model...")
                    try:
                        refactoring_generator.llm.message_history.append({"role": "user", "content": f"Compilation errors:\n{compile_summary}"})
                    except:
                        pass
                    print("LLM compilation summary:")
                    print(compile_summary)
                    continue  # Next iteration

                # === Test (full suite, since graph skipped) ===
                print("Running full test suite...")
                process = run_maven_test(project_dir=project_dir_after)

                if process.returncode != 0:
                    test_summary = process.stderr.strip() or "Tests failed."
                    print("Tests failed. Feeding back to model...")
                    try:
                        refactoring_generator.llm.message_history.append({"role": "user", "content": f"Test failures:\n{test_summary}"})
                    except:
                        pass
                    print("Test failure output:")
                    print(test_summary)
                    results["Compilation"] = True
                    results["Test passed"] = False
                    results["is improved"] = False
                    continue

                print("Compilation and tests PASSED!")

                # === After metrics ===
                after_input = "code_smells/project/after"
                after_output = "./code_smells/tmp/after"
                os.makedirs(after_input, exist_ok=True)
                os.makedirs(after_output, exist_ok=True)

                write_to_java_file(file_path=f"{after_input}/{target_class}.java", java_code=improvement)
                after_calculator = JavaMetricsCalculator(after_input, after_output, designite_jar)
                after_calculator.parse_java_code(path_to_java_file_after)
                after_metrics = after_calculator.compute_metrics_for_class()
                after_calculator.clean_repository()

                # === Improvement check via LLM ===
                improvement_query = f"""
                Compare these two versions and their CKO metrics.
                Has code quality, readability, maintainability improved?

                Before:
                {Before_java_code}
                Metrics: {before_metrics}

                After:
                {improvement}
                Metrics: {after_metrics}

                Answer only True or False.
                """
                is_better = planner.send(None, improvement_query)
                if 'true' in str(is_better).lower():
                    print(f"Successful improvement for {target_class}!")
                    results["Compilation"] = True
                    results["Test passed"] = True
                    results["is improved"] = True
                    results["CKO metrics After"] = after_metrics
                    break
                else:
                    print("No improvement detected. Continuing...")
                    results["is improved"] = False

            else:
                print(f"Max iterations reached for {target_class} without success.")

            # Restore original if no success
            if results.get("is improved") != True:
                write_to_java_file(file_path=path_to_java_file_after, java_code=Before_java_code)

            # Save final results
            export_dict_to_json(results, f"results/{project_name}/{target_class}/metrics.json")

        except Exception as e:
            print(f"Error processing {file}: {e}")
            continue

    print("Refactoring pipeline completed.")