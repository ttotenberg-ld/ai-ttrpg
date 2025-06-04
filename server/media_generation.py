import os
from typing import Optional
from openai import OpenAI
import uuid
import requests # For downloading the image

# Initialize OpenAI client
# Ensure your OPENAI_API_KEY environment variable is set.
try:
    client = OpenAI()
    OPENAI_API_KEY_SET = True
except Exception as e:
    print(f"OpenAI API key not found or client failed to initialize for DALL-E: {e}")
    print("Please set the OPENAI_API_KEY environment variable.")
    print("Image generation functionality will be disabled.")
    client = None
    OPENAI_API_KEY_SET = False

# Directory to store generated images, relative to the server's root.
# If main.py is in server/, this means server/generated_media/images/
IMAGE_GENERATION_DIR = "generated_media/images"
SFX_GENERATION_DIR = "generated_media/sfx" # Directory for generated sound effects
MUSIC_GENERATION_DIR = "generated_media/music" # Directory for generated background music

def ensure_image_dir_exists():
    # This path needs to be relative to where the server process is running.
    # If server runs from project root (e.g., /ai-ttrpg), then path is "server/generated_media/images"
    # If server runs from server/ (e.g., /ai-ttrpg/server), then path is "generated_media/images"
    # For consistency with gm_ai.py and main.py, we'll assume the server CWD is the project root,
    # or paths will be constructed relative to `main.py`'s location.
    # For now, let's make it relative to this file, and main.py will handle full path construction for serving.
    # Let's define it as relative from the server root for now.
    # The actual directory creation will be handled in main.py's startup.
    # This function can just return the defined path.
    # No, this function *should* create it based on its own file location if needed for standalone testing,
    # but `main.py` will primarily be responsible for ensuring it exists at server startup.
    
    # Path relative to this file (media_generation.py inside server/)
    # dir_path = os.path.join(os.path.dirname(__file__), IMAGE_GENERATION_DIR)
    # This causes issues if __file__ is not server/media_generation.py
    # Let's stick to the relative path from server root, as defined by IMAGE_GENERATION_DIR
    
    # The directory `server/generated_media/images` should be created by `main.py`.
    # This function will just use `IMAGE_GENERATION_DIR` assuming it's ready.
    pass # Directory creation handled by main.py

async def generate_encounter_image(prompt_text: str, image_size: str = "1024x1024", image_quality: str = "standard") -> Optional[str]:
    """
    Generates an image using DALL-E based on the prompt text, saves it, 
    and returns the relative path to the saved image (e.g., "generated_media/images/filename.png").
    Returns None if image generation is disabled or fails.
    """
    if not OPENAI_API_KEY_SET or not client:
        print("Image generation (DALL-E) is disabled due to missing API key or client init failure.")
        return None

    # The directory IMAGE_GENERATION_DIR ("generated_media/images") 
    # is expected to be created by main.py relative to the server root (e.g., server/generated_media/images).
    # os.makedirs(IMAGE_GENERATION_DIR, exist_ok=True) # main.py will handle this.

    try:
        print(f"Generating DALL-E image for prompt: '{prompt_text[:100]}...'")
        response = await client.images.generate(
            model="dall-e-3", # Or "dall-e-2" if preferred
            prompt=f"Digital art, fantasy tabletop RPG style: {prompt_text}",
            size=image_size, # "1024x1024", "1024x1792", "1792x1024" for DALL-E 3
            quality=image_quality, # "standard" or "hd"
            n=1, # Generate one image
            response_format="url" # Get a temporary URL to download the image
        )
        
        image_url = response.data[0].url
        if not image_url:
            print("DALL-E response did not contain an image URL.")
            return None

        # Download the image from the URL
        image_response = requests.get(image_url, stream=True)
        image_response.raise_for_status() # Raise an exception for HTTP errors

        # Generate a unique filename
        filename = f"{uuid.uuid4().hex}.png" 
        # The file path will be like "generated_media/images/some_uuid.png"
        # This path is relative to the `server` directory if `IMAGE_GENERATION_DIR` is just "generated_media/images"
        # and `main.py` is in `server/`.
        file_path = os.path.join(IMAGE_GENERATION_DIR, filename)
        
        # Ensure the full directory path exists (main.py should handle base creation)
        # os.makedirs(os.path.dirname(file_path), exist_ok=True) # This is problematic. IMAGE_GENERATION_DIR is the dir.

        with open(file_path, "wb") as f:
            for chunk in image_response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"Saved DALL-E image to {file_path}")
        # Return the relative path, which will be used by main.py to construct the full URL
        return file_path # e.g., "generated_media/images/filename.png"

    except Exception as e:
        print(f"Error generating or saving image using DALL-E: {e}")
        return None

