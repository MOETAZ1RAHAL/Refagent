from refAgent.java_metrics_calculator import JavaMetricsCalculator
from refAgent.dependency_graph import JavaClassDependencyAnalyzer, draw_dependency_graph
from utilities import *
from settings import Settings
import argparse
from refAgent.agents import PlannerAgent, RefactoringGeneratorAgent, CompilerAgent, TestAgent
import subprocess
import os
import re

# === Parse project name argument ===
parser = argparse.ArgumentParser(description="Refactor Java Project")
parser.add_argument("project_name", type=str, help="Name of the project folder (e.g. flow)")
args = parser.parse_args()

project_name = args.project_name

config = Settings()

# Example usage
if __name__ == "__main__":

    # Prepare needed folders
    results = {}
    os.makedirs(f"results/{project_name}", exist_ok=True)
    os.makedirs(f"data/paths/{project_name}", exist_ok=True)

    # PMD Integration: Run PMD to detect god classes first
    pmd_bin_path = os.path.expanduser("~/pmd-bin-7.19.0/bin/pmd")  # Path to PMD CLI
    project_directory = f"/home/moetaz/projects/before/{project_name}"  # Full path to project
    pmd_output_file = f"data/pmd/{project_name}_god_classes.txt"  # Output file for PMD results
    os.makedirs(os.path.dirname(pmd_output_file), exist_ok=True)

    # Run PMD command for GodClass rule
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
            print("PMD error:", result.stderr)
    print(f"PMD output saved to {pmd_output_file}")

    # Parse PMD output to extract unique god class file paths
    god_class_files = set()
    with open(pmd_output_file, "r") as f:
        for line in f:
            # Example line: /path/to/Class.java:1: GodClass: Description
            match = re.match(r"^(.*?):\d+:\s*GodClass:", line)
            if match:
                file_path = match.group(1)
                god_class_files.add(file_path)

    # Filter to non-test files (as before)
    god_class_files = find_non_test_files(list(god_class_files))

    # If no god classes detected, skip or log
    if not god_class_files:
        print(f"No god classes detected in {project_name}. Skipping refactoring.")
    else:
        print(f"Detected {len(god_class_files)} god classes. Proceeding with RefAgent...")

    # Now use god_class_files instead of all files
    for file in god_class_files:
        try:
            target_class = extract_class_name(file)
            class_directory = os.path.dirname(file)

            if target_class is None:
                continue
            os.makedirs(f"results/{project_name}/{target_class}", exist_ok=True)

            graph_path = f"data/graphs/{project_name}/{target_class}_dependency_graph.json"
            
            #analyzer = JavaClassDependencyAnalyzer(target_class)
            #analyzer.analyze_project(project_directory)
            #analyzer.export_to_json(graph_path)
            #draw_dependency_graph(analyzer.dependencies, filename=f"data/graphs/{project_name}/{target_class}_dependency_graph.png")
            
            # 1. For a single file
            input_path = "code_smells/project/before"  # Path to the Java code directory
            output_path = "./code_smells/tmp/before"   # Path to store metrics
            designite_jar = "./code_smells/DesigniteJava.jar"  # Path to DesigniteJava.jar

            copy_file(class_directory, input_path, target_class+".java")

            before_calculator = JavaMetricsCalculator(input_path, output_path, designite_jar)
            before_calculator.parse_java_code(file)
            before_metrics = before_calculator.compute_metrics_for_class()
            before_calculator.clean_repository()

            path_to_java_file = file
            path_to_java_file_after = path_to_java_file.replace("before","after")

            Before_java_code = before_calculator.java_code

            #Export the CKO metrics of the original class to results folder
            results["CKO metrics"] = before_metrics

            # Example usage with agents:
            api_key = config.API_KEY
            planner = PlannerAgent(api_key, model=config.MODEL_NAME)
            refactoring_generator = RefactoringGeneratorAgent(api_key, model=config.MODEL_NAME)
            compiler = CompilerAgent(api_key, model=config.MODEL_NAME)
            test_agent = TestAgent(api_key, model=config.MODEL_NAME)

            # Build instruction query via PlannerAgent
            Instruction = planner.analyze_methods(before_calculator.java_code, before_calculator.as_string())
            results["Instruction"] = Instruction

            # Decision Node: ask planner to decide if any method needs improvement
            query_decisition = f"""
                            Output: True or false

                            From this set of instruction to improve all these methods does at least one method need improvement:

                            Instruction: {Instruction}

                            Don't return any natural language explanation
                            """
            do_instrect = planner.send(None, query_decisition)

            if 'true' in do_instrect.lower():
                for i in range(20):
                    query = f"""
                                Following the instruction Instructions:{Instruction}  and CKO metrics {before_metrics} and dependent classes, improve the provided java code {Before_java_code} and improve the
                                CKO metrics. You can assume that the given class and methods are functionally correct. Ensure that you do not
                                Alter the behaviour of the external method while maintaining the behaviour of the method, maintaining both syntactic
                                and semantic correctness. Don't remove any comments or annotations.
                                Provide the java class within code block. Avoid using natural language explanations
                                """
                    # RefactoringGeneratorAgent.run will use REFACTORING_GENERATOR_MAX_TOKENS as the system prompt and strip fences
                    improvement = refactoring_generator.run(query, use_refactoring_generator_prompt=True)

                    print(f"------------ Start making the improvement to compile and test Iteration {i}-----------------")
                    print(f"=============================================================================================")

                    write_to_java_file(file_path=path_to_java_file_after, java_code=improvement)

                    #Write the improved code in the results file
                    write_to_java_file(file_path=f"results/{project_name}/{target_class}/original_java_code.java", java_code=Before_java_code)
                    write_to_java_file(file_path=f"results/{project_name}/{target_class}/improved_java_code.java", java_code=improvement)


                    print("-------------------- Compile the improved code ---------------------------------------")

                    project_directory = f"/home/moetaz/projects/after/{project_name}"
                    # Use CompilerAgent to compile and (on failure) generate an LLM summary of the error.
                    is_compiled, compile_summary = compiler.compile_and_summarize(project_directory, Before_java_code, improvement)
                    if not is_compiled:
                        results["Compilation"] = False
                        results["Test passed"] = False
                        results["is improved"] = False
                        # Restore original code on failed compilation
                        write_to_java_file(file_path=path_to_java_file_after, java_code=Before_java_code)
                        # Add the compiler LLM summary to the refactoring_generator's message history for context (in-memory only).
                        try:
                            refactoring_generator.llm.message_history.append({"role": "user", "content": compile_summary})
                        except Exception:
                            pass
                        # Print the summary for the user, but do not persist it to disk.
                        print("Compilation summary (LLM):")
                        print(compile_summary)
                        continue

                    print("------------ Test the improved code ---------------------------------------")
                    graph_dep = read_json_file(graph_path)
                    files = extract_ids(graph_dep)
                    tests = find_test_files(files)

                    # Collect per-test summaries and produce one combined summary at the end
                    test_summaries = []
                    for test in tests:
                        if test != "TestCase":
                            rcode, test_summary = test_agent.run_test_and_summarize(
                                test,
                                project_dir=project_directory,
                                verify=False,
                                original_code=Before_java_code,
                                refactored_code=improvement,
                            )
                            if rcode.returncode != 0:
                                # collect the LLM summary when available, otherwise raw stderr
                                test_summaries.append(test_summary or rcode.stderr)
                                # continue checking other tests to aggregate all failures
                                continue

                    # If any tests failed, synthesize one summary for all failures and skip commit/metrics
                    if test_summaries:
                        combined_summary = test_agent.combine_summaries(test_summaries, original_code=Before_java_code, refactored_code=improvement)
                        results["Compilation"] = True
                        results["Test passed"] = False
                        results["is improved"] = False
                        # keep combined summary in-memory for context
                        try:
                            refactoring_generator.llm.message_history.append({"role": "user", "content": combined_summary})
                        except Exception:
                            pass
                        # Print the combined summary for visibility
                        print("Combined test failure summary (LLM):")
                        print(combined_summary)
                        continue
                    print("------------- Commit the code changes to github-------------------")

                    repo_path = f'/home/moetaz/projects/after/{project_name}'
                    file_path = file.replace(f"/home/moetaz/projects/before/{project_name}/", "")

                    commit_message = f'Refactored {file_path}'
                    commit_file_to_github(repo_path, file_path, commit_message)   

                    #Compute CKO metrics
                    # 1. For a single file
                    input_path = "code_smells/project/after"  # Path to the Java code directory
                    output_path = "./code_smells/tmp/after"   # Path to store metrics

                    write_to_java_file(file_path=input_path+"/"+target_class+".java", java_code=improvement)


                    after_calculator = JavaMetricsCalculator(input_path, output_path, designite_jar)
                    after_calculator.parse_java_code(file)
                    after_metrics = after_calculator.compute_metrics_for_class()
                    after_calculator.clean_repository()

                    # Check there was an improvement
                    query = """
                            Given the Java code before and after the proposed changes, along with their corresponding CKO metrics, 
                            assess whether the code has improved. Analyze both versions of the code and compare the CKO metrics.
                            Determine if the changes resulted in better code quality, readability, maintainability, and performance.
                            Java code before improvement :{}
                            CKO metrics before improvement : {}
                            
                            Java code after Improvement: {}
                            CKO metrics after Improvement: {}

                            Return True or False.
                            Avoid using natural language explanation
                            """.format(Before_java_code, before_metrics, improvement, after_metrics)
                    
                    is_improvement_resp = planner.send(None, query)
                    try:
                        is_improvement = str(is_improvement_resp).strip().lower() in ("true", "yes", "1")
                    except Exception:
                        is_improvement = False

                    if not is_improvement:
                        results["Compilation"] = True
                        results["Test passed"] = True
                        results["is improved"] = False
                        continue
                            
                    results["Compilation"] = True
                    results["Test passed"] = True
                    results["is improved"] = True
                    results["CKO metrics After"] = after_metrics

                    break
                
                write_to_java_file(file_path=path_to_java_file_after, java_code=Before_java_code)
                export_dict_to_json(results, f"results/{project_name}/{target_class}/metrics")
        except Exception as e:
            print(f"Error processing {file}: {e}")
            continue
