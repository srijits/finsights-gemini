"""
Test script for Gemini API with Google Search grounding.
Uses google-genai SDK v1.x
"""
import os
from google import genai
from google.genai import types

# Get API key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("Error: GEMINI_API_KEY not set")
    print("Usage: set GEMINI_API_KEY=your-key-here")
    exit(1)

# Create client
client = genai.Client(api_key=api_key)

# Test query with grounding
query = "What are the latest developments in Indian stock market today?"

print(f"Testing Gemini API with Google Search grounding")
print(f"Query: {query}\n")
print("-" * 50)

try:
    # Google Search grounding tool
    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=query,
        config=types.GenerateContentConfig(tools=[grounding_tool]),
    )
    
    print("Response:")
    print(response.text)
    
    # Check for grounding sources
    if response.candidates and response.candidates[0].grounding_metadata:
        grounding = response.candidates[0].grounding_metadata
        print("\n" + "-" * 50)
        print("Grounding Sources:")
        if hasattr(grounding, 'grounding_chunks') and grounding.grounding_chunks:
            for i, chunk in enumerate(grounding.grounding_chunks, 1):
                if hasattr(chunk, 'web') and chunk.web:
                    print(f"  [{i}] {getattr(chunk.web, 'title', 'Unknown')}: {getattr(chunk.web, 'uri', '')}")
        else:
            print("  No grounding chunks found")
    
    print("\n✓ Test completed successfully with grounding!")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