async def generate_sound_effect(prompt_text: str) -> Optional[str]:
    """
    Placeholder for sound effect generation.
    In a real implementation, this would call a sound generation AI.
    For now, it logs the request and might return a path to a dummy sound file.
    Saves to SFX_GENERATION_DIR (e.g., "generated_media/sfx/filename.mp3")
    Returns the relative path or None.
    """
    print(f"Sound effect generation requested for prompt: '{prompt_text[:100]}...'")
    
    # Ensure the directory exists (main.py should primarily handle this on startup)
    # Path is relative to server root, e.g. server/generated_media/sfx
    # os.makedirs(SFX_GENERATION_DIR, exist_ok=True) # main.py will do this

    # TODO: Replace with actual sound generation AI call
    # For now, simulate by checking if a placeholder file exists or just returning a name.
    # Let's assume we have a placeholder file that main.py will ensure is available.
    placeholder_filename = "placeholder_effect.mp3"
    placeholder_path = os.path.join(SFX_GENERATION_DIR, placeholder_filename)

    # To make this runnable without a real placeholder file, we can just return the path
    # and let the frontend handle a 404 if it's not there. Or, create a dummy one.
    # For simplicity in this step, we'll just return the expected path.
    # A more robust placeholder would create a tiny silent mp3 if it doesn't exist.

    print(f"Placeholder: Would generate sound effect. Returning path: {placeholder_path}")
    # In a real scenario, you'd save the generated file here with a unique name.
    # e.g., filename = f"{uuid.uuid4().hex}.mp3"
    # actual_file_path = os.path.join(SFX_GENERATION_DIR, filename)
    # ... save AI generated sound to actual_file_path ...
    # return actual_file_path
    
    return placeholder_path # e.g. "generated_media/sfx/placeholder_effect.mp3"

async def generate_background_music(prompt_text: str) -> Optional[str]:
    """
    Placeholder for background music generation.
    In a real implementation, this would call a music generation AI.
    For now, it logs the request and returns a path to a dummy music file.
    Saves to MUSIC_GENERATION_DIR (e.g., "generated_media/music/filename.mp3")
    Returns the relative path or None.
    """
    print(f"Background music generation requested for prompt: '{prompt_text[:100]}...'")
    
    # Ensure the directory exists (main.py should primarily handle this on startup)
    # os.makedirs(MUSIC_GENERATION_DIR, exist_ok=True) # main.py will do this

    # TODO: Replace with actual music generation AI call
    placeholder_filename = "placeholder_music.mp3"
    placeholder_path = os.path.join(MUSIC_GENERATION_DIR, placeholder_filename)

    print(f"Placeholder: Would generate background music. Returning path: {placeholder_path}")
    # In a real scenario, you'd save the generated file here with a unique name.
    # e.g., filename = f"{uuid.uuid4().hex}.mp3"
    # actual_file_path = os.path.join(MUSIC_GENERATION_DIR, filename)
    # ... save AI generated music to actual_file_path ...
    # return actual_file_path
    
    return placeholder_path # e.g. "generated_media/music/placeholder_music.mp3"

# Example Usage (for testing this module directly, if needed):
# if __name__ == "__main__":
#     async def main_test():
#         # This assumes IMAGE_GENERATION_DIR is relative to the server directory
#         # and the server directory is the current working directory or that
#         # this script is run from server/
#         if not os.path.exists(IMAGE_GENERATION_DIR):
#             os.makedirs(IMAGE_GENERATION_DIR)
#         
#         test_prompt = "A brave knight facing a fierce dragon in a dark cave, treasure chest in the background."
#         image_file = await generate_encounter_image(test_prompt)
#         if image_file:
#             print(f"Test image generated: {image_file}")
#         else:
#             print("Test image generation failed.")
#
#     asyncio.run(main_test())
# Need to import asyncio for the test main
# import asyncio 