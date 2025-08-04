from crewai_tools import tool
from pathlib import Path

@tool("read_conflicted_file")
def read_conflicted_file(file_path: str) -> str:
    """
    Checks if a file contains Git merge conflict markers (e.g. <<<<<<<, =======, >>>>>>>)
    and returns a status message.
    """
    path = Path(file_path)

    if not path.exists() or not path.is_file():
        return f"❌ Error: File not found or is not a file -> {file_path}"

    try:
        content = path.read_text(encoding='utf-8')
    except Exception as e:
        return f"❌ Failed to read file '{file_path}': {str(e)}"

    has_conflicts = all(marker in content for marker in ["<<<<<<<", "=======", ">>>>>>>"])

    if has_conflicts:
        return f"⚠️ Merge conflict markers found in file: {file_path}"
    else:
        return f"✅ No merge conflicts found in file: {file_path}"
