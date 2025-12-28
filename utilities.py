import os
import re
import json
import shutil
import subprocess

def find_non_test_files(files):
    return [f for f in files if 'test' not in f.lower() and not f.endswith('Test.java')]

def extract_class_name(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                match = re.match(r'\s*(public\s+)?class\s+(\w+)', line.strip())
                if match:
                    return match.group(2)
    except Exception as e:
        print(f"Error extracting class name from {file_path}: {e}")
    return None

def copy_file(source_dir, dest_dir, filename):
    source_path = os.path.join(source_dir, filename)
    dest_path = os.path.join(dest_dir, filename)
    os.makedirs(dest_dir, exist_ok=True)
    shutil.copy(source_path, dest_path)

def write_to_java_file(file_path, java_code):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(java_code)

def read_json_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def export_dict_to_json(data, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def commit_file_to_github(repo_path, file_path, commit_message):
    try:
        os.chdir(repo_path)
        subprocess.run(['git', 'add', file_path], check=True)
        subprocess.run(['git', 'commit', '-m', commit_message], check=True)
        subprocess.run(['git', 'push'], check=True)
    except Exception as e:
        print(f"Git commit error: {e}")

def extract_ids(graph_dep):
    return [node['id'] for node in graph_dep['nodes'] if 'id' in node]

def find_test_files(files):
    return [f for f in files if 'test' in f.lower() or f.endswith('Test.java')]

def create_directory_if_not_exists(path):
    os.makedirs(path, exist_ok=True)

# Missing Maven functions required by agents.py
def compile_project_with_maven(project_dir: str = ".") -> subprocess.CompletedProcess:
    cmd = ["mvn", "clean", "install", "-DskipTests"]
    return subprocess.run(cmd, cwd=project_dir, capture_output=True, text=True)

def run_maven_test(class_name: str = None, method_name: str = None, project_dir: str = ".", verify: bool = False) -> subprocess.CompletedProcess:
    cmd = ["mvn"]
    if verify:
        cmd.extend(["clean", "verify"])
    else:
        cmd.append("test")
    
    if class_name:
        test_filter = class_name
        if method_name:
            test_filter += "#" + method_name
        cmd.extend(["-Dtest=" + test_filter])
    
    return subprocess.run(cmd, cwd=project_dir, capture_output=True, text=True)
