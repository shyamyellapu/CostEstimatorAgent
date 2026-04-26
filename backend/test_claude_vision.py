"""Test Claude Sonnet 4.6 vision API with a simple image."""
import asyncio
import base64
import os
from anthropic import AsyncAnthropic

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

async def test_vision():
    client = AsyncAnthropic(api_key=API_KEY)
    
    # Create a simple 1x1 red PNG pixel
    red_pixel_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    )
    
    b64_image = base64.standard_b64encode(red_pixel_png).decode("utf-8")
    
    print("Testing Claude Sonnet 4.6 with vision...")
    print("=" * 80)
    
    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            temperature=0.0,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "What color is this pixel? Reply with just the color name."},
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
        print(f"Response: {response.content[0].text}")
        print("=" * 80)
        print("SUCCESS: Claude Sonnet 4.6 vision API working correctly")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_vision())
