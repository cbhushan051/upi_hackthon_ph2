
import re

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
REPLACE: REPLACE_TEXT"""

def parse_and_apply(content, details):
    import re
    # Divide string by SEARCH: markers
    parts = re.split(r'SEARCH:', details, flags=re.IGNORECASE)
    temp_content = content
    for part in parts:
        if not part.strip(): continue
        if "REPLACE:" in part:
            # Further split by REPLACE:
            subparts = re.split(r'REPLACE:', part, flags=re.IGNORECASE)
            if len(subparts) >= 2:
                # Strip only leading/trailing newlines to preserve indentation
                search_text = subparts[0].strip('\r\n')
                # If the first line of search_text started on the same line as SEARCH:
                # it might have a leading space.
                if search_text.startswith(' '):
                    # Only strip ONE leading space if there's exactly one after SEARCH:
                    # But better: check if the matched string in content has those spaces.
                    pass
                
                replace_text = subparts[1].strip('\r\n')
                
                print(f"Parsed SEARCH (len={len(search_text)}):\n{repr(search_text)}")
                
                if search_text in temp_content:
                    print("MATCH FOUND")
                    temp_content = temp_content.replace(search_text, replace_text)
                else:
                    # Fallback: try stripping leading space if SEARCH: <space><code>
                    if search_text.startswith(' ') and search_text[1:] in temp_content:
                         print("MATCH FOUND (after stripping one leading space)")
                         temp_content = temp_content.replace(search_text[1:], replace_text)
                    else:
                        print("MATCH NOT FOUND")
    return temp_content

updated = parse_and_apply(content, details)
if updated != content:
    print("FINAL SUCCESS")
else:
    print("FINAL FAILURE")
