from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, List, Dict, Any
from pathlib import Path
import re

class FixMergeConflictsInput(BaseModel):
    file_path: str = Field(..., description="The path to the conflicted file.")
    resolved_blocks: List[Dict[str, Any]] = Field(
        ..., description="List of resolved conflict blocks with 'start_line', 'end_line', and 'resolved_content'"
    )

class FixMergeConflictsTool(BaseTool):
    name: str = "Fix Merge Conflicts in File"
    description: str = (
        "Applies resolved conflict blocks into the specified lines of the file, "
        "preserving the rest of the content and important custom markers like WEBBAR."
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
            # Create backup before making changes
            backup_path = path.with_suffix(path.suffix + '.backup')
            backup_path.write_text('\n'.join(file_lines) + '\n', encoding='utf-8')
            
            # Process conflicts in reverse order to maintain line numbers
            for conflict in sorted(resolved_blocks, key=lambda c: c["start_line"], reverse=True):
                start = conflict["start_line"] - 1  # Convert to 0-based index
                end = conflict["end_line"]          # Slicing end is exclusive

                # Extract the original conflict block for analysis
                original_conflict_lines = file_lines[start:end]
                original_conflict_content = '\n'.join(original_conflict_lines)
                
                # Parse the conflict to extract HEAD, INCOMING, and any BASE content
                conflict_info = self._parse_conflict_block(original_conflict_content)
                
                if conflict_info:
                    # Apply intelligent resolution that preserves WEBBAR and other important content
                    intelligent_resolution = self._apply_intelligent_resolution(
                        conflict_info, 
                        conflict.get("resolved_content", ""),
                        file_path
                    )
                    resolved_lines = intelligent_resolution.splitlines()
                else:
                    # Fallback to provided resolution if parsing fails
                    resolved_lines = conflict["resolved_content"].splitlines()

                # Replace the conflicted lines with resolved lines
                file_lines[start:end] = resolved_lines

            # Write final content
            path.write_text("\n".join(file_lines) + "\n", encoding='utf-8')
            return f"Successfully resolved and saved conflicts in: {file_path}. Backup created at: {backup_path}"
            
        except Exception as e:
            return f"Failed to resolve conflicts in file '{file_path}': {str(e)}"

    def _parse_conflict_block(self, conflict_content: str) -> Dict[str, str]:
        """Parse a conflict block to extract HEAD, INCOMING, and BASE content"""
        lines = conflict_content.split('\n')
        
        head_start = None
        separator = None
        base_separator = None
        incoming_end = None
        
        # Find conflict markers
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if line_stripped.startswith('<<<<<<<'):
                head_start = i
            elif line_stripped.startswith('|||||||') and separator is None:
                base_separator = i
            elif line_stripped.startswith('=======') and separator is None:
                separator = i
            elif line_stripped.startswith('>>>>>>>'):
                incoming_end = i
                break
        
        if head_start is None or separator is None or incoming_end is None:
            return None
        
        # Extract content sections
        if base_separator is not None:
            # 3-way merge
            head_content = '\n'.join(lines[head_start + 1:base_separator])
            base_content = '\n'.join(lines[base_separator + 1:separator])
            incoming_content = '\n'.join(lines[separator + 1:incoming_end])
        else:
            # 2-way merge
            head_content = '\n'.join(lines[head_start + 1:separator])
            base_content = ""
            incoming_content = '\n'.join(lines[separator + 1:incoming_end])
        
        return {
            'head': head_content,
            'incoming': incoming_content,
            'base': base_content
        }

    def _apply_intelligent_resolution(self, conflict_info: Dict[str, str], 
                                    provided_resolution: str, file_path: str) -> str:
        """Apply intelligent resolution that preserves important custom content"""
        
        head_content = conflict_info['head']
        incoming_content = conflict_info['incoming']
        base_content = conflict_info.get('base', '')
        
        # Check if we have a provided resolution
        if provided_resolution and provided_resolution.strip():
            # Enhance the provided resolution by ensuring WEBBAR content is preserved
            enhanced_resolution = self._preserve_custom_markers(
                head_content, incoming_content, provided_resolution, file_path
            )
            return enhanced_resolution
        
        # If no resolution provided, create one intelligently
        return self._create_intelligent_resolution(head_content, incoming_content, file_path)

    def _preserve_custom_markers(self, head_content: str, incoming_content: str, 
                               resolution: str, file_path: str) -> str:
        """Ensure custom markers like WEBBAR are preserved in the resolution"""
        
        # Extract custom markers and comments from HEAD content
        custom_markers = self._extract_custom_markers(head_content)
        
        if not custom_markers:
            return resolution
        
        # Check if resolution already contains the custom markers
        resolution_upper = resolution.upper()
        missing_markers = []
        
        for marker in custom_markers:
            if marker.upper() not in resolution_upper:
                missing_markers.append(marker)
        
        if not missing_markers:
            return resolution  # All markers already present
        
        # Add missing markers to the resolution
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext in ['.h', '.cc', '.cpp', '.c']:
            # For C++ files, add missing markers appropriately
            return self._merge_cpp_with_markers(resolution, missing_markers)
        else:
            # For other files, append missing markers
            return resolution + '\n' + '\n'.join(missing_markers)

    def _extract_custom_markers(self, content: str) -> List[str]:
        """Extract custom markers and important comments from content"""
        markers = []
        lines = content.split('\n')
        
        for line in lines:
            line_stripped = line.strip()
            # Look for important custom markers
            if any(keyword in line_stripped.upper() for keyword in 
                   ['WEBBAR', 'CUSTOM', 'PATCH', 'LOCAL', 'BROWSER']):
                markers.append(line)
            # Also preserve comments that look important
            elif (line_stripped.startswith('//') and 
                  any(char in line_stripped for char in ['>', '<', '*', '!'])):
                markers.append(line)
        
        return markers

    def _merge_cpp_with_markers(self, resolution: str, markers: List[str]) -> str:
        """Intelligently merge C++ resolution with custom markers"""
        resolution_lines = resolution.split('\n')
        
        # Separate includes from other content
        includes = []
        other_content = []
        marker_content = []
        
        for line in resolution_lines:
            if line.strip().startswith('#include'):
                includes.append(line)
            else:
                other_content.append(line)
        
        # Process markers
        for marker in markers:
            marker_stripped = marker.strip()
            if marker_stripped.startswith('#include'):
                # Add to includes if not already present
                if marker not in includes:
                    includes.append(marker)
            else:
                # Add to marker content
                marker_content.append(marker)
        
        # Reconstruct the content
        result_parts = []
        
        # Add includes first
        if includes:
            result_parts.extend(includes)
        
        # Add marker content
        if marker_content:
            if includes:
                result_parts.append('')  # Add blank line after includes
            result_parts.extend(marker_content)
        
        # Add other content
        if other_content and any(line.strip() for line in other_content):
            if includes or marker_content:
                result_parts.append('')  # Add blank line
            result_parts.extend(other_content)
        
        return '\n'.join(result_parts)

    def _create_intelligent_resolution(self, head_content: str, incoming_content: str, file_path: str) -> str:
        """Create an intelligent resolution when none is provided"""
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext in ['.h', '.cc', '.cpp', '.c']:
            return self._resolve_cpp_conflict(head_content, incoming_content)
        else:
            return self._resolve_generic_conflict(head_content, incoming_content)

    def _resolve_cpp_conflict(self, head_content: str, incoming_content: str) -> str:
        """Resolve C++ conflicts intelligently"""
        # Extract includes from both sides
        head_includes = self._extract_includes(head_content)
        incoming_includes = self._extract_includes(incoming_content)
        
        # Extract non-include content
        head_other = self._get_non_include_content(head_content)
        incoming_other = self._get_non_include_content(incoming_content)
        
        # Merge includes (remove duplicates, preserve order)
        all_includes = []
        seen_includes = set()
        
        # Add head includes first
        for include in head_includes:
            include_normalized = include.strip()
            if include_normalized not in seen_includes:
                all_includes.append(include)
                seen_includes.add(include_normalized)
        
        # Add incoming includes
        for include in incoming_includes:
            include_normalized = include.strip()
            if include_normalized not in seen_includes:
                all_includes.append(include)
                seen_includes.add(include_normalized)
        
        # Combine all content
        result_parts = []
        
        if all_includes:
            result_parts.extend(all_includes)
        
        # Add non-include content, preserving custom markers
        if head_other and head_other.strip():
            if all_includes:
                result_parts.append('')  # Blank line after includes
            result_parts.extend(head_other.split('\n'))
        
        if incoming_other and incoming_other.strip() and incoming_other != head_other:
            if all_includes or head_other:
                result_parts.append('')  # Blank line
            result_parts.extend(incoming_other.split('\n'))
        
        return '\n'.join(result_parts)

    def _extract_includes(self, content: str) -> List[str]:
        """Extract #include statements"""
        includes = []
        for line in content.split('\n'):
            if line.strip().startswith('#include'):
                includes.append(line)
        return includes

    def _get_non_include_content(self, content: str) -> str:
        """Get content that's not #include statements"""
        non_include_lines = []
        for line in content.split('\n'):
            if not line.strip().startswith('#include') and line.strip():
                non_include_lines.append(line)
        return '\n'.join(non_include_lines) if non_include_lines else ""

    def _resolve_generic_conflict(self, head_content: str, incoming_content: str) -> str:
        """Generic conflict resolution preserving custom content"""
        # Look for important custom markers in head content
        head_lines = head_content.split('\n')
        incoming_lines = incoming_content.split('\n')
        
        custom_lines = []
        for line in head_lines:
            if any(keyword in line.upper() for keyword in 
                   ['WEBBAR', 'CUSTOM', 'PATCH', 'LOCAL', 'BROWSER']):
                custom_lines.append(line)
        
        # Combine incoming content with custom markers
        result_lines = incoming_lines[:]
        
        if custom_lines:
            result_lines.extend([''] + custom_lines)  # Add blank line before custom content
        
        return '\n'.join(result_lines)