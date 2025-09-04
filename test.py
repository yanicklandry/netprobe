#!/usr/bin/env pipenv run python
"""
Main test runner for NetProbe project.
Runs all tests in the test/ directory.
"""

import sys
import os
import pytest

def main():
    """Run all tests with proper configuration."""
    
    # Add the project root to Python path so tests can import modules
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)
    
    # Configure pytest arguments
    test_args = [
        'test/',  # Test directory
        '-v',     # Verbose output
        '--tb=short',  # Short traceback format
        '--color=yes',  # Colored output
        '-x',     # Stop on first failure
        '--durations=10'  # Show slowest 10 tests
    ]
    
    # Add coverage if pytest-cov is available
    try:
        import pytest_cov
        test_args.extend([
            '--cov=netprobe',
            '--cov=vpn_manager', 
            '--cov-report=term-missing',
            '--cov-report=html:test/coverage'
        ])
        print("📊 Running tests with coverage analysis...")
    except ImportError:
        print("📋 Running tests (install pytest-cov for coverage analysis)...")
    
    print("🧪 NetProbe Test Suite")
    print("=" * 50)
    
    # Run the tests
    exit_code = pytest.main(test_args)
    
    if exit_code == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ Tests failed (exit code: {exit_code})")
    
    return exit_code

if __name__ == '__main__':
    sys.exit(main())