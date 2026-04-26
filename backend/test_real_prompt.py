"""Test Claude Sonnet 4.6 with the actual DRAWING_READER_SYSTEM_PROMPT."""
import asyncio
import base64
import sys
sys.path.insert(0, 'app')

import os
from anthropic import AsyncAnthropic
from app.ai.prompts import DRAWING_READER_SYSTEM_PROMPT, IMAGE_EXTRACTION_PROMPT

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

async def test_with_real_prompt():
    client = AsyncAnthropic(api_key=API_KEY)
    
    # Simple test image
    red_pixel_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    )
    
    b64_image = base64.standard_b64encode(red_pixel_png).decode("utf-8")
    
    user_prompt = IMAGE_EXTRACTION_PROMPT.format(filename="test.pdf", context="")
    
    print("Testing Claude Sonnet 4.6 with DRAWING_READER_SYSTEM_PROMPT...")
    print(f"System prompt length: {len(DRAWING_READER_SYSTEM_PROMPT)} chars")
    print(f"User prompt length: {len(user_prompt)} chars")
    print("=" * 80)
    
    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            temperature=0.0,
            system=DRAWING_READER_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64_image
                        }
                    }
                ]
            }]
        )
        
        print(f"✅ Response received")
        print(f"Model: {response.model}")
        print(f"Content blocks: {len(response.content)}")
        print(f"Response length: {len(response.content[0].text)}")
        print(f"First 500 chars: {response.content[0].text[:500]}")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_with_real_prompt())
