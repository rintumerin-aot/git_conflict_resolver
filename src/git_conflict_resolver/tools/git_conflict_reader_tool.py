from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, List
from pathlib import Path
import json

class ReadConflictedFileInput(BaseModel):
    file_path: str = Field(..., description="Path to the file to check and extract Git merge conflict markers")

class ReadConflictedFileTool(BaseTool):
    name: str = "Read Conflicted File"
    description: str = (
        "Extracts structured conflict blocks from a file containing Git merge conflict markers "
        "(e.g. <<<<<<<, =======, >>>>>>>), including line numbers and content. "
        "Returns data in a format suitable for LLM-based conflict resolution."
    )
    args_schema: Type[BaseModel] = ReadConflictedFileInput

    def _run(self, file_path: str) -> str:
        path = Path(file_path)

        if not path.exists() or not path.is_file():
            return json.dumps({"error": f"File not found or is not a file: {file_path}"})

        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except Exception as e:
            return json.dumps({"error": f"Failed to read file: {str(e)}"})

        conflicts = []
        in_conflict = False
        start_line = 0
        buffer = []

        for i, line in enumerate(lines, start=1):
            if line.startswith("<<<<<<<"):
                in_conflict = True
                start_line = i
                buffer = [line]
            elif in_conflict:
                buffer.append(line)
                if line.startswith(">>>>>>>"):
                    conflicts.append({
                        "start_line": start_line,
                        "end_line": i,
                        "conflicted_content": "\n".join(buffer)
                    })
                    in_conflict = False
                    buffer = []

        result = {
            "file_path": file_path,
            "conflicts": conflicts
        }

        return json.dumps(result, indent=2)
