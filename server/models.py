from typing import Optional, List
from enum import Enum
from datetime import datetime

from sqlmodel import Field, SQLModel, Relationship


# --- Enum Definitions (moved to top for proper import order) ---

class RewardType(str, Enum):
    EQUIPMENT = "equipment"
    NEW_SKILL = "new_skill"
    STAT_UPGRADE = "stat_upgrade"
    # Could add CURRENCY, CONSUMABLE_ITEM, etc.


class EquipmentType(str, Enum):
    """Standardized equipment types for character items"""
    WEAPON = "weapon"
    ARMOR = "armor"
    ACCESSORY = "accessory"
    CONSUMABLE = "consumable"
    TOOL = "tool"
    MISC = "misc"


class SkillCategory(str, Enum):
    """Categories for organizing skills"""
    COMBAT = "combat"
    SOCIAL = "social"
    EXPLORATION = "exploration"
    CRAFTING = "crafting"
    MAGIC = "magic"
    KNOWLEDGE = "knowledge"
    SURVIVAL = "survival"


# --- User Models ---

class UserBase(SQLModel):
    username: str = Field(index=True, unique=True)
    email: str = Field(unique=True)


class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    email_verified: bool = Field(default=False)
    is_active: bool = Field(default=True)
    failed_login_attempts: int = Field(default=0)
    locked_until: Optional[datetime] = None
    last_login: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    player_characters: List["PlayerCharacter"] = Relationship(back_populates="user")
    user_sessions: List["UserSession"] = Relationship(back_populates="user")
    password_reset_tokens: List["PasswordResetToken"] = Relationship(back_populates="user")
    character_versions: List["CharacterVersion"] = Relationship(back_populates="user")


class UserSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    refresh_token: str = Field(unique=True, index=True)
    expires_at: datetime
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: Optional[User] = Relationship(back_populates="user_sessions")


