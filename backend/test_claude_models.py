"""Test script to discover valid Claude 4 model names."""
import asyncio
import os
from anthropic import AsyncAnthropic

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

async def test_model(client, model_name):
    """Test if a model name is valid."""
    try:
        response = await client.messages.create(
            model=model_name,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        print(f"✅ {model_name:<50} - WORKS")
        return True
    except Exception as e:
        error_msg = str(e)[:100]
        print(f"❌ {model_name:<50} - {error_msg}")
        return False

async def main():
    client = AsyncAnthropic(api_key=API_KEY)
    
    print("Testing Claude 4 model names...")
    print("=" * 80)
    
    # Possible Claude 4 naming patterns
    test_models = [
        # Pattern 1: claude-version-model-date
        "claude-4-sonnet-20260101",
        "claude-4-opus-20260101",
        "claude-4-haiku-20260101",
        
        # Pattern 2: claude-model-version
        "claude-sonnet-4",
        "claude-opus-4",
        "claude-haiku-4",
        
        # Pattern 3: claude-model-version-patch
        "claude-sonnet-4-6",
        "claude-opus-4-7",
        "claude-haiku-4-5",
        
        # Pattern 4: claude-version-model (no date)
        "claude-4-sonnet",
        "claude-4-opus",
        "claude-4-haiku",
        
        # Claude 3.5 (known working)
        "claude-3-5-sonnet-20241022",
    ]
    
    for model in test_models:
        await test_model(client, model)
        await asyncio.sleep(0.5)  # Rate limiting
    
    print("=" * 80)
    print("\nTo find the exact model names, visit:")
    print("https://docs.anthropic.com/en/docs/about-claude/models")

if __name__ == "__main__":
    asyncio.run(main())
