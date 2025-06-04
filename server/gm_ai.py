import os
import random # Added for dice rolls
from openai import OpenAI
from typing import Optional
from models import SQLModel # Added to use SkillCheckResult with SQLModel features
import pyttsx3 # Added for TTS
import uuid # Added for unique filenames for TTS
import asyncio # Added for running blocking TTS in a thread

# Define SkillCheckResult class early to avoid forward reference issues
class SkillCheckResult(SQLModel): # Using SQLModel for potential future use, can be BaseModel
    success: bool
    roll_value: int
    modifier_applied: int
    dc: int
    description: str

# Ensure your OPENAI_API_KEY environment variable is set
# client = OpenAI()
# For testing without an API key or for local models, you might initialize differently
# or use a mock. For now, we'll assume the key is set for a real call.

# It's good practice to initialize the client once if possible, 
# but for a simple function, it can be initialized inside if preferred.
# We will initialize it outside to follow best practices if this module grows.

try:
    client = OpenAI()
    # Test the client initialization by making a simple call, e.g., listing models (optional)
    # client.models.list() # This line can be commented out after initial setup check
    OPENAI_API_KEY_SET = True
except Exception as e: # Catching a broad exception as OpenAI client init can fail for various reasons
    print(f"OpenAI API key not found or client failed to initialize: {e}")
    print("Please set the OPENAI_API_KEY environment variable.")
    print("AI functionality will be mocked or limited.")
    client = None
    OPENAI_API_KEY_SET = False

# --- Text-to-Speech ---
_tts_engine = None
TTS_ENABLED = False
TTS_AUDIO_DIR = "generated_audio_files/tts" # Directory to store TTS audio files, relative to server/

try:
    _tts_engine = pyttsx3.init()
    # Example: set to the first available voice if needed, platform dependent
    # voices = _tts_engine.getProperty('voices')
    # if voices: _tts_engine.setProperty('voice', voices[0].id)
    TTS_ENABLED = True
    print("TTS Engine Initialized (pyttsx3).")
    # Ensure TTS audio directory exists when module is loaded and TTS is enabled
    if not os.path.exists(TTS_AUDIO_DIR):
        os.makedirs(TTS_AUDIO_DIR)
    print(f"TTS audio will be saved to: {os.path.abspath(TTS_AUDIO_DIR)}")
except Exception as e:
    print(f"Failed to initialize pyttsx3 TTS engine or create TTS directory: {e}. TTS will be disabled.")
    TTS_ENABLED = False
    _tts_engine = None # Ensure engine is None if init fails

async def transcribe_audio_file_to_text(audio_file_path: str) -> str:
    """
    Transcribes an audio file to text using OpenAI's Whisper model.
    """
    if not OPENAI_API_KEY_SET or not client:
        print("OpenAI client not available. Cannot transcribe audio.")
        # In a real scenario, you might raise an exception or return a specific error message.
        return "Error: Audio transcription service not available."

    try:
        with open(audio_file_path, "rb") as audio_file:
            transcription = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        return transcription.text
    except Exception as e:
        print(f"Error during audio transcription: {e}")
        return f"Error transcribing audio: {str(e)}"

async def generate_speech_audio(text: str, npc_voice_description: Optional[str] = None) -> Optional[str]:
    """
    Generates speech from text using pyttsx3, saves it to a file, and returns the file path.
    Runs blocking I/O in a separate thread.
    Returns the path to the generated audio file (e.g., generated_audio_files/tts/some_uuid.mp3) 
    or None if TTS is disabled or an error occurs.
    """
    if not TTS_ENABLED or not _tts_engine:
        print(f"TTS (generate_speech_audio): TTS DISABLED. Input text: {text[:50]}...")
        return None

    try:
        # Ensure directory exists (created during TTS init)
        # TTS_AUDIO_DIR is "generated_audio_files/tts"
        # os.makedirs(TTS_AUDIO_DIR, exist_ok=True) # Already done in TTS init

        filename = f"{uuid.uuid4().hex}.mp3"
        file_path = os.path.join(TTS_AUDIO_DIR, filename) # e.g., server/generated_audio_files/tts/someuid.mp3

        print(f"TTS (generate_speech_audio): Preparing to save to: {file_path}")
        if npc_voice_description:
            print(f"(As NPC with voice: {npc_voice_description})")
            # Limited voice selection logic would go here for pyttsx3
        
        await asyncio.to_thread(_tts_engine.save_to_file, text, file_path)
        await asyncio.to_thread(_tts_engine.runAndWait) # runAndWait is essential for file to be written
        
        print(f"TTS (generate_speech_audio): Saved audio to {file_path}")
        return file_path 
    except Exception as e:
        print(f"Error during TTS audio generation: {e}")
        return None

