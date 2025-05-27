from pathlib import Path
from memory_manager import get_known_contexts

def main():
    contexts = get_known_contexts()
    print("✅ Known memory contexts:")
    for ctx in contexts:
        print(" -", ctx)

if __name__ == "__main__":
    main()
