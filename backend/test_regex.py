"""Test the _parse_json_response regex."""
import re
import json

# Sample response from Claude (what we just saw)
sample_response = """```json
{
  "drawing_metadata": {
    "project_name": "Test",
    "total_sheets_in_drawing": 1
  },
  "dimensions": []
}
```"""

def parse_json_response(content: str) -> dict:
    """Parse JSON from Claude response, handling markdown code blocks."""
    print(f"Input length: {len(content)}")
    print(f"Starts with backticks: {content.strip().startswith('```')}")
    
    if not content or not content.strip():
        raise ValueError("Empty response from Claude")
    
    # Try to extract JSON from markdown code block if present
    if content.strip().startswith("```"):
        print("Attempting to extract from markdown block...")
        json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', content, re.DOTALL)
        if json_match:
            print(f"✅ Regex matched! Extracted {len(json_match.group(1))} chars")
            content = json_match.group(1)
        else:
            print("❌ Regex did NOT match!")
            # Try alternative pattern
            alt_match = re.search(r'```json\s*(.*)```', content, re.DOTALL)
            if alt_match:
                print("✅ Alternative regex matched!")
                content = alt_match.group(1).strip()
            else:
                print("❌ Alternative regex also failed!")
    
    try:
        result = json.loads(content)
        print(f"✅ JSON parsed successfully: {list(result.keys())}")
        return result
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        print(f"Content: {content[:200]}")
        raise

print("Testing _parse_json_response regex...")
print("=" * 80)
try:
    result = parse_json_response(sample_response)
    print("✅ SUCCESS")
except Exception as e:
    print(f"❌ FAILED: {e}")
