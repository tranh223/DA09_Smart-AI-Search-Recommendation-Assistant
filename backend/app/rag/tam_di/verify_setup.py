"""
System Verification Script
Kiểm tra xem hệ thống có cấu hình đúng không
"""

import sys
import os
from pathlib import Path

def check_env_file():
    """Kiểm tra file .env"""
    print("\n1. Checking .env file...")
    if Path(".env").exists():
        print("   ✓ .env file exists")
        with open(".env", "r") as f:
            content = f.read()
            if "OPENAI_API_KEY=" in content:
                if "OPENAI_API_KEY=sk-" in content or "OPENAI_API_KEY=sk_" in content:
                    print("   ✓ OPENAI_API_KEY is set")
                else:
                    print("   ⚠ OPENAI_API_KEY appears to be empty or invalid")
            else:
                print("   ✗ OPENAI_API_KEY not found in .env")
        return True
    else:
        print("   ✗ .env file not found")
        print("   → Run: cp .env.example .env")
        return False

def check_dependencies():
    """Kiểm tra dependencies"""
    print("\n2. Checking dependencies...")
    
    required_packages = {
        'openai': 'openai',
        'dotenv': 'python-dotenv',
        'pydantic_settings': 'pydantic',
        'langsmith': 'langsmith'
    }
    
    all_installed = True
    for import_name, package_name in required_packages.items():
        try:
            __import__(import_name)
            print(f"   ✓ {package_name} installed")
        except ImportError:
            print(f"   ✗ {package_name} not installed")
            print(f"   → Run: pip install {package_name}")
            all_installed = False
    
    return all_installed

def check_file_structure():
    """Kiểm tra cấu trúc file"""
    print("\n3. Checking file structure...")
    
    required_files = [
        "rag_system.py",
        "api.py",
        "config/settings.py",
        "modules/planner.py",
        "modules/short_term_memory.py",
        "modules/retrieval.py",
        "modules/total_info.py",
        "modules/generation.py",
        "tools/rag_tool.py",
        "tools/graph_tool.py",
        "tools/user_profile_tool.py",
        "tools/short_term_memory_tool.py",
        "utils/logger.py",
        "utils/llm_client.py",
        "utils/langsmith_tracer.py"
    ]
    
    all_exist = True
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"   ✓ {file_path}")
        else:
            print(f"   ✗ {file_path} missing")
            all_exist = False
    
    return all_exist

def check_imports():
    """Kiểm tra imports"""
    print("\n4. Checking imports...")
    
    try:
        from config.settings import settings
        print("   ✓ config.settings imported successfully")
        
        from utils.logger import get_logger
        print("   ✓ utils.logger imported successfully")
        
        from utils.llm_client import llm_client
        print("   ✓ utils.llm_client imported successfully")
        
        from modules.planner import plan
        print("   ✓ modules.planner imported successfully")
        
        from rag_system import RAGSystem
        print("   ✓ rag_system imported successfully")
        
        return True
    except Exception as e:
        print(f"   ✗ Import error: {str(e)}")
        return False

def check_configuration():
    """Kiểm tra configuration"""
    print("\n5. Checking configuration...")
    
    try:
        from config.settings import settings
        
        print(f"   • OPENAI_MODEL: {settings.OPENAI_MODEL}")
        print(f"   • LOG_LEVEL: {settings.LOG_LEVEL}")
        print(f"   • LANGSMITH_ENABLED: {settings.LANGSMITH_ENABLED}")
        print(f"   • CHUNK_SIZE: {settings.CHUNK_SIZE}")
        
        return True
    except Exception as e:
        print(f"   ✗ Configuration error: {str(e)}")
        return False

def test_llm_connection():
    """Test LLM connection"""
    print("\n6. Testing LLM connection...")
    
    try:
        from utils.llm_client import llm_client
        
        print("   Testing OpenAI API connection...")
        response = llm_client.call(
            [{"role": "user", "content": "Say 'Hello'"}],
            system_prompt="You are a helpful assistant. Respond with exactly one word."
        )
        
        if response:
            print(f"   ✓ LLM connection successful")
            print(f"   → Response: {response[:50]}...")
            return True
        else:
            print("   ✗ LLM returned empty response")
            return False
    
    except Exception as e:
        print(f"   ✗ LLM connection failed: {str(e)}")
        print("   → Check OPENAI_API_KEY in .env")
        return False

def run_full_verification():
    """Chạy full verification"""
    print("=" * 60)
    print("RAG System Verification Script")
    print("=" * 60)
    
    results = {
        ".env file": check_env_file(),
        "Dependencies": check_dependencies(),
        "File structure": check_file_structure(),
        "Imports": check_imports(),
        "Configuration": check_configuration(),
        "LLM connection": test_llm_connection()
    }
    
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    for check, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{check:.<40} {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All checks passed! System is ready to use.")
        print("\nTo start using the system:")
        print("  1. Simple: python -c \"from rag_system import RAGSystem; s = RAGSystem(); print(s.chat('Hello'))\"")
        print("  2. Interactive: python api.py")
        print("  3. Examples: python examples.py")
    else:
        print("✗ Some checks failed. Please fix the issues above.")
        print("\nFor help:")
        print("  1. Read README.md")
        print("  2. Read QUICK_START.py")
        print("  3. Check logs for more details")
    
    print("=" * 60 + "\n")
    
    return all_passed

if __name__ == "__main__":
    success = run_full_verification()
    sys.exit(0 if success else 1)
