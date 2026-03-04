"""
Code updater module for automated code modifications based on change manifests.
"""

import ast
import logging
import os
import re
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class CodeUpdater:
    """Handles automated code updates based on change manifests."""
    
    def __init__(self, base_path: str = "."):
        """
        Initialize code updater.
        
        Args:
            base_path: Base path for code files
        """
        self.base_path = Path(base_path)
        self.changes_log: List[Dict[str, Any]] = []
        self._init_git()
    
    def _init_git(self):
        """Initialize git repository if not already present."""
        try:
            import subprocess
            
            # Check if git is installed
            subprocess.run(["git", "--version"], capture_output=True, check=True)
            
            # Add safe directory exception for Docker/Ownership issues
            subprocess.run(["git", "config", "--global", "--add", "safe.directory", "*"], check=True)
            
            # Check if already a git repo
            if not (self.base_path / ".git").exists():
                logger.info(f"Initializing git repository in {self.base_path}")
                subprocess.run(["git", "init"], cwd=str(self.base_path), check=True)
                
                # Set dummy config if not set
                subprocess.run(["git", "config", "user.email", "agent@upi-ai.org"], cwd=str(self.base_path), check=True)
                subprocess.run(["git", "config", "user.name", "AI Agent"], cwd=str(self.base_path), check=True)
                
                # Initial commit of existing files
                subprocess.run(["git", "add", "."], cwd=str(self.base_path), check=True)
                subprocess.run(["git", "commit", "-m", "Initial commit from AI Agent"], cwd=str(self.base_path), check=True)
        except Exception as e:
            logger.warning(f"Git initialization failed: {e}. Changes will be made without version control.")

    def _git_commit(self, file_path: str, message: str):
        """Commit changes to git with robust logging."""
        try:
            import subprocess
            print(f">>> [Git] Adding file: {file_path}")
            subprocess.run(["git", "add", file_path], cwd=str(self.base_path), check=True)
            
            print(f">>> [Git] Committing: {message}")
            result = subprocess.run(
                ["git", "commit", "-m", message], 
                cwd=str(self.base_path), 
                capture_output=True, 
                text=True, 
                check=True
            )
            print(f">>> [Git] Commit successful: {result.stdout.strip()}")
            logger.info(f"Committed changes for {file_path}: {message}")
        except subprocess.CalledProcessError as e:
            print(f">>> [Git] Commit failed: {e.stderr.strip()}")
            logger.warning(f"Git commit failed: {e.stderr.strip()}")
        except Exception as e:
            print(f">>> [Git] Error during git commit: {e}")
            logger.warning(f"Git commit failed: {e}")

    def update_file(
        self,
        file_path: str,
        changes: Dict[str, Any],
        manifest_id: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Update a file based on change instructions with robust visibility.
        """
        full_path = self.base_path / file_path
        print(f"\n>>> [CodeUpdater] Starting update for: {file_path}")
        print(f">>> [CodeUpdater] Full path: {full_path.absolute()}")
        
        if not full_path.exists():
            msg = f"File not found: {file_path}"
            print(f">>> [CodeUpdater] ERROR: {msg}")
            return False, msg, None
        
        try:
            original_content = full_path.read_text(encoding="utf-8")
            print(f">>> [CodeUpdater] Read {len(original_content)} bytes from {file_path}")
            
            updated_content = self._apply_changes(original_content, changes)
            
            if updated_content != original_content:
                print(f">>> [CodeUpdater] Changes detected for {file_path}")
                
                # Save backup
                backup_path = full_path.with_suffix(full_path.suffix + ".backup")
                backup_path.write_text(original_content, encoding="utf-8")
                print(f">>> [CodeUpdater] Original content backed up to {backup_path.name}")
                
                # Write updated content
                full_path.write_text(updated_content, encoding="utf-8")
                print(f">>> [CodeUpdater] Successfully wrote updated content to {file_path}")

                # If this is a Python file, run a syntax check before committing.
                if full_path.suffix == ".py":
                    try:
                        import ast
                        ast.parse(updated_content)
                        print(f">>> [CodeUpdater] Syntax check passed for {file_path}")
                    except SyntaxError as e:
                        # Restore backup and report failure
                        print(f">>> [CodeUpdater] SYNTAX ERROR in {file_path}: {e}. Restoring backup.")
                        full_path.write_text(original_content, encoding="utf-8")
                        return False, f"Syntax error after update to {file_path}: {e}", None
                
                diff = self._generate_diff(original_content, updated_content)
                if diff:
                    print(f">>> [CodeUpdater] Generated Diff:\n{diff}")
                
                # Commit to git
                commit_msg = f"Update {file_path}"
                if manifest_id:
                    commit_msg += f" (Manifest: {manifest_id})"
                
                self._git_commit(file_path, commit_msg)
                
                self.changes_log.append({
                    "file": file_path,
                    "change_type": changes.get("type", "unknown"),
                    "status": "APPLIED",
                    "manifest_id": manifest_id
                })
                
                return True, f"Updated {file_path}", diff
            else:
                print(f">>> [CodeUpdater] No changes needed for {file_path} (content matches)")
                return False, f"No changes needed for {file_path}", None
                
        except Exception as e:
            logger.error(f"Error updating {file_path}: {e}")
            return False, f"Error: {str(e)}", None
    
    def _apply_changes(self, content: str, changes: Dict[str, Any]) -> str:
        """Apply changes to content."""
        change_type = changes.get("type", "unknown")
        
        if change_type == "add_function":
            return self._add_function(content, changes)
        elif change_type == "modify_function":
            return self._modify_function(content, changes)
        elif change_type == "add_import":
            return self._add_import(content, changes)
        elif change_type == "add_validation":
            return self._add_validation(content, changes)
        elif change_type == "modify_field":
            return self._modify_field(content, changes)
        else:
            # Generic text replacement
            return self._generic_replace(content, changes)
    
    def _add_function(self, content: str, changes: Dict[str, Any]) -> str:
        """Add a new function to the file."""
        function_code = changes.get("code", "")
        insert_after = changes.get("insert_after", "")
        
        if insert_after:
            pattern = re.compile(re.escape(insert_after), re.MULTILINE)
            if pattern.search(content):
                return pattern.sub(f"{insert_after}\n\n{function_code}", content)
        
        # Append at end if no insert point specified
        return f"{content}\n\n{function_code}"
    
    def _modify_function(self, content: str, changes: Dict[str, Any]) -> str:
        """Modify an existing function."""
        function_name = changes.get("function_name", "")
        new_code = changes.get("new_code", "")
        
        # Find function definition
        pattern = re.compile(
            rf"def\s+{re.escape(function_name)}\s*\([^)]*\):.*?(?=\n\ndef\s+|\nclass\s+|\Z)",
            re.DOTALL,
        )
        
        if pattern.search(content):
            return pattern.sub(f"def {function_name}(*args, **kwargs):\n{new_code}", content)
        
        return content
    
    def _add_import(self, content: str, changes: Dict[str, Any]) -> str:
        """Add an import statement."""
        import_stmt = changes.get("import", "")
        
        # Find last import
        lines = content.split("\n")
        last_import_idx = -1
        for i, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                last_import_idx = i
        
        if last_import_idx >= 0:
            lines.insert(last_import_idx + 1, import_stmt)
        else:
            lines.insert(0, import_stmt)
        
        return "\n".join(lines)
    
    def _add_validation(self, content: str, changes: Dict[str, Any]) -> str:
        """Add validation logic, maintaining indentation with robustness."""
        validation_code = changes.get("validation_code", "")
        insert_point = changes.get("insert_point", "")
        
        if insert_point:
            # Find indentation of the insertion point (last line)
            lines = insert_point.split("\n")
            last_line = lines[-1]
            indent = ""
            match = re.match(r"^(\s*)", last_line)
            if match:
                indent = match.group(1)
            
            # Clean validation code: strip leading indentation from each line
            # so we don't end up with double indentation
            val_lines = validation_code.split("\n")
            if val_lines:
                # Find common indentation if any
                first_line_strip = val_lines[0].lstrip()
                if not first_line_strip and len(val_lines) > 1:
                    first_line_strip = val_lines[1].lstrip()
                
            # Simpler approach: strip all leading whitespace from the WHOLE block
            # but keep relative indentation of sub-lines.
            # For now, just strip the base indentation of the block.
            stripped_val_lines = [line.lstrip() for line in val_lines]
            
            # Indent each line of the validation code with the target indent
            indented_code = "\n".join([f"{indent}{line}" if line.strip() else line for line in stripped_val_lines])
            
            pattern = re.compile(re.escape(insert_point), re.MULTILINE)
            if pattern.search(content):
                return pattern.sub(f"{insert_point}\n{indented_code}", content)
        
        return content
    
    def _modify_field(self, content: str, changes: Dict[str, Any]) -> str:
        """Modify a field in code."""
        old_field = changes.get("old_field", "")
        new_field = changes.get("new_field", "")
        
        if old_field and new_field:
            return content.replace(old_field, new_field)
        
        return content
    
    def _generic_replace(self, content: str, changes: Dict[str, Any]) -> str:
        """Generic text replacement with fallback patterns for flexible LLM instructions."""
        details = changes.get("details", "")
        
        # Collect all potential replacements
        all_replacements = []
        
        # 1. Standard 'replacements' list
        if isinstance(changes.get("replacements"), list):
            all_replacements.extend(changes["replacements"])
            
        # 2. 'details' as a list of replacement objects
        elif isinstance(details, list):
            all_replacements.extend(details)
            
        # 3. 'details' as a single replacement object
        elif isinstance(details, dict):
            all_replacements.append(details)
            
        # If we have collected any replacements, process them
        if all_replacements:
            new_content = content
            for r in all_replacements:
                if not isinstance(r, dict):
                    continue
                # Try all common key variants
                old_text = r.get("old") or r.get("code_before") or r.get("code_snippet_before") or r.get("before")
                new_text = r.get("new") or r.get("code_after") or r.get("code_snippet_after") or r.get("after") or ""
                
                if old_text:
                    # Strip common whitespace issues from LLM
                    old_text_clean = old_text.strip()
                    if old_text_clean in new_content:
                        new_content = new_content.replace(old_text_clean, new_text.strip() if isinstance(new_text, str) else str(new_text))
                    elif old_text in new_content:
                        new_content = new_content.replace(old_text, new_text)
            return new_content

        # 4. 'details' as a string with SEARCH/REPLACE or diff-like patterns
        if isinstance(details, str):
            # 4a. SEARCH/REPLACE split logic (Most robust)
            if "SEARCH:" in details.upper() and "REPLACE:" in details.upper():
                import re
                parts = re.split(r'SEARCH:', details, flags=re.IGNORECASE)
                new_content = content
                for part in parts:
                    if not part.strip() or "REPLACE:" not in part.upper():
                        continue
                        
                    subparts = re.split(r'REPLACE:', part, flags=re.IGNORECASE)
                    if len(subparts) >= 2:
                        search_text = subparts[0].strip('\r\n')
                        replace_text = subparts[1].strip('\r\n')
                        
                        if not search_text:
                            continue
                            
                        # Try exact match
                        if search_text in new_content:
                            new_content = new_content.replace(search_text, replace_text)
                        # Try stripping ONE leading space (common if LLM does SEARCH: <code>)
                        elif search_text.startswith(' ') and search_text[1:] in new_content:
                            # If we stripped a leading space from search, strip one from replace too if it exists
                            final_replace = replace_text[1:] if replace_text.startswith(' ') else replace_text
                            new_content = new_content.replace(search_text[1:], final_replace)
                        # Try stripping ALL leading/trailing whitespace but check if it's still unique
                        else:
                            search_text_clean = search_text.strip()
                            if search_text_clean and new_content.count(search_text_clean) == 1:
                                new_content = new_content.replace(search_text_clean, replace_text.strip())
                
                if new_content != content:
                    return new_content

            # 4b. Check for ``` markers
            blocks = re.findall(r'```(?:python)?\n(.*?)\n```', details, re.DOTALL)
            if len(blocks) >= 2:
                 temp_content = content
                 for i in range(0, len(blocks) - 1, 2):
                     before = blocks[i].strip()
                     after = blocks[i+1].strip()
                     if before in temp_content:
                         temp_content = temp_content.replace(before, after)
                     elif before.strip() in temp_content and temp_content.count(before.strip()) == 1:
                         temp_content = temp_content.replace(before.strip(), after)
                 return temp_content

        return content
    
    def _generate_diff(self, old_content: str, new_content: str) -> str:
        """Generate a simple diff between old and new content."""
        old_lines = old_content.split("\n")
        new_lines = new_content.split("\n")
        
        diff_lines = []
        max_len = max(len(old_lines), len(new_lines))
        
        for i in range(max_len):
            old_line = old_lines[i] if i < len(old_lines) else None
            new_line = new_lines[i] if i < len(new_lines) else None
            
            if old_line != new_line:
                if old_line is not None:
                    diff_lines.append(f"- {old_line}")
                if new_line is not None:
                    diff_lines.append(f"+ {new_line}")
        
        return "\n".join(diff_lines)
    
    def get_changes_log(self) -> List[Dict[str, Any]]:
        """Get log of all changes made."""
        return self.changes_log
