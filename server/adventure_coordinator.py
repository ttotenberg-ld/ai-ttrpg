from models import PlayerCharacterRead
from typing import Optional

def gather_pc_info_for_adventure(pc: PlayerCharacterRead) -> dict:
    """Extracts key information from a PlayerCharacter model for adventure generation."""
    if not pc:
        return {}

    pc_details = {
        "name": pc.name,
        "strength": pc.strength,
        "dexterity": pc.dexterity,
        "intelligence": pc.intelligence,
        "charisma": pc.charisma,
        "personality_traits": pc.personality_traits,
        "skills": pc.skills,
        "inventory": pc.inventory,
        # Potentially add more derived information here later
    }
    # Filter out None values to keep the prompt clean
    return {k: v for k, v in pc_details.items() if v is not None}


def construct_adventure_generation_prompt(
    pc_info: dict,
    player_preferences: Optional[dict] = None # Placeholder for future use
) -> str:
    """Constructs a prompt for an LLM to generate a TTRPG adventure."""
    
    prompt = f"""You are an expert Tabletop RPG Game Master.
Generate a short, unique TTRPG adventure with an overarching story, a clear end goal, and 1 to 3 distinct encounters.

The adventure should be tailored for the following player character:

Character Name: {pc_info.get('name', 'An unnamed hero')}
"
""
    if pc_info.get('strength'):
        prompt += f"Strength: {pc_info['strength']}\n"
    if pc_info.get('dexterity'):
        prompt += f"Dexterity: {pc_info['dexterity']}\n"
    if pc_info.get('intelligence'):
        prompt += f"Intelligence: {pc_info['intelligence']}\n"
    if pc_info.get('charisma'):
        prompt += f"Charisma: {pc_info['charisma']}\n"
    if pc_info.get('personality_traits'):
        prompt += f"Personality Traits: {pc_info['personality_traits']}\n"
    if pc_info.get('skills'):
        prompt += f"Skills: {pc_info['skills']}\n"
    if pc_info.get('inventory'):
        prompt += f"Inventory: {pc_info['inventory']}\n"
    
    prompt += "\nConsider these character details when designing the adventure and its challenges.
"

    if player_preferences:
        prompt += "\nConsider the following player preferences:\n"
        if player_preferences.get('theme'):
            prompt += f"- Preferred Theme: {player_preferences['theme']}\n"
        if player_preferences.get('difficulty'):
            prompt += f"- Preferred Difficulty: {player_preferences['difficulty']}\n"
        if player_preferences.get('length'):
            prompt += f"- Preferred Length: {player_preferences['length']}\n"

    prompt += "\nPlease provide the adventure in the following structure:
1.  **Adventure Title:** (A catchy title for the adventure)
2.  **Overall Goal:** (What the player needs to achieve to complete the adventure)
3.  **Encounter 1:**
    *   **Description:** (Details of the first encounter, scene setting)
    *   **Challenge/Objective:** (What the player needs to do or overcome)
    *   **Potential Outcomes/Paths:** (Brief ideas on how it might resolve)
4.  **Encounter 2 (Optional):**
    *   **Description:**
    *   **Challenge/Objective:**
    *   **Potential Outcomes/Paths:**
5.  **Encounter 3 (Optional):**
    *   **Description:**
    *   **Challenge/Objective:**
    *   **Potential Outcomes/Paths:**
6.  **Conclusion:** (How the adventure wraps up upon achieving the goal)

Focus on creativity and replayability. Encounters can be varied (e.g., conversations, puzzles, escape rooms, battles that can be resolved in multiple ways).
"""
    return prompt 