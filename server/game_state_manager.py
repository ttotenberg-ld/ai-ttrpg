import re
from typing import Dict, Optional, List
from uuid import uuid4

from models import AdventureDefinition, AdventureEncounter, AdventureState

# In-memory store for active adventure states. Key: adventure_id (str), Value: AdventureState
# This would need to be replaced with a more persistent solution (e.g., Redis, DB) for a real app.
_active_adventures: Dict[str, AdventureState] = {}

def parse_adventure_text_to_definition(adventure_text: str) -> Optional[AdventureDefinition]:
    """Rudimentary parser for AI-generated adventure text."""
    try:
        title_match = re.search(r"Adventure Title: (.+)", adventure_text)
        goal_match = re.search(r"Overall Goal: (.+)", adventure_text)
        conclusion_match = re.search(r"Conclusion: (.+)", adventure_text, re.DOTALL)

        if not (title_match and goal_match and conclusion_match):
            print("Error parsing: Missing title, goal, or conclusion.")
            return None

        title = title_match.group(1).strip()
        overall_goal = goal_match.group(1).strip()
        conclusion = conclusion_match.group(1).strip()

        encounters_raw = re.findall(r"Encounter \d+: (.+?)(?=Encounter \d+:|Conclusion:)", adventure_text, re.DOTALL)
        
        parsed_encounters: List[AdventureEncounter] = []
        for enc_text in encounters_raw:
            desc_match = re.search(r"Description: (.+?)(Challenge/Objective:)", enc_text, re.DOTALL)
            obj_match = re.search(r"Challenge/Objective: (.+?)(Potential Outcomes/Paths:|$)", enc_text, re.DOTALL)
            outcomes_match = re.search(r"Potential Outcomes/Paths: (.+)", enc_text, re.DOTALL)

            if desc_match and obj_match:
                parsed_encounters.append(
                    AdventureEncounter(
                        description=desc_match.group(1).strip(),
                        challenge_objective=obj_match.group(1).strip(),
                        potential_outcomes=outcomes_match.group(1).strip() if outcomes_match else None
                    )
                )
            else:
                print(f"Warning: Could not fully parse an encounter: {enc_text[:100]}...")
        
        if not parsed_encounters:
            print("Error parsing: No encounters found or parsed.")
            # Fallback: create a single encounter from the general text if possible
            # This is a very basic fallback
            if len(adventure_text) > 100 : # Arbitrary length check
                 parsed_encounters.append(AdventureEncounter(description=adventure_text[:200], challenge_objective="Survive!"))
            else:
                return None


        return AdventureDefinition(
            title=title,
            overall_goal=overall_goal,
            encounters=parsed_encounters,
            conclusion=conclusion
        )
    except Exception as e:
        print(f"Exception during adventure text parsing: {e}")
        return None

def start_adventure(adventure_definition: AdventureDefinition, pc_id: int) -> str:
    """Initializes a new adventure state with a PC ID and returns its ID."""
    adventure_id = str(uuid4())
    state = AdventureState(
        adventure_definition=adventure_definition, 
        current_encounter_index=0,
        pc_id=pc_id
    )
    _active_adventures[adventure_id] = state
    return adventure_id

def get_adventure_state(adventure_id: str) -> Optional[AdventureState]:
    return _active_adventures.get(adventure_id)

def get_current_encounter(adventure_id: str) -> Optional[AdventureEncounter]:
    state = get_adventure_state(adventure_id)
    if state and 0 <= state.current_encounter_index < len(state.adventure_definition.encounters):
        return state.adventure_definition.encounters[state.current_encounter_index]
    return None

def advance_to_next_encounter(adventure_id: str) -> Optional[AdventureEncounter]:
    state = get_adventure_state(adventure_id)
    if not state:
        return None
    
    if state.current_encounter_index < len(state.adventure_definition.encounters) - 1:
        state.current_encounter_index += 1
        _active_adventures[adventure_id] = state # Update the state in the store
        return get_current_encounter(adventure_id)
    else:
        # Adventure finished (no more encounters)
        return None 

def end_adventure(adventure_id: str):
    """Removes an adventure from the active store."""
    if adventure_id in _active_adventures:
        del _active_adventures[adventure_id] 