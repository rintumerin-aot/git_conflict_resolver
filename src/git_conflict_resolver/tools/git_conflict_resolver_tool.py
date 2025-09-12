from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, List, Dict, Any
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

class FixMergeConflictsInput(BaseModel):
    file_path: str = Field(..., description="The path to the conflicted file.")
    resolved_blocks: List[Dict[str, Any]] = Field(
        ..., description="List of resolved conflict blocks with 'start_line', 'end_line', and 'resolved_content'"
    )

class FixMergeConflictsTool(BaseTool):
    name: str = "Fix Merge Conflicts in File"
    description: str = (
        "Applies resolved conflict blocks into the specified lines of the file, "
        "preserving all other content exactly as-is, including WEBBAR tags."
    )
    args_schema: Type[BaseModel] = FixMergeConflictsInput

    def _run(self, file_path: str, resolved_blocks: List[Dict[str, Any]]) -> str:
        path = Path(file_path)

        if not path.exists():
            return f"File does not exist: {file_path}"

        try:
            file_lines = path.read_text(encoding='utf-8').splitlines()
        except Exception as e:
            return f"Failed to read file '{file_path}': {str(e)}"

        try:
            backup_path = path.with_suffix(path.suffix + '.backup')
            backup_path.write_text('\n'.join(file_lines) + '\n', encoding='utf-8')
            
            for conflict in sorted(resolved_blocks, key=lambda c: c["start_line"], reverse=True):
                start = conflict["start_line"] - 1
                end = conflict["end_line"]

                original_conflict_lines = file_lines[start:end]
                original_conflict_content = '\n'.join(original_conflict_lines)
                
                conflict_info = self._parse_conflict_block(original_conflict_content)
                
                if conflict_info:
                    intelligent_resolution = self._apply_intelligent_resolution(
                        conflict_info, 
                        conflict.get("resolved_content", ""),
                        file_path
                    )
                    resolved_lines = intelligent_resolution.splitlines()
                else:
                    logging.warning("Conflict block could not be parsed, using provided resolution.")
                    resolved_lines = conflict["resolved_content"].splitlines()

                file_lines[start:end] = resolved_lines

            path.write_text("\n".join(file_lines) + "\n", encoding='utf-8')
            return f"Successfully resolved and saved conflicts in: {file_path}. Backup created at: {backup_path}"
            
        except Exception as e:
            return f"Failed to resolve conflicts in file '{file_path}': {str(e)}"

    def _parse_conflict_block(self, conflict_content: str) -> Dict[str, str]:
        lines = conflict_content.split('\n')
        head_start, separator, base_separator, incoming_end = None, None, None, None
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('<<<<<<<'):
                head_start = i
            elif stripped.startswith('|||||||') and separator is None:
                base_separator = i
            elif stripped.startswith('=======') and separator is None:
                separator = i
            elif stripped.startswith('>>>>>>>'):
                incoming_end = i
                break
        
        if head_start is None or separator is None or incoming_end is None:
            return None
        
        if base_separator is not None:
            return {
                'head': '\n'.join(lines[head_start + 1:base_separator]),
                'base': '\n'.join(lines[base_separator + 1:separator]),
                'incoming': '\n'.join(lines[separator + 1:incoming_end])
            }
        else:
            return {
                'head': '\n'.join(lines[head_start + 1:separator]),
                'base': "",
                'incoming': '\n'.join(lines[separator + 1:incoming_end])
            }

    def _apply_intelligent_resolution(self, conflict_info: Dict[str, str], 
                                    provided_resolution: str, file_path: str) -> str:
        head_content = conflict_info['head']
        incoming_content = conflict_info['incoming']

        if provided_resolution and provided_resolution.strip():
            logging.info("Rule 8: Using provided resolution with WEBBAR preservation.")
            return self._preserve_custom_markers(head_content, incoming_content, provided_resolution, file_path)

        logging.info("Auto-resolving conflict...")
        return self._create_intelligent_resolution(head_content, incoming_content, file_path)

    def _preserve_custom_markers(self, head_content: str, incoming_content: str, 
                               resolution: str, file_path: str) -> str:
        custom_markers = self._extract_custom_markers(head_content)
        if not custom_markers:
            return resolution

        resolution_upper = resolution.upper()
        missing_markers = [m for m in custom_markers if m.upper() not in resolution_upper]

        if missing_markers:
            logging.info("Rule 3: Preserving missing WEBBAR/custom blocks from HEAD.")
        return resolution + ("\n\n" + "\n\n".join(missing_markers) if missing_markers else "")

    def _extract_custom_markers(self, content: str) -> List[str]:
        markers, block, inside_webbar = [], [], False
        for line in content.split('\n'):
            stripped = line.strip()
            if stripped.startswith(("# WEBBAR", "// WEBBAR", "<!-- WEBBAR")):
                inside_webbar, block = True, [line]
                continue
            if inside_webbar:
                block.append(line)
                if stripped.endswith(("# />", "// />", "<!-- /> -->")):
                    markers.append("\n".join(block))
                    inside_webbar, block = False, []
                continue
            if any(k in stripped.upper() for k in ['CUSTOM', 'PATCH', 'LOCAL', 'BROWSER']):
                markers.append(line)
        if inside_webbar and block:
            markers.append("\n".join(block))
        return markers

    def _create_intelligent_resolution(self, head_content: str, incoming_content: str, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        if ext in ['.h', '.cc', '.cpp', '.c']:
            return self._resolve_cpp_conflict(head_content, incoming_content)
        else:
            return self._resolve_generic_conflict(head_content, incoming_content)

    def _resolve_cpp_conflict(self, head_content: str, incoming_content: str) -> str:
        head_includes = self._extract_includes(head_content)
        incoming_includes = self._extract_includes(incoming_content)
        head_other = self._get_non_include_content(head_content)
        incoming_other = self._get_non_include_content(incoming_content)

        all_includes, seen = [], set()
        for inc in head_includes + incoming_includes:
            if inc.strip() not in seen:
                all_includes.append(inc)
                seen.add(inc.strip())

        logging.info("Rule 4: Preserving both sets of #include directives.")

        result = []
        if all_includes: result.extend(all_includes)
        if head_other.strip(): result.extend([""] + head_other.splitlines())
        if incoming_other.strip() and incoming_other != head_other:
            result.extend([""] + incoming_other.splitlines())
        return "\n".join(result)

    def _extract_includes(self, content: str) -> List[str]:
        return [line for line in content.splitlines() if line.strip().startswith("#include")]

    def _get_non_include_content(self, content: str) -> str:
        return "\n".join([l for l in content.splitlines() if l.strip() and not l.strip().startswith("#include")])

    def _resolve_generic_conflict(self, head_content: str, incoming_content: str) -> str:
        custom_blocks = self._extract_custom_markers(head_content)
        result_lines = incoming_content.splitlines()

        if not head_content.strip():
            logging.info("Rule 1: HEAD is empty → taking INCOMING.")
            return incoming_content
        elif custom_blocks:
            logging.info("Rule 3: Conflict inside WEBBAR → keeping WEBBAR from HEAD.")
            return "\n".join(result_lines + [""] + custom_blocks)
        elif head_content.strip() != incoming_content.strip():
            logging.info("Rule 2: Different logic → concatenating both versions.")
            return head_content + "\n\n" + incoming_content
        else:
            logging.info("Rule 8: Could not auto-resolve → keeping INCOMING for safety.")
            return incoming_content
