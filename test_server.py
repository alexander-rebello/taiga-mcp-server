#!/usr/bin/env python3
"""
Test suite for Taiga MCP Server

Tests the structure and logic of the server without requiring
actual external dependencies (MCP and python-taiga libraries).
"""

import ast
import inspect
import os
import sys


def test_file_exists():
    """Test that all required files exist"""
    print("Testing file existence...")
    required_files = [
        "taiga_mcp_server.py",
        "__init__.py",
        "__main__.py",
        "pyproject.toml",
        "requirements.txt",
        "README.md",
        "QUICKSTART.md",
        "CREDENTIALS.md",
        ".env.example",
        ".gitignore",
    ]

    for filename in required_files:
        filepath = os.path.join("/home/rebelloa/mcp-taiga", filename)
        if os.path.exists(filepath):
            print(f"  ✓ {filename}")
        else:
            print(f"  ✗ {filename} - MISSING")
            return False

    return True


def test_python_syntax():
    """Test Python file syntax"""
    print("\nTesting Python syntax...")
    python_files = [
        "taiga_mcp_server.py",
        "__init__.py",
        "__main__.py",
    ]

    for filename in python_files:
        filepath = os.path.join("/home/rebelloa/mcp-taiga", filename)
        try:
            with open(filepath, "r") as f:
                ast.parse(f.read())
            print(f"  ✓ {filename}")
        except SyntaxError as e:
            print(f"  ✗ {filename} - Syntax Error: {e}")
            return False

    return True


def test_taiga_mcp_server_structure():
    """Test TaigaMCPServer class structure"""
    print("\nTesting TaigaMCPServer class structure...")

    filepath = "/home/rebelloa/mcp-taiga/taiga_mcp_server.py"
    with open(filepath, "r") as f:
        content = f.read()

    # Parse the AST
    tree = ast.parse(content)

    # Find the TaigaMCPServer class
    class_found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "TaigaMCPServer":
            class_found = True

            # Expected methods
            expected_methods = [
                "__init__",
                "initialize_api",
                "setup_handlers",
                "handle_get_current_project",
                "handle_get_project_backlog",
                "_format_project",
                "run",
            ]

            # Get both regular and async functions
            method_names = [
                m.name
                for m in node.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]

            for method in expected_methods:
                if method in method_names:
                    print(f"  ✓ Method: {method}")
                else:
                    print(f"  ✗ Method: {method} - MISSING")
                    return False
            break

    if not class_found:
        print("  ✗ TaigaMCPServer class not found")
        return False

    return True


def test_environment_variables():
    """Test environment variable handling"""
    print("\nTesting environment variable handling...")

    filepath = "/home/rebelloa/mcp-taiga/taiga_mcp_server.py"
    with open(filepath, "r") as f:
        content = f.read()

    required_env_vars = [
        "TAIGA_HOST",
        "TAIGA_USERNAME",
        "TAIGA_PASSWORD",
        "TAIGA_TOKEN",
    ]

    for env_var in required_env_vars:
        if f'os.getenv("{env_var}"' in content:
            print(f"  ✓ Environment variable: {env_var}")
        else:
            print(f"  ✗ Environment variable: {env_var} - NOT FOUND")
            return False

    return True


def test_tool_definitions():
    """Test that tools are properly defined"""
    print("\nTesting tool definitions...")

    filepath = "/home/rebelloa/mcp-taiga/taiga_mcp_server.py"
    with open(filepath, "r") as f:
        content = f.read()

    required_tools = [
        "get_current_project",
        "get_project_backlog",
    ]

    for tool in required_tools:
        if f'name="{tool}"' in content:
            print(f"  ✓ Tool defined: {tool}")
        else:
            print(f"  ✗ Tool defined: {tool} - NOT FOUND")
            return False

    return True


def test_error_handling():
    """Test error handling patterns"""
    print("\nTesting error handling...")

    filepath = "/home/rebelloa/mcp-taiga/taiga_mcp_server.py"
    with open(filepath, "r") as f:
        content = f.read()

    error_patterns = [
        ("TaigaRestException", "Taiga API exception handling"),
        ("try:", "try-except blocks"),
        ("logger.error", "error logging"),
    ]

    for pattern, description in error_patterns:
        if pattern in content:
            print(f"  ✓ {description}")
        else:
            print(f"  ✗ {description} - NOT FOUND")
            return False

    return True


def test_documentation():
    """Test that documentation files are present and contain content"""
    print("\nTesting documentation...")

    doc_files = {
        "README.md": ["Installation", "Features", "Configuration"],
        "QUICKSTART.md": ["Installation", "Test"],
        "CREDENTIALS.md": ["authentication", "Taiga"],
    }

    for filename, keywords in doc_files.items():
        filepath = os.path.join("/home/rebelloa/mcp-taiga", filename)
        try:
            with open(filepath, "r") as f:
                content = f.read()

            # Check if file has reasonable content
            if len(content) > 100:
                print(f"  ✓ {filename} ({len(content)} bytes)")
            else:
                print(f"  ⚠ {filename} - Very small ({len(content)} bytes)")
        except Exception as e:
            print(f"  ✗ {filename} - Error: {e}")
            return False

    return True


def test_entry_point():
    """Test entry points"""
    print("\nTesting entry points...")

    # Check __main__.py
    main_file = "/home/rebelloa/mcp-taiga/__main__.py"
    with open(main_file, "r") as f:
        main_content = f.read()

    if "from taiga_mcp_server import main" in main_content and "main()" in main_content:
        print("  ✓ __main__.py entry point")
    else:
        print("  ✗ __main__.py entry point - malformed")
        return False

    # Check pyproject.toml
    proj_file = "/home/rebelloa/mcp-taiga/pyproject.toml"
    with open(proj_file, "r") as f:
        proj_content = f.read()

    if 'taiga-mcp-server = "taiga_mcp_server:main"' in proj_content:
        print("  ✓ pyproject.toml entry point")
    else:
        print("  ✗ pyproject.toml entry point - malformed")
        return False

    return True


def test_requirements():
    """Test requirements are properly specified"""
    print("\nTesting requirements...")

    # Check requirements.txt
    req_file = "/home/rebelloa/mcp-taiga/requirements.txt"
    with open(req_file, "r") as f:
        req_content = f.read()

    required_packages = ["mcp", "python-taiga"]

    for package in required_packages:
        if package in req_content:
            print(f"  ✓ {package} in requirements.txt")
        else:
            print(f"  ✗ {package} - NOT found in requirements.txt")
            return False

    # Check pyproject.toml dependencies
    proj_file = "/home/rebelloa/mcp-taiga/pyproject.toml"
    with open(proj_file, "r") as f:
        proj_content = f.read()

    for package in required_packages:
        if package.replace("-", "_") in proj_content or package in proj_content:
            print(f"  ✓ {package} in pyproject.toml")
        else:
            print(f"  ✗ {package} - NOT found in pyproject.toml")
            return False

    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("Taiga MCP Server - Test Suite")
    print("=" * 60)

    tests = [
        test_file_exists,
        test_python_syntax,
        test_taiga_mcp_server_structure,
        test_environment_variables,
        test_tool_definitions,
        test_error_handling,
        test_documentation,
        test_entry_point,
        test_requirements,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append((test.__name__, result))
        except Exception as e:
            print(f"\n✗ Test {test.__name__} failed with exception: {e}")
            results.append((test.__name__, False))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
    sys.exit(main())
    sys.exit(main())
    sys.exit(main())
