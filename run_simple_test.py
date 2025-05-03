"""
Simple test runner that loads .env.test and runs pytest
"""
import os
import subprocess
from dotenv import load_dotenv

def main():
    # Load environment variables from .env.test
    print("Loading test environment variables...")
    load_dotenv(".env.test")
    
    # Run the tests
    print("Running tests...")
    subprocess.run(["pytest", "tests/", "--cov=app", "-v"])
    
    # Generate coverage report
    print("Generating coverage report...")
    subprocess.run(["pytest", "tests/", "--cov=app", "--cov-report=html"])
    
    print("Tests completed! Coverage report available in htmlcov/ directory")

if __name__ == "__main__":
    main()