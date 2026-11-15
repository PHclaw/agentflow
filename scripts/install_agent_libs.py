"""
安装 agent-* 库生态

从 GitHub 安装 PHclaw 的 agent 库
"""
import subprocess
import sys

AGENT_LIBS = [
    "agent-config-loader",
    "agent-prompt-templates",
    "agent-output-parser",
    "agent-tool-registry",
    "agent-memory-store",
    "agent-observability",
    "agent-orchestrator",
    "agent-mcp-client",
]

def install_from_github():
    """从 GitHub 安装 agent 库"""
    for lib in AGENT_LIBS:
        url = f"git+https://github.com/PHclaw/{lib}.git"
        print(f"Installing {lib}...")
        
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", url],
                check=True
            )
            print(f"  ✓ {lib} installed")
        except subprocess.CalledProcessError as e:
            print(f"  ✗ {lib} failed: {e}")

def check_installed():
    """检查已安装的库"""
    print("\nInstalled agent libraries:")
    for lib in AGENT_LIBS:
        try:
            __import__(lib.replace("-", "_"))
            print(f"  ✓ {lib}")
        except ImportError:
            print(f"  ✗ {lib} (not installed)")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Check installed libraries")
    args = parser.parse_args()
    
    if args.check:
        check_installed()
    else:
        install_from_github()
        print("\n")
        check_installed()