async def generate_adventure_from_prompt(prompt: str) -> str:
    """Sends a prompt to an OpenAI model and returns the adventure story."""
    if not OPENAI_API_KEY_SET or not client:
        # Fallback or mock response if API key is not set
        return """
        Adventure Title: The Mockingbird's Secret
        Overall Goal: Retrieve the stolen Mockingbird amulet from the thieving magpie.
        Encounter 1:
            Description: You start in a quiet forest clearing. A weeping willow sways gently. You notice oversized bird tracks.
            Challenge/Objective: Follow the tracks to find the magpie's nest.
            Potential Outcomes/Paths: Success leads to the nest. Failure might involve losing the trail or a minor beast encounter.
        Conclusion: Retrieving the amulet restores peace to the Whispering Woods.
        """

    try:
        # Using a chat model like gpt-3.5-turbo or gpt-4
        # Adjust model and parameters as needed
        completion = await client.chat.completions.create(
            model="gpt-3.5-turbo", 
            messages=[
                {"role": "system", "content": "You are a creative and engaging Tabletop RPG Game Master."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7, # Controls randomness: higher is more random
            max_tokens=1500  # Adjust based on expected length
        )
        
        ai_response = completion.choices[0].message.content
        if not ai_response:
            return "Error: AI model returned an empty response."
        return ai_response.strip()
    
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        # Return a more structured error or the mock response in case of API failure
        return f"Error from AI: {str(e)}\n\nFallback Adventure:\n" + generate_adventure_from_prompt("") # Call itself for the mock

# Example of a simple narration call (can be expanded)
async def narrate_action_outcome(
    scene_description: str,
    pc_action: str,
    skill_check_result: Optional[SkillCheckResult] = None,
    # Potentially add pc_info: dict for more context for the AI
) -> str:
    """Prompts the AI to narrate the outcome of a player's action, considering a skill check."""
    if not OPENAI_API_KEY_SET or not client:
        mock_narration = f"Mock narration for action: '{pc_action}' in scene: '{scene_description}'."
        if skill_check_result:
            mock_narration += f" Skill check: {skill_check_result.description}"
        mock_narration += " The story progresses... [Example NPC, calm voice]: \"Well done, adventurer.\""
        # speak_text_placeholder(mock_narration, npc_voice_description="calm voice (example)") # conceptual call
        return mock_narration

    prompt_parts = [
        f"You are a master storyteller and TTRPG Game Master. Narrate the outcome of the player character\'s action within the current scene.",
        f"Current Scene: {scene_description}",
        f"Player Character attempts to: {pc_action}"
    ]

    if skill_check_result:
        prompt_parts.append(
            f"A skill check was performed with the following result: {skill_check_result.description}"
        )
        if skill_check_result.success:
            prompt_parts.append("The action succeeded. Describe how this success unfolds creatively.")
        else:
            prompt_parts.append("The action failed. Describe the consequences or how the failure manifests in an interesting way.")
    else:
        prompt_parts.append("This action does not require a skill check. Describe the outcome of this automatic action.")
    
    prompt_parts.append(
        "If an NPC speaks, clearly indicate their dialogue. You can also optionally describe the NPC's tone or manner of speaking "
        "(e.g., [Grizzled Guard, gruff voice], [Mysterious Stranger, whispering], [Shopkeeper, cheerful tone]). "
        "This description will assist a Text-to-Speech engine or voice actor."
    )
    prompt_parts.append("Keep the narration engaging and concise (1-3 paragraphs typically). Focus on the immediate consequences and setup for the next player decision if appropriate.")

    full_prompt = "\n\n".join(prompt_parts)

    try:
        completion = await client.chat.completions.create(
            model="gpt-3.5-turbo", 
            messages=[
                {"role": "system", "content": "You are a creative and engaging Tabletop RPG Game Master narrating player actions. Provide voice cues for NPCs like [Character Name, voice description]: \"Dialogue\""}, 
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.7,
            max_tokens=400 
        )
        narration = completion.choices[0].message.content
        final_narration = narration.strip() if narration else "The AI seems unsure how that went..."
        
        # Conceptual: If we had a way to parse out npc_voice_description from final_narration:
        # speak_text_placeholder(final_narration, npc_voice_description=parsed_voice_cue)
        # For now, the frontend would receive the full text with cues.
        return final_narration
    except Exception as e:
        print(f"Error during action outcome narration: {e}")
        # speak_text_placeholder(f"The story takes an unexpected turn... (AI Error: {str(e)})", npc_voice_description="error tone")
        return f"The story takes an unexpected turn... (AI Error: {str(e)})"

# Old narrate_scene can be removed or kept if it serves a different purpose (e.g., general scene setting without direct action)
# For now, let's assume narrate_action_outcome is the primary function for player turns.
# async def narrate_scene(description: str, pc_action: Optional[str] = None) -> str: ... (keeping it commented if we need it later)

# --- Dice Rolling and Skill Checks ---

def roll_dice(dice_notation: str) -> int:
    """Simulates a dice roll based on standard notation (e.g., '1d20', '2d6', '1d4+1')."""
    try:
        num_dice_str, rest = dice_notation.lower().split('d')
        num_dice = int(num_dice_str) if num_dice_str else 1
        
        modifier = 0
        if '+' in rest:
            sides_str, mod_str = rest.split('+')
            modifier = int(mod_str)
        elif '-' in rest:
            sides_str, mod_str = rest.split('-')
            modifier = -int(mod_str)
        else:
            sides_str = rest
            
        sides = int(sides_str)
        if sides <= 0 or num_dice <=0:
            raise ValueError("Number of dice and sides must be positive.")

        total_roll = sum(random.randint(1, sides) for _ in range(num_dice))
        return total_roll + modifier
    except ValueError as e:
        print(f"Invalid dice notation: {dice_notation}. Error: {e}")
        # Return a default roll or raise the error, depending on desired handling
        return random.randint(1, 20) # Default to 1d20 on error
    except Exception as e:
        print(f"Unexpected error in roll_dice for {dice_notation}: {e}")
        return random.randint(1, 20) # Default to 1d20

def perform_skill_check(
    pc_modifier: int, 
    dc: int, 
    dice_to_roll: str = "1d20",
    advantage: bool = False, # Roll twice, take higher
    disadvantage: bool = False # Roll twice, take lower
) -> SkillCheckResult:
    """Performs a skill check (e.g., 1d20 + modifier vs DC)."""
    
    if advantage and disadvantage:
        # Per D&D 5e rules, advantage and disadvantage cancel each other out
        advantage = False
        disadvantage = False

    roll1 = roll_dice(dice_to_roll)
    final_roll = roll1

    if advantage:
        roll2 = roll_dice(dice_to_roll)
        final_roll = max(roll1, roll2)
        roll_description = f"Rolled {dice_to_roll} with advantage ({roll1}, {roll2}), took {final_roll}"
    elif disadvantage:
        roll2 = roll_dice(dice_to_roll)
        final_roll = min(roll1, roll2)
        roll_description = f"Rolled {dice_to_roll} with disadvantage ({roll1}, {roll2}), took {final_roll}"
    else:
        roll_description = f"Rolled {dice_to_roll}, result {final_roll}"

    total_value = final_roll + pc_modifier
    success = total_value >= dc

    description = f"{roll_description}. Modifier: {pc_modifier}. Total: {total_value} vs DC {dc}. Success: {success}."
    
    return SkillCheckResult(
        success=success,
        roll_value=final_roll,
        modifier_applied=pc_modifier,
        dc=dc,
        description=description
    )

# The AI GM would need to be prompted to call for these checks or provide DC.
# Example usage (would be integrated into game loop):
# strength_modifier = (pc_stats.strength - 10) // 2 # Example modifier calculation
# check_result = perform_skill_check(pc_modifier=strength_modifier, dc=15)
# print(check_result.description) 