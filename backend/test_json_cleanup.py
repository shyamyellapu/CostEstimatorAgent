"""Test the trailing comma cleanup."""
import json
import re

def clean_json_string(json_str: str) -> str:
    """Remove trailing commas and other common JSON syntax errors."""
    # Remove trailing commas before closing braces/brackets
    # Match: , followed by optional whitespace and then } or ]
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
    return json_str

# Test cases with trailing commas
test_cases = [
    # Trailing comma in object
    '{"key": "value",}',
    # Trailing comma in array
    '[1, 2, 3,]',
    # Nested trailing commas
    '{"a": {"b": [1, 2,],}, "c": 3,}',
    # Valid JSON (should not change)
    '{"key": "value"}',
    # The actual problematic pattern from Claude
    '''{
      "total_weight_kg": 72.0,
    }''',
]

print("Testing trailing comma cleanup...")
print("=" * 80)

for i, test_json in enumerate(test_cases, 1):
    print(f"\nTest {i}:")
    print(f"Input:  {test_json[:100]}")
    
    cleaned = clean_json_string(test_json)
    print(f"Output: {cleaned[:100]}")
    
    try:
        result = json.loads(cleaned)
        print("✅ Valid JSON after cleanup")
    except json.JSONDecodeError as e:
        print(f"❌ Still invalid: {e}")

print("\n" + "=" * 80)
print("All tests completed")
