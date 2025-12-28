#!/bin/bash

set -u  # Treat unset variables as errors
set -e  # Exit on any command failure

# === CHECK ARGUMENTS ===
if [ "$#" -ne 2 ]; then
    echo "❌ Usage: $0 <org/repo-name> <tag>"
    echo "Example: $0 apache/maven v3.8.6"
    exit 1
fi

ORG_REPO="$1"
TAG="$2"

ORG=$(echo "$ORG_REPO" | cut -d'/' -f1)
REPO=$(echo "$ORG_REPO" | cut -d'/' -f2)

REPO_URL="https://github.com/$ORG_REPO.git"
BEFORE_PATH="projects/before/$REPO"
AFTER_PATH="projects/after/$REPO"
ROOT_DIR="$(pwd)"
# === STEP 1: Clone specific tag only ===
if [ -d "$BEFORE_PATH" ]; then
    echo "📁 Project already exists at $BEFORE_PATH. Skipping clone."
else
    echo "📥 Cloning tag '$TAG' from $REPO_URL into $BEFORE_PATH..."
    mkdir -p "$(dirname "$BEFORE_PATH")"
    git clone --branch "$TAG" --depth 1 "$REPO_URL" "$BEFORE_PATH" || {
        echo "❌ Failed to clone tag '$TAG' from $REPO_URL"
        exit 1
    }
fi

# === STEP 2: Copy to 'after' directory ===
echo "📄 Copying project to $AFTER_PATH..."
rm -rf "$AFTER_PATH"
mkdir -p "$(dirname "$AFTER_PATH")"
cp -r "$BEFORE_PATH" "$AFTER_PATH"

# === STEP 3: Build using Maven ===
echo "🔧 Building project in $AFTER_PATH..."
cd "$AFTER_PATH"
if ! mvn clean install -DskipTests; then
    echo "❌ Maven build failed in $AFTER_PATH"
    exit 1
fi

echo "✅ Maven build succeeded!"

# === STEP 4: Run Python script with project name ===
repo_root="$ROOT_DIR"

cd "$repo_root" || exit 2
echo "🚀 Running Python script for project: $REPO... (repo root: $repo_root)"

# Support both possible locations for the Python entrypoint. Prefer a top-level
# RefAgent_main.py if present (historical), otherwise use refAgent/RefAgent_main.py.
if [ -f "$repo_root/refAgent/RefAgent_main.py" ]; then
    # Run the package as a module so imports like `import refAgent.*` resolve
    echo "Using module: refAgent.RefAgent_main"
    python3 -m refAgent.RefAgent_main "$REPO"
elif [ -f "$repo_root/RefAgent_main.py" ]; then
    # Fall back to running the top-level script directly (legacy layout)
    echo "Using script: $repo_root/RefAgent_main.py"
    python3 "$repo_root/RefAgent_main.py" "$REPO"
else
    echo "❌ Could not find RefAgent_main.py in expected locations:"
    echo "   $repo_root/RefAgent_main.py"
    echo "   $repo_root/refAgent/RefAgent_main.py"
    exit 1
fi
