from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import json
import hashlib

class ConflictSummaryInput(BaseModel):
    base_path: str = Field(..., description="Base path of the project")
    scanned_files: List[str] = Field(..., description="List of all files that were scanned")
    detection_results: Dict[str, Any] = Field(..., description="Results from conflict detection task")
    resolution_results: Dict[str, Any] = Field(..., description="Results from conflict resolution task")
    output_file: str = Field(default="output/conflicts.md", description="Output file path for the report")

class ConflictSummaryTool(BaseTool):
    name: str = "Generate Conflict Resolution Summary"
    description: str = (
        "Generates a comprehensive summary report of the conflict resolution process, "
        "including statistics, detailed file reports, and manual review recommendations."
    )
    args_schema: Type[BaseModel] = ConflictSummaryInput

    def _run(self, base_path: str, scanned_files: List[str], detection_results: Dict[str, Any], 
             resolution_results: Dict[str, Any], output_file: str = "output/conflicts.md") -> str:
        
        try:
            # Parse and analyze the results
            summary_data = self._analyze_results(base_path, scanned_files, detection_results, resolution_results)
            
            # Generate the markdown report
            report_content = self._generate_markdown_report(summary_data)
            
            # Ensure output directory exists
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write the report
            output_path.write_text(report_content, encoding='utf-8')
            
            # Also generate a JSON summary for programmatic use
            json_output = output_path.with_suffix('.json')
            json_output.write_text(json.dumps(summary_data, indent=2), encoding='utf-8')
            
            return f"Successfully generated conflict resolution summary:\n- Markdown Report: {output_file}\n- JSON Data: {json_output}\n\nSummary: {summary_data['overall_stats']['files_successfully_resolved']}/{summary_data['overall_stats']['files_with_conflicts']} files resolved successfully"
            
        except Exception as e:
            return f"Failed to generate summary report: {str(e)}"

    def _analyze_results(self, base_path: str, scanned_files: List[str], 
                        detection_results: Dict[str, Any], resolution_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the detection and resolution results to create summary data"""
        
        # Parse detection results
        detected_conflicts = self._parse_detection_results(detection_results)
        
        # Parse resolution results  
        resolution_status = self._parse_resolution_results(resolution_results)
        
        # Calculate overall statistics
        overall_stats = self._calculate_overall_stats(scanned_files, detected_conflicts, resolution_status)
        
        # Generate detailed file reports
        file_reports = self._generate_file_reports(detected_conflicts, resolution_status)
        
        # Identify files needing manual review
        manual_review_files = self._identify_manual_review_files(file_reports)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'base_path': base_path,
            'overall_stats': overall_stats,
            'file_reports': file_reports,
            'manual_review_files': manual_review_files,
            'detection_results': detected_conflicts,
            'resolution_status': resolution_status
        }

    def _parse_detection_results(self, detection_results: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """Parse conflict detection results to extract file-level conflict information"""
        conflicts_by_file = {}
        
        # Handle different formats of detection results
        if isinstance(detection_results, dict):
            for file_path, conflicts in detection_results.items():
                if isinstance(conflicts, list):
                    conflicts_by_file[file_path] = conflicts
                elif isinstance(conflicts, str) and "conflict" in conflicts.lower():
                    # Parse string-based conflict descriptions
                    conflicts_by_file[file_path] = self._parse_conflict_string(conflicts)
        elif isinstance(detection_results, str):
            # Parse string-based results
            conflicts_by_file = self._parse_detection_string(detection_results)
        
        return conflicts_by_file

    def _parse_resolution_results(self, resolution_results: Dict[str, Any]) -> Dict[str, Dict]:
        """Parse conflict resolution results to extract success/failure status"""
        resolution_status = {}
        
        if isinstance(resolution_results, dict):
            for file_path, result in resolution_results.items():
                if isinstance(result, dict):
                    resolution_status[file_path] = result
                elif isinstance(result, str):
                    resolution_status[file_path] = self._parse_resolution_string(result)
        elif isinstance(resolution_results, str):
            resolution_status = self._parse_resolution_string_global(resolution_results)
        
        return resolution_status

    def _parse_conflict_string(self, conflict_str: str) -> List[Dict]:
        """Parse conflict information from string format"""
        conflicts = []
        lines = conflict_str.split('\n')
        
        current_conflict = {}
        for line in lines:
            if 'CONFLICT' in line and 'Lines:' in line:
                if current_conflict:
                    conflicts.append(current_conflict)
                current_conflict = {'type': 'merge_conflict'}
                # Extract line numbers
                import re
                line_match = re.search(r'Lines:\s*(\d+)-(\d+)', line)
                if line_match:
                    current_conflict['start_line'] = int(line_match.group(1))
                    current_conflict['end_line'] = int(line_match.group(2))
            elif 'HEAD' in line and current_conflict:
                current_conflict['head_content'] = ''
            elif 'INCOMING' in line and current_conflict:
                current_conflict['incoming_content'] = ''
        
        if current_conflict:
            conflicts.append(current_conflict)
        
        return conflicts

    def _parse_detection_string(self, detection_str: str) -> Dict[str, List[Dict]]:
        """Parse global detection string to extract per-file conflicts"""
        conflicts_by_file = {}
        current_file = None
        
        lines = detection_str.split('\n')
        for line in lines:
            if line.strip().endswith('.cc') or line.strip().endswith('.h') or line.strip().endswith('.cpp'):
                current_file = line.strip()
                conflicts_by_file[current_file] = []
            elif 'conflict' in line.lower() and current_file:
                conflict_info = {'type': 'detected', 'description': line.strip()}
                conflicts_by_file[current_file].append(conflict_info)
        
        return conflicts_by_file

    def _parse_resolution_string(self, resolution_str: str) -> Dict[str, Any]:
        """Parse resolution result string"""
        if 'successfully' in resolution_str.lower():
            return {'status': 'resolved', 'message': resolution_str}
        elif 'failed' in resolution_str.lower() or 'error' in resolution_str.lower():
            return {'status': 'failed', 'message': resolution_str}
        else:
            return {'status': 'partial', 'message': resolution_str}

    def _parse_resolution_string_global(self, resolution_str: str) -> Dict[str, Dict]:
        """Parse global resolution string"""
        resolution_status = {}
        lines = resolution_str.split('\n')
        
        for line in lines:
            if any(ext in line for ext in ['.cc', '.h', '.cpp', '.py']):
                if 'successfully' in line.lower():
                    # Extract file path
                    for word in line.split():
                        if any(ext in word for ext in ['.cc', '.h', '.cpp', '.py']):
                            resolution_status[word] = {'status': 'resolved', 'message': line}
                            break
                elif 'failed' in line.lower():
                    for word in line.split():
                        if any(ext in word for ext in ['.cc', '.h', '.cpp', '.py']):
                            resolution_status[word] = {'status': 'failed', 'message': line}
                            break
        
        return resolution_status

    def _calculate_overall_stats(self, scanned_files: List[str], detected_conflicts: Dict, 
                               resolution_status: Dict) -> Dict[str, int]:
        """Calculate overall statistics"""
        files_with_conflicts = len(detected_conflicts)
        
        resolved_files = sum(1 for status in resolution_status.values() 
                           if isinstance(status, dict) and status.get('status') == 'resolved')
        
        partially_resolved_files = sum(1 for status in resolution_status.values() 
                                     if isinstance(status, dict) and status.get('status') == 'partial')
        
        failed_files = files_with_conflicts - resolved_files - partially_resolved_files
        
        total_conflicts = sum(len(conflicts) for conflicts in detected_conflicts.values() 
                            if isinstance(conflicts, list))
        
        return {
            'total_files_scanned': len(scanned_files),
            'files_with_conflicts': files_with_conflicts,
            'files_successfully_resolved': resolved_files,
            'files_partially_resolved': partially_resolved_files,
            'files_with_unresolved_conflicts': failed_files,
            'total_conflicts_detected': total_conflicts,
            'total_conflicts_resolved': resolved_files,  # Simplified - can be enhanced
            'total_conflicts_unresolved': total_conflicts - resolved_files
        }

    def _generate_file_reports(self, detected_conflicts: Dict, resolution_status: Dict) -> List[Dict]:
        """Generate detailed reports for each file"""
        file_reports = []
        
        all_conflict_files = set(detected_conflicts.keys()) | set(resolution_status.keys())
        
        for file_path in all_conflict_files:
            conflicts = detected_conflicts.get(file_path, [])
            resolution = resolution_status.get(file_path, {})
            
            # Determine file status
            if resolution.get('status') == 'resolved':
                file_status = "Resolved Successfully"
            elif resolution.get('status') == 'partial':
                file_status = "Partially Resolved (Some Conflicts Remain)"
            elif resolution.get('status') == 'failed':
                file_status = "Unresolved (All Conflicts Remain)"
            else:
                file_status = "Status Unknown"
            
            report = {
                'file_path': file_path,
                'file_status': file_status,
                'conflicts': []
            }
            
            # Add conflict details
            for i, conflict in enumerate(conflicts):
                conflict_report = {
                    'conflict_id': i + 1,
                    'start_line': conflict.get('start_line', 'Unknown'),
                    'end_line': conflict.get('end_line', 'Unknown'),
                    'resolution_status': 'Resolved' if resolution.get('status') == 'resolved' else 'Unresolved',
                    'head_content_excerpt': self._create_excerpt(conflict.get('head_content', '')),
                    'incoming_content_excerpt': self._create_excerpt(conflict.get('incoming_content', '')),
                    'resolved_content_excerpt': 'N/A' if resolution.get('status') != 'resolved' else 'Applied'
                }
                report['conflicts'].append(conflict_report)
            
            file_reports.append(report)
        
        return file_reports

    def _create_excerpt(self, content: str, max_lines: int = 3) -> str:
        """Create an excerpt of content for the report"""
        if not content or not content.strip():
            return "(empty)"
        
        lines = content.strip().split('\n')
        if len(lines) <= max_lines:
            return content.strip()
        
        excerpt_lines = lines[:max_lines]
        return '\n'.join(excerpt_lines) + f'\n... ({len(lines) - max_lines} more lines)'

    def _identify_manual_review_files(self, file_reports: List[Dict]) -> List[Dict]:
        """Identify files that need manual review"""
        manual_review = []
        
        for report in file_reports:
            needs_review = False
            reasons = []
            
            if report['file_status'] != "Resolved Successfully":
                needs_review = True
                reasons.append(f"File status: {report['file_status']}")
            
            unresolved_conflicts = [c for c in report['conflicts'] 
                                  if c['resolution_status'] == 'Unresolved']
            if unresolved_conflicts:
                needs_review = True
                reasons.append(f"{len(unresolved_conflicts)} unresolved conflicts")
            
            if needs_review:
                manual_review.append({
                    'file_path': report['file_path'],
                    'reasons': reasons,
                    'priority': self._determine_priority(report),
                    'unresolved_conflicts': len(unresolved_conflicts)
                })
        
        # Sort by priority
        manual_review.sort(key=lambda x: (x['priority'], -x['unresolved_conflicts']))
        return manual_review

    def _determine_priority(self, report: Dict) -> int:
        """Determine priority for manual review (1=highest, 3=lowest)"""
        file_path = report['file_path'].lower()
        
        # High priority: Core browser files
        if any(keyword in file_path for keyword in ['browser', 'chrome', 'content', 'ui']):
            return 1
        
        # Medium priority: Extension or component files
        if any(keyword in file_path for keyword in ['extension', 'component', 'service']):
            return 2
        
        # Low priority: Test or utility files
        return 3

    def _generate_markdown_report(self, summary_data: Dict) -> str:
        """Generate the markdown report content"""
        
        report = f"""# Conflict Resolution Summary Report

**Generated:** {summary_data['timestamp']}  
**Project Path:** `{summary_data['base_path']}`

## Overall Summary

| Metric | Count |
|--------|-------|
| Total Files Scanned | {summary_data['overall_stats']['total_files_scanned']} |
| Files with Conflicts Found | {summary_data['overall_stats']['files_with_conflicts']} |
| Files Successfully Resolved | {summary_data['overall_stats']['files_successfully_resolved']} |
| Files Partially Resolved | {summary_data['overall_stats']['files_partially_resolved']} |
| Files with Unresolved Conflicts | {summary_data['overall_stats']['files_with_unresolved_conflicts']} |
| Total Conflicts Detected | {summary_data['overall_stats']['total_conflicts_detected']} |
| Total Conflicts Resolved | {summary_data['overall_stats']['total_conflicts_resolved']} |
| Total Conflicts Unresolved | {summary_data['overall_stats']['total_conflicts_unresolved']} |

## Resolution Success Rate

**Overall Success Rate:** {(summary_data['overall_stats']['files_successfully_resolved'] / max(summary_data['overall_stats']['files_with_conflicts'], 1) * 100):.1f}%

"""

        # Manual Review Section
        if summary_data['manual_review_files']:
            report += "## ⚠️ Files Requiring Manual Review\n\n"
            
            for file_info in summary_data['manual_review_files']:
                report += f"**{file_info['file_path']}**\n"
                report += f"   - Unresolved Conflicts: {file_info['unresolved_conflicts']}\n"
                report += f"   - Reasons: {', '.join(file_info['reasons'])}\n\n"
        else:
            report += "## All Conflicts Successfully Resolved\n\nNo files require manual review.\n\n"

        # Detailed File Reports
        report += "## Detailed File Reports\n\n"
        
        for file_report in summary_data['file_reports']:
            
            report += f"### {file_report['file_path']}\n\n"
            report += f"**Status:** {file_report['file_status']}  \n"
            report += f"**Conflicts Found:** {len(file_report['conflicts'])}\n\n"
            
            for conflict in file_report['conflicts']:
                status_symbol = "✓" if conflict['resolution_status'] == 'Resolved' else "✗"
                report += f"#### {status_symbol} Conflict {conflict['conflict_id']}\n"
                report += f"**Lines:** {conflict['start_line']}-{conflict['end_line']}  \n"
                report += f"**Status:** {conflict['resolution_status']}\n\n"
                
                if conflict['head_content_excerpt'] != "(empty)":
                    report += "**HEAD Content:**\n```\n" + conflict['head_content_excerpt'] + "\n```\n\n"
                
                if conflict['incoming_content_excerpt'] != "(empty)":
                    report += "**INCOMING Content:**\n```\n" + conflict['incoming_content_excerpt'] + "\n```\n\n"
                
                if conflict['resolved_content_excerpt'] != "N/A":
                    report += "**Resolution:** Applied successfully\n\n"
                else:
                    report += "**Resolution:** Not resolved - requires manual intervention\n\n"
            
            report += "---\n\n"

        # Footer
        report += f"""## Summary

This report was generated automatically by the Conflict Resolution Agent. 
For questions or issues, please review the files marked for manual attention above.

**Next Steps:**
1. Review files marked with (high priority) first
2. Manually resolve any remaining conflicts
3. Test the resolved code to ensure functionality
4. Commit the changes when satisfied

*Report generated on {summary_data['timestamp']}*
"""

        return report
