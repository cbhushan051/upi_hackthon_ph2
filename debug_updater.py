
import re
from typing import Dict, Any

def _generic_replace(content: str, changes: Dict[str, Any]) -> str:
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
                    print(f"DEBUG: Found clean match for {old_text_clean[:20]}...")
                    new_content = new_content.replace(old_text_clean, new_text.strip() if isinstance(new_text, str) else str(new_text))
                elif old_text in new_content:
                    print(f"DEBUG: Found exact match for {old_text[:20]}...")
                    new_content = new_content.replace(old_text, new_text)
                else:
                    print(f"DEBUG: Failed to find match for:\n'{old_text}'")
        return new_content

    # 4. 'details' as a string with diff-like block patterns (Experimental)
    if isinstance(details, str):
        # Check for ``` markers
        blocks = re.findall(r'```(?:python)?\n(.*?)\n```', details, re.DOTALL)
        if len(blocks) >= 2:
             print("DEBUG: Found code blocks")
             temp_content = content
             for i in range(0, len(blocks) - 1, 2):
                 before = blocks[i].strip()
                 after = blocks[i+1].strip()
                 if before in temp_content:
                     temp_content = temp_content.replace(before, after)
             return temp_content
        
        # Simple text-based SEARCH/REPLACE patterns
        search_match = re.search(r'SEARCH:?\s*\n(.*?)\nREPLACE:?', details, re.DOTALL | re.IGNORECASE)
        replace_match = re.search(r'REPLACE:?\s*\n(.*?)(?:\n\n|\Z)', details, re.DOTALL | re.IGNORECASE)
        if search_match and replace_match:
            search_text = search_match.group(1).rstrip('\r\n')
            replace_text = replace_match.group(1).rstrip('\r\n')
            print(f"DEBUG: SEARCH found (len={len(search_text)}):\n'{search_text}'")
            print(f"DEBUG: CONTENT len={len(content)}")
            if search_text in content:
                print("DEBUG: Found SEARCH text in content")
                return content.replace(search_text, replace_text)
            else:
                print("DEBUG: SEARCH text NOT in content")
                print(f"SEARCH START: {repr(search_text[:50])}")
                print(f"CONTENT START: {repr(content[:50])}")
                
                # Check for whitespace mismatch
                if search_text.replace(" ", "") == content.replace(" ", ""):
                    print("DEBUG: Match found after removing spaces! Whitespace mismatch.")

    return content

content = """        if not account:
            result = "FAILURE"
            err_code = "PAYEE_NOT_FOUND"
        elif amount <= 0:
            result = "FAILURE"
            err_code = "INVALID_AMOUNT"
        else:
            account.balance += amount
            session.commit()
            bal_amt = account.balance"""

details = """SEARCH:         if not account:
            result = "FAILURE"
            err_code = "PAYEE_NOT_FOUND"
        elif amount <= 0:
            result = "FAILURE"
            err_code = "INVALID_AMOUNT"
        else:
            account.balance += amount
            session.commit()
            bal_amt = account.balance
REPLACE:         if not account:
            result = "FAILURE"
            err_code = "PAYEE_NOT_FOUND"
        elif amount < MIN_TXN_AMOUNT:
            # Transaction amount is below the minimum threshold
            result = "FAILURE"
            err_code = "MIN_AMOUNT_NOT_MET"
        elif amount <= 0:
            result = "FAILURE"
            err_code = "INVALID_AMOUNT"
        else:
            account.balance += amount
            session.commit()
            bal_amt = account.balance"""

updated = _generic_replace(content, {"details": details})
if updated != content:
    print("SUCCESS")
else:
    print("FAILURE")