class PasswordResetToken(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    token: str = Field(unique=True, index=True)
    expires_at: datetime
    is_used: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: "User" = Relationship(back_populates="password_reset_tokens")


class UserCreate(UserBase):
    password: str


class UserProfile(SQLModel):
    """User profile information that can be viewed and updated"""
    username: str
    email: str
    email_verified: bool
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class UserProfileUpdate(SQLModel):
    """User profile fields that can be updated"""
    username: Optional[str] = None
    email: Optional[str] = None


class PlayerCharacterBase(SQLModel):
    name: str
    # Stats - using simple integers for now
    strength: int = Field(default=10)
    dexterity: int = Field(default=10)
    intelligence: int = Field(default=10)
    charisma: int = Field(default=10)
    # Personality & Skills - simple strings for now
    personality_traits: Optional[str] = None
    skills: Optional[str] = None # Could be a JSON or comma-separated string
    # Inventory
    inventory: Optional[str] = None # Could be JSON or comma-separated string


class PlayerCharacter(PlayerCharacterBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    # Versioning and meta fields
    version: int = Field(default=1)
    is_template: bool = Field(default=False)
    is_public: bool = Field(default=False)
    experience_points: int = Field(default=0)
    character_level: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    user: Optional[User] = Relationship(back_populates="player_characters")
    equipment: List["Equipment"] = Relationship(back_populates="character")
    versions: List["CharacterVersion"] = Relationship(back_populates="character")
    character_skills: List["CharacterSkill"] = Relationship(back_populates="character")


class PlayerCharacterCreate(PlayerCharacterBase):
    pass


class PlayerCharacterRead(PlayerCharacterBase):
    id: int
    user_id: int


class PlayerCharacterUpdate(SQLModel): # Using SQLModel directly for all optional fields
    name: Optional[str] = None
    strength: Optional[int] = None
    dexterity: Optional[int] = None
    intelligence: Optional[int] = None
    charisma: Optional[int] = None
    personality_traits: Optional[str] = None
    skills: Optional[str] = None
    inventory: Optional[str] = None
    # Versioning and meta fields
    version: Optional[int] = None
    is_template: Optional[bool] = None
    is_public: Optional[bool] = None
    experience_points: Optional[int] = None
    character_level: Optional[int] = None


class Equipment(SQLModel, table=True):
    """Equipment items that can be owned and equipped by characters"""
    id: Optional[int] = Field(default=None, primary_key=True)
    character_id: int = Field(foreign_key="playercharacter.id")
    name: str
    description: str
    item_type: EquipmentType = Field(description="Equipment type: weapon, armor, accessory, consumable, tool, misc")
    stat_modifiers: Optional[str] = Field(default=None, description="JSON string of stat modifications")
    is_equipped: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    character: Optional["PlayerCharacter"] = Relationship(back_populates="equipment")


class EquipmentCreate(SQLModel):
    """Model for creating new equipment"""
    name: str
    description: str
    item_type: EquipmentType
    stat_modifiers: Optional[str] = None
    is_equipped: bool = Field(default=False)


class EquipmentRead(SQLModel):
    """Model for reading equipment data"""
    id: int
    character_id: int
    name: str
    description: str
    item_type: EquipmentType
    stat_modifiers: Optional[str] = None
    is_equipped: bool
    created_at: datetime


class EquipmentUpdate(SQLModel):
    """Model for updating equipment"""
    name: Optional[str] = None
    description: Optional[str] = None
    item_type: Optional[EquipmentType] = None
    stat_modifiers: Optional[str] = None
    is_equipped: Optional[bool] = None


class CharacterVersion(SQLModel, table=True):
    """Tracks character history and changes over time"""
    id: Optional[int] = Field(default=None, primary_key=True)
    character_id: int = Field(foreign_key="playercharacter.id")
    user_id: int = Field(foreign_key="user.id")
    version_number: int
    character_data: str = Field(description="JSON snapshot of character state")
    change_description: str = Field(description="Description of what changed in this version")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    character: Optional["PlayerCharacter"] = Relationship(back_populates="versions")
    user: Optional["User"] = Relationship(back_populates="character_versions")


class CharacterVersionCreate(SQLModel):
    """Model for creating character version snapshots"""
    character_data: str
    change_description: str


class CharacterVersionRead(SQLModel):
    """Model for reading character version data"""
    id: int
    character_id: int
    user_id: int
    version_number: int
    character_data: str
    change_description: str
    created_at: datetime


# --- Adventure and Game State Models (Not necessarily DB tables yet) ---

class AdventureEncounter(SQLModel): # Using SQLModel for consistency, can be BaseModel
    description: str
    challenge_objective: str
    potential_outcomes: Optional[str] = None
    image_url: Optional[str] = None # URL to the generated image for this encounter
    background_music_url: Optional[str] = None # URL to background music for this encounter

class AdventureDefinition(SQLModel):
    title: str
    overall_goal: str
    encounters: List[AdventureEncounter]
    conclusion: str

class AdventureState(SQLModel):
    adventure_definition: AdventureDefinition
    current_encounter_index: int = 0
    pc_id: int # Added to link the adventure state to the player character
    # Potentially add more state: PC status during adventure, world state changes, etc.
    # For now, this is a very basic representation.


class PlayerActionRequest(SQLModel):
    action_text: str
    # Optional fields if frontend/player suggests a specific check
    # The GM AI will ultimately decide if a check is truly needed and its parameters
    stat_to_check: Optional[str] = None # e.g., "strength", "dexterity", "intelligence", "charisma"
    # skills_involved: Optional[List[str]] = None # Could be more complex later
    suggested_dc: Optional[int] = None
    # For simplicity, advantage/disadvantage could be determined by GM or future game logic

class ActionOutcomeResponse(SQLModel):
    narration: str
    skill_check_result_desc: Optional[str] = None # Description from SkillCheckResult if a check was made
    skill_check_success: Optional[bool] = None # Added to explicitly pass success status
    audio_narration_url: Optional[str] = None # URL to the generated audio narration
    sound_effect_url: Optional[str] = None # URL to a relevant sound effect
    # Potentially, encounter_advanced: bool, new_encounter_details, game_over: bool, etc.


# --- Reward System Models ---

class Reward(SQLModel): # Not a table, but a structure for reward data
    reward_type: RewardType
    name: str # e.g., "Sword of Slaying", "Lockpicking Finesse", "Strength Boost"
    description: str # "A finely crafted sword, +1 to attack.", "You gain proficiency in lockpicking.", "Your Strength increases by 1."
    # Details for applying the reward:
    target_stat: Optional[str] = None # e.g., "strength", "dexterity" for stat_upgrade
    value: Optional[str] = None # e.g., "+1", "proficiency_lockpicking", "Dagger of Swiftness"
    # For equipment, 'value' could be the item name to be added to inventory.
    # For skills, 'value' could be the skill name/identifier.
    # For stat_upgrade, 'target_stat' is the stat and 'value' could be the amount (e.g., "+1").
    experience_points: Optional[int] = None


# --- Player Preferences for Adventure Generation ---
class PlayerPreferences(SQLModel):
    theme: Optional[str] = None # e.g., "fantasy", "mystery", "sci-fi"
    difficulty: Optional[str] = None # e.g., "easy", "medium", "hard"
    length: Optional[str] = None # e.g., "short", "medium", "long" (1-3 encounters is already set by default)
    # Other potential preferences could be added here 

class Skill(SQLModel, table=True):
    """Base skill definitions with prerequisites and descriptions"""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: str
    category: SkillCategory
    prerequisite_skills: Optional[str] = Field(default=None, description="JSON array of required skill names")
    minimum_level: int = Field(default=1, description="Minimum character level required")
    stat_requirements: Optional[str] = Field(default=None, description="JSON object of minimum stat requirements")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    character_skills: List["CharacterSkill"] = Relationship(back_populates="skill")


class CharacterSkill(SQLModel, table=True):
    """Tracks skills acquired by characters with proficiency levels"""
    id: Optional[int] = Field(default=None, primary_key=True)
    character_id: int = Field(foreign_key="playercharacter.id")
    skill_id: int = Field(foreign_key="skill.id")
    proficiency_level: int = Field(default=1, description="Skill proficiency level (1-5)")
    experience_points: int = Field(default=0, description="XP invested in this skill")
    acquired_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None
    
    # Relationships
    character: Optional["PlayerCharacter"] = Relationship(back_populates="character_skills")
    skill: Optional[Skill] = Relationship(back_populates="character_skills")


class SkillCreate(SQLModel):
    """Model for creating new skill definitions"""
    name: str
    description: str
    category: SkillCategory
    prerequisite_skills: Optional[str] = None
    minimum_level: int = Field(default=1)
    stat_requirements: Optional[str] = None


class SkillRead(SQLModel):
    """Model for reading skill data"""
    id: int
    name: str
    description: str
    category: SkillCategory
    prerequisite_skills: Optional[str] = None
    minimum_level: int
    stat_requirements: Optional[str] = None
    created_at: datetime


class CharacterSkillCreate(SQLModel):
    """Model for adding skills to characters"""
    skill_id: int
    proficiency_level: int = Field(default=1)


class CharacterSkillRead(SQLModel):
    """Model for reading character skill data"""
    id: int
    character_id: int
    skill_id: int
    proficiency_level: int
    experience_points: int
    acquired_at: datetime
    last_used: Optional[datetime] = None
    skill: Optional[SkillRead] = None


class CharacterSkillUpdate(SQLModel):
    """Model for updating character skills"""
    proficiency_level: Optional[int] = None
    experience_points: Optional[int] = None
    last_used: Optional[datetime] = None 