"""Test the updated _parse_json_response with Claude 4's format."""
import json
import re

def parse_json_response(content: str) -> dict:
    """Parse JSON from Claude response, handling markdown code blocks."""
    print(f"Input length: {len(content)}")
    print(f"First 100 chars: {content[:100]}")
    
    if not content or not content.strip():
        raise ValueError("Empty response from Claude")
    
    # Try to extract JSON from markdown code block if present ANYWHERE in the response
    if "```json" in content or "```" in content:
        # First try to find ```json specifically
        json_match = re.search(r'```json\s*\n(.*?)\n```', content, re.DOTALL)
        if json_match:
            print("✅ Found ```json block in response")
            content = json_match.group(1)
        else:
            # Try generic ``` blocks
            json_match = re.search(r'```\s*\n(.*?)\n```', content, re.DOTALL)
            if json_match:
                print("✅ Found generic ``` block in response")
                content = json_match.group(1)
    
    # If still not JSON, try to find a JSON object in the text
    if not content.strip().startswith("{"):
        # Look for the first { to the last matching }
        json_match = re.search(r'(\{.*\})', content, re.DOTALL)
        if json_match:
            print("✅ Extracted JSON object from text")
            content = json_match.group(1)
    
    try:
        result = json.loads(content)
        print(f"✅ JSON parsed successfully: {list(result.keys())[:5]}")
        return result
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        print(f"Content: {content[:200]}")
        raise

# Test with Claude 4's actual format
sample_response = """I'll systematically process all 3 sheets following the mandatory 5-pass extraction process.

**PASS 1 — TITLE BLOCK SCAN**
- Project: Test Project
- Drawing No: 12345

```json
{
  "drawing_metadata": {
    "project_name": "Test",
    "total_sheets_in_drawing": 3
  },
  "dimensions": []
}
```

That completes the extraction."""

print("Testing updated _parse_json_response with Claude 4 format...")
print("=" * 80)
try:
    result = parse_json_response(sample_response)
    print("✅ SUCCESS")
except Exception as e:
    print(f"❌ FAILED: {e}")
    import traceback
    traceback.print_exc()
