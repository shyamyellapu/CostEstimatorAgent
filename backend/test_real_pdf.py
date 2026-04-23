"""Test Claude with actual PDF converted to images (replicating real scenario)."""
import asyncio
import base64
import sys
sys.path.insert(0, 'app')

import os
from anthropic import AsyncAnthropic
from app.ai.prompts import DRAWING_READER_SYSTEM_PROMPT, IMAGE_EXTRACTION_PROMPT
from app.services.document_parser import pdf_to_images

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

async def test_with_real_pdf():
    client = AsyncAnthropic(api_key=API_KEY)
    
    # Use an actual PDF from uploads
    pdf_path = r"c:\Users\Bhatia\Desktop\CostEstimatorAgent\backend\storage\uploads\43306781-2972-4f47-b9fc-04da29e7a504\e3e1f40cce76439ba95e4f879b24e0fa.pdf"
    
    print("Reading PDF...")
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    
    print(f"PDF size: {len(pdf_bytes)} bytes")
    
    # Convert to images exactly like the app does
    print("Converting PDF to images...")
    image_list = pdf_to_images(pdf_bytes, max_pages=3, scale=1.5)
    print(f"Converted to {len(image_list)} images")
    
    for i, img_bytes in enumerate(image_list):
        print(f"  Image {i+1}: {len(img_bytes)} bytes")
    
    # Build user content exactly like extract_from_image does
    user_prompt = IMAGE_EXTRACTION_PROMPT.format(filename="test.pdf", context="")
    user_content = [{"type": "text", "text": user_prompt}]
    
    for img_bytes in image_list:
        b64_image = base64.standard_b64encode(img_bytes).decode("utf-8")
        user_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",  # Set to PNG since pdf_to_images converts to PNG
                "data": b64_image
            }
        })
    
    print(f"\nCalling Claude with {len(image_list)} images...")
    print("=" * 80)
    
    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            temperature=0.0,
            system=DRAWING_READER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}]
        )
        
        print(f"✅ Response received")
        print(f"Model: {response.model}")
        print(f"Content blocks: {len(response.content)}")
        
        if response.content and len(response.content) > 0:
            content_text = response.content[0].text
            print(f"Response length: {len(content_text)} chars")
            print(f"First 500 chars:\n{content_text[:500]}")
            print("\n" + "=" * 80)
            print(f"Last 1000 chars:\n{content_text[-1000:]}")
            print("=" * 80)
            
            # Check if JSON is present
            if "```json" in content_text:
                print("✅ Found ```json code block in response")
            elif "{" in content_text:
                print("✅ Found { but no ```json marker")
            else:
                print("❌ No JSON found in response!")
            
            print("✅ SUCCESS: Got response from Claude")
        else:
            print("❌ Empty response content!")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_with_real_pdf())
