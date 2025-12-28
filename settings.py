import os

class Settings:
    API_KEY = "unused"  # Dummy for local Ollama
    MODEL_NAME = "starcoder2:3b"
    DEFAULT_MAX_TOKENS = 4096
    PLANNER_MAX_TOKENS = 4096
    REFRACTORING_GENERATOR_MAX_TOKENS = 4096
    COMPILER_MAX_TOKENS = 2048
    TEST_MAX_TOKENS = 2048
    GITHUB_API_KEY = []  # Empty list or add your tokens if using github_api.py