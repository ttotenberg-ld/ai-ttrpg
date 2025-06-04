import random
from typing import Optional

from models import Reward, RewardType, PlayerCharacterRead # Assuming PlayerCharacterRead might be used for context later

# Predefined list of possible rewards. This could be much more extensive and data-driven.
PREDEFINED_REWARDS = [
    Reward(reward_type=RewardType.EQUIPMENT, name="Dagger of Swiftness", description="A lightweight dagger that feels quick in your hand.", value="Dagger of Swiftness"),
    Reward(reward_type=RewardType.EQUIPMENT, name="Shield of Minor Warding", description="A sturdy shield that hums with faint protective magic.", value="Shield of Minor Warding"),
    Reward(reward_type=RewardType.NEW_SKILL, name="Keen Eye", description="You've learned to spot details others might miss. You gain advantage on Perception checks related to finding hidden objects.", value="skill_keen_eye"),
    Reward(reward_type=RewardType.NEW_SKILL, name="Persuasive Tongue", description="You've honed your ability to sway others with words. You gain proficiency in Persuasion.", value="skill_persuasion_proficiency"),
    Reward(reward_type=RewardType.STAT_UPGRADE, name="Minor Strength Boost", description="Your physical training pays off. Your Strength increases by 1.", target_stat="strength", value="+1"),
    Reward(reward_type=RewardType.STAT_UPGRADE, name="Minor Dexterity Boost", description="You feel more agile. Your Dexterity increases by 1.", target_stat="dexterity", value="+1"),
    Reward(reward_type=RewardType.STAT_UPGRADE, name="Minor Intelligence Boost", description="Your studies sharpen your mind. Your Intelligence increases by 1.", target_stat="intelligence", value="+1"),
    Reward(reward_type=RewardType.STAT_UPGRADE, name="Minor Charisma Boost", description="Your presence becomes more commanding. Your Charisma increases by 1.", target_stat="charisma", value="+1"),
]

def generate_adventure_reward(pc: Optional[PlayerCharacterRead] = None) -> Reward:
    """
    Generates a reward for completing an adventure.
    Currently selects randomly from a predefined list.
    Could be expanded to consider PC level, adventure difficulty, or use LLM for suggestions.
    """
    # pc parameter is there for future use (e.g., tailoring reward to PC class/stats/level)
    return random.choice(PREDEFINED_REWARDS)

# Placeholder for how the reward would be translated into an update for the PC model
# This logic would live where the reward is actually *applied* (e.g., in an API endpoint handler)
# For now, the API endpoint for updating PCs (`PATCH /pcs/{pc_id}`) can take the `PlayerCharacterUpdate` 
# model, and the frontend would construct that update based on the `Reward` data.

# Example: If reward is STAT_UPGRADE, target_stat="strength", value="+1"
# The client would then prepare a PlayerCharacterUpdate like: { strength: current_strength + 1 }
# If reward is EQUIPMENT, value="Dagger of Swiftness"
# The client would prepare PlayerCharacterUpdate like: { inventory: current_inventory + ", Dagger of Swiftness" } 