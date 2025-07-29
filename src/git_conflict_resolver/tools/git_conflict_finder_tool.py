from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, List
import os
from .logger import logger


class GitConflictFinderInput(BaseModel):
    log_file_path: str = Field(..., description="Path to the cherry-pick conflict log or list of file paths.")


class GitConflictFinderTool(BaseTool):
    name: str = "Git Conflict Finder"
    description: str = (
        "Parses Git conflict logs or file lists and finds unresolved Git conflict markers (e.g. <<<<<<<) in the actual files."
    )
    args_schema: Type[BaseModel] = GitConflictFinderInput

    def _run(self, log_file_path: str) -> str:
        base_path = os.environ.get("GIT_BASE_PATH", "").strip()
        if not base_path:
            logger.error(" GIT_BASE_PATH is not set in the environment.")
            return "GIT_BASE_PATH is not set in the environment."

        file_paths = self._extract_paths_with_base(log_file_path, base_path)
        logger.info(f" Extracted {len(file_paths)} valid paths from: {log_file_path}")

        conflicts = self._scan_for_conflict_markers(file_paths)

        if not conflicts:
            logger.info(" No merge markers found.")
            return "✅ No merge markers found in the extracted files."

        logger.warning(f" Found conflicts in {len(conflicts)} files.")
        for path in conflicts:
            logger.warning(f" - {path}")

        return f" Found conflicts in {len(conflicts)} files:\n" + "\n".join(conflicts)

    def _extract_paths_with_base(self, input_path: str, base_path: str) -> List[str]:
        if not os.path.exists(input_path):
            logger.error(f" Provided file does not exist: {input_path}")
            return []

        paths = []
        with open(input_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                path = ""
                if line.startswith("- "):
                    path = line.lstrip("- ").strip()
                elif "Merge conflict in" in line:
                    path = line.split("Merge conflict in")[-1].strip()

                full_path = path if os.path.isabs(path) else os.path.normpath(os.path.join(base_path, path))

                if os.path.isfile(full_path):
                    paths.append(full_path)
                else:
                    logger.warning(f" Skipped: {full_path} (not a valid file)")

        return paths

    def _scan_for_conflict_markers(self, file_paths: List[str]) -> List[str]:
        conflicted = []
        for file_path in file_paths:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if all(marker in content for marker in ['<<<<<<<', '=======', '>>>>>>>']):
                        conflicted.append(file_path)
            except Exception as e:
                logger.error(f" Error reading {file_path}: {e}")
        return conflicted
