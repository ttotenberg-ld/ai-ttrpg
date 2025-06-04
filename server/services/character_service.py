"""
Character validation service with business rules and validation logic.
Handles stat point allocation, equipment compatibility, skill prerequisites, and progression rules.
"""

import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from sqlmodel import Session

from ..models import (
    PlayerCharacter, Equipment, EquipmentType, Skill, CharacterSkill,
    SkillCategory, PlayerCharacterCreate, PlayerCharacterUpdate, CharacterVersion
)


class CharacterValidationError(Exception):
    """Custom exception for character validation errors"""
    pass


class CharacterValidationService:
    """Service for validating character data and business rules"""
    
    # Configuration constants
    DEFAULT_STAT_POINTS = 40  # Total points to distribute across stats
    MIN_STAT_VALUE = 8
    MAX_STAT_VALUE = 18
    STAT_POINT_COST = {  # Cost per stat point above minimum
        10: 1, 11: 1, 12: 1, 13: 1, 14: 2, 15: 2, 16: 3, 17: 4, 18: 5
    }
    MAX_PROFICIENCY_LEVEL = 5
    BASE_SKILL_XP_COST = 100  # XP cost for first proficiency level
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def validate_character_creation(self, character_data: PlayerCharacterCreate) -> Dict[str, any]:
        """
        Validate character creation data with all business rules.
        Returns validation result with errors if any.
        """
        errors = []
        warnings = []
        
        # Validate stats
        stat_errors = self._validate_stat_allocation(
            character_data.strength,
            character_data.dexterity, 
            character_data.intelligence,
            character_data.charisma
        )
        errors.extend(stat_errors)
        
        # Validate name
        name_errors = self._validate_character_name(character_data.name)
        errors.extend(name_errors)
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def validate_character_update(self, 
                                character: PlayerCharacter, 
                                update_data: PlayerCharacterUpdate) -> Dict[str, any]:
        """
        Validate character updates with progression rules.
        """
        errors = []
        warnings = []
        
        # If stats are being updated, validate new allocation
        if any([update_data.strength, update_data.dexterity, 
                update_data.intelligence, update_data.charisma]):
            
            new_strength = update_data.strength or character.strength
            new_dexterity = update_data.dexterity or character.dexterity
            new_intelligence = update_data.intelligence or character.intelligence
            new_charisma = update_data.charisma or character.charisma
            
            stat_errors = self._validate_stat_allocation(
                new_strength, new_dexterity, new_intelligence, new_charisma
            )
            errors.extend(stat_errors)
            
            # Check if stat increases are valid based on character level
            if update_data.strength and update_data.strength > character.strength:
                level_errors = self._validate_stat_increase(
                    character, "strength", character.strength, update_data.strength
                )
                errors.extend(level_errors)
        
        # Validate level progression
        if update_data.character_level and update_data.character_level != character.character_level:
            level_errors = self._validate_level_progression(
                character, update_data.character_level
            )
            errors.extend(level_errors)
        
        # Validate experience points
        if update_data.experience_points is not None:
            xp_errors = self._validate_experience_points(
                character, update_data.experience_points
            )
            errors.extend(xp_errors)
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def validate_skill_acquisition(self, 
                                 character: PlayerCharacter, 
                                 skill_id: int, 
                                 proficiency_level: int = 1) -> Dict[str, any]:
        """
        Validate skill acquisition with prerequisite checks.
        """
        errors = []
        warnings = []
        
        # Get skill data
        skill = self.db.get(Skill, skill_id)
        if not skill:
            errors.append(f"Skill with ID {skill_id} not found")
            return {"valid": False, "errors": errors, "warnings": warnings}
        
        # Check level requirements
        if character.character_level < skill.minimum_level:
            errors.append(
                f"Character level {character.character_level} is below required "
                f"level {skill.minimum_level} for skill '{skill.name}'"
            )
        
        # Check stat requirements
        if skill.stat_requirements:
            stat_errors = self._validate_skill_stat_requirements(character, skill)
            errors.extend(stat_errors)
        
        # Check prerequisite skills
        if skill.prerequisite_skills:
            prereq_errors = self._validate_skill_prerequisites(character, skill)
            errors.extend(prereq_errors)
        
        # Check proficiency level
        if proficiency_level < 1 or proficiency_level > self.MAX_PROFICIENCY_LEVEL:
            errors.append(
                f"Proficiency level must be between 1 and {self.MAX_PROFICIENCY_LEVEL}"
            )
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "skill": skill
        }
    
    def validate_equipment_compatibility(self, 
                                       character: PlayerCharacter, 
                                       equipment: Equipment) -> Dict[str, any]:
        """
        Validate equipment compatibility with character.
        """
        errors = []
        warnings = []
        
        # Check level requirements for equipment
        if equipment.stat_modifiers:
            try:
                modifiers = json.loads(equipment.stat_modifiers)
                required_level = modifiers.get("required_level", 1)
                if character.character_level < required_level:
                    errors.append(
                        f"Character level {character.character_level} is below "
                        f"required level {required_level} for '{equipment.name}'"
                    )
            except json.JSONDecodeError:
                warnings.append(f"Invalid stat modifiers format for '{equipment.name}'")
        
        # Check equipment slot conflicts (only one item equipped per type)
        if equipment.is_equipped and equipment.item_type in [EquipmentType.WEAPON, EquipmentType.ARMOR]:
            existing_equipped = [
                eq for eq in character.equipment 
                if eq.is_equipped and eq.item_type == equipment.item_type and eq.id != equipment.id
            ]
            if existing_equipped:
                warnings.append(
                    f"Character already has {equipment.item_type.value} equipped. "
                    f"Equipping '{equipment.name}' will unequip existing items."
                )
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def calculate_total_stat_cost(self, strength: int, dexterity: int, 
                                intelligence: int, charisma: int) -> int:
        """Calculate total point cost for stat allocation"""
        total_cost = 0
        for stat_value in [strength, dexterity, intelligence, charisma]:
            if stat_value < self.MIN_STAT_VALUE:
                continue
            for value in range(self.MIN_STAT_VALUE, min(stat_value + 1, self.MAX_STAT_VALUE + 1)):
                if value in self.STAT_POINT_COST:
                    total_cost += self.STAT_POINT_COST.get(value, 1)
        return total_cost
    
    def calculate_skill_xp_cost(self, current_level: int, target_level: int) -> int:
        """Calculate XP cost to advance skill from current to target level"""
        if target_level <= current_level:
            return 0
        
        total_cost = 0
        for level in range(current_level + 1, target_level + 1):
            total_cost += self.BASE_SKILL_XP_COST * level
        return total_cost
    
    def get_character_available_skills(self, character: PlayerCharacter) -> List[Dict]:
        """Get skills available for character based on level and prerequisites"""
        all_skills = self.db.query(Skill).all()
        available_skills = []
        
        for skill in all_skills:
            validation = self.validate_skill_acquisition(character, skill.id)
            if validation["valid"]:
                available_skills.append({
                    "skill": skill,
                    "can_acquire": True
                })
            else:
                available_skills.append({
                    "skill": skill,
                    "can_acquire": False,
                    "reasons": validation["errors"]
                })
        
        return available_skills
    
    # Private validation methods
    
    def _validate_stat_allocation(self, strength: int, dexterity: int, 
                                intelligence: int, charisma: int) -> List[str]:
        """Validate stat point allocation"""
        errors = []
        
        # Check stat ranges
        stats = {"strength": strength, "dexterity": dexterity, 
                "intelligence": intelligence, "charisma": charisma}
        
        for stat_name, value in stats.items():
            if value < self.MIN_STAT_VALUE:
                errors.append(f"{stat_name.capitalize()} cannot be below {self.MIN_STAT_VALUE}")
            elif value > self.MAX_STAT_VALUE:
                errors.append(f"{stat_name.capitalize()} cannot exceed {self.MAX_STAT_VALUE}")
        
        # Check total point allocation
        total_cost = self.calculate_total_stat_cost(strength, dexterity, intelligence, charisma)
        if total_cost > self.DEFAULT_STAT_POINTS:
            errors.append(
                f"Total stat points ({total_cost}) exceed allowed limit ({self.DEFAULT_STAT_POINTS})"
            )
        
        return errors
    
    def _validate_character_name(self, name: str) -> List[str]:
        """Validate character name"""
        errors = []
        
        if not name or len(name.strip()) < 2:
            errors.append("Character name must be at least 2 characters long")
        elif len(name) > 50:
            errors.append("Character name cannot exceed 50 characters")
        
        return errors
    
    def _validate_stat_increase(self, character: PlayerCharacter, 
                              stat_name: str, old_value: int, new_value: int) -> List[str]:
        """Validate stat increases based on character progression"""
        errors = []
        
        increase = new_value - old_value
        if increase > 0:
            # Characters can increase stats by 1 point every 5 levels
            max_increases = character.character_level // 5
            current_increases = self._count_stat_increases(character)
            
            if current_increases + increase > max_increases:
                errors.append(
                    f"Character can only increase stats {max_increases} times at level "
                    f"{character.character_level} (currently used {current_increases})"
                )
        
        return errors
    
    def _validate_level_progression(self, character: PlayerCharacter, new_level: int) -> List[str]:
        """Validate character level progression"""
        errors = []
        
        if new_level < character.character_level:
            errors.append("Character level cannot be decreased")
        elif new_level > character.character_level + 1:
            errors.append("Character can only advance one level at a time")
        
        # Check XP requirements (simplified calculation)
        required_xp = self._calculate_xp_for_level(new_level)
        if character.experience_points < required_xp:
            errors.append(
                f"Insufficient experience points. Need {required_xp}, have {character.experience_points}"
            )
        
        return errors
    
    def _validate_experience_points(self, character: PlayerCharacter, new_xp: int) -> List[str]:
        """Validate experience point changes"""
        errors = []
        
        if new_xp < 0:
            errors.append("Experience points cannot be negative")
        elif new_xp < character.experience_points:
            errors.append("Experience points cannot be decreased")
        
        return errors
    
    def _validate_skill_stat_requirements(self, character: PlayerCharacter, skill: Skill) -> List[str]:
        """Validate skill stat requirements"""
        errors = []
        
        try:
            requirements = json.loads(skill.stat_requirements)
            
            stat_map = {
                "strength": character.strength,
                "dexterity": character.dexterity,
                "intelligence": character.intelligence,
                "charisma": character.charisma
            }
            
            for stat_name, min_value in requirements.items():
                if stat_name in stat_map and stat_map[stat_name] < min_value:
                    errors.append(
                        f"Skill '{skill.name}' requires {stat_name} of {min_value}, "
                        f"character has {stat_map[stat_name]}"
                    )
        
        except (json.JSONDecodeError, TypeError):
            # Invalid JSON format, skip validation
            pass
        
        return errors
    
    def _validate_skill_prerequisites(self, character: PlayerCharacter, skill: Skill) -> List[str]:
        """Validate skill prerequisites"""
        errors = []
        
        try:
            prerequisites = json.loads(skill.prerequisite_skills)
            if not isinstance(prerequisites, list):
                return errors
            
            character_skill_names = [
                cs.skill.name for cs in character.character_skills 
                if cs.skill
            ]
            
            for prereq_name in prerequisites:
                if prereq_name not in character_skill_names:
                    errors.append(
                        f"Skill '{skill.name}' requires prerequisite skill '{prereq_name}'"
                    )
        
        except (json.JSONDecodeError, TypeError):
            # Invalid JSON format, skip validation
            pass
        
        return errors
    
    def _count_stat_increases(self, character: PlayerCharacter) -> int:
        """Count total stat increases for character (simplified implementation)"""
        # This would typically track stat increases from character history
        # For now, assume base stats of 10 and count increases
        base_total = 40  # 4 stats * 10 each
        current_total = (character.strength + character.dexterity + 
                        character.intelligence + character.charisma)
        return max(0, current_total - base_total)
    
    def _calculate_xp_for_level(self, level: int) -> int:
        """Calculate XP required for a given level"""
        # Simple XP progression: level * 1000
        return (level - 1) * 1000 


class CharacterTemplateService:
    """Service for managing character templates"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.validation_service = CharacterValidationService(db_session)
    
    def create_character_template(self, 
                                user_id: int,
                                template_data: PlayerCharacterCreate,
                                description: Optional[str] = None,
                                is_public: bool = False) -> Dict[str, any]:
        """
        Create a character template from character data.
        Templates are validated but don't need to follow progression rules.
        """
        # Validate template data (less strict than regular characters)
        validation = self._validate_template_creation(template_data)
        if not validation["valid"]:
            return {
                "success": False,
                "errors": validation["errors"],
                "template": None
            }
        
        # Create template character
        template = PlayerCharacter(
            user_id=user_id,
            name=template_data.name,
            strength=template_data.strength,
            dexterity=template_data.dexterity,
            intelligence=template_data.intelligence,
            charisma=template_data.charisma,
            personality_traits=template_data.personality_traits,
            skills=template_data.skills,
            inventory=template_data.inventory,
            is_template=True,
            is_public=is_public,
            version=1,
            experience_points=0,
            character_level=1
        )
        
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        
        return {
            "success": True,
            "errors": [],
            "template": template
        }
    
    def create_character_from_template(self, 
                                     template_id: int, 
                                     user_id: int,
                                     character_name: Optional[str] = None) -> Dict[str, any]:
        """
        Create a new character based on a template.
        """
        # Get template
        template = self.db.get(PlayerCharacter, template_id)
        if not template:
            return {
                "success": False,
                "errors": ["Template not found"],
                "character": None
            }
        
        if not template.is_template:
            return {
                "success": False,
                "errors": ["Specified character is not a template"],
                "character": None
            }
        
        # Check if template is accessible
        if not template.is_public and template.user_id != user_id:
            return {
                "success": False,
                "errors": ["Template is not accessible"],
                "character": None
            }
        
        # Create character from template
        character_data = PlayerCharacterCreate(
            name=character_name or f"{template.name} Copy",
            strength=template.strength,
            dexterity=template.dexterity,
            intelligence=template.intelligence,
            charisma=template.charisma,
            personality_traits=template.personality_traits,
            skills=template.skills,
            inventory=template.inventory
        )
        
        # Validate character creation
        validation = self.validation_service.validate_character_creation(character_data)
        if not validation["valid"]:
            return {
                "success": False,
                "errors": validation["errors"],
                "character": None
            }
        
        # Create new character
        character = PlayerCharacter(
            user_id=user_id,
            name=character_data.name,
            strength=character_data.strength,
            dexterity=character_data.dexterity,
            intelligence=character_data.intelligence,
            charisma=character_data.charisma,
            personality_traits=character_data.personality_traits,
            skills=character_data.skills,
            inventory=character_data.inventory,
            is_template=False,
            is_public=False,
            version=1,
            experience_points=0,  # Reset XP and level for copies
            character_level=1
        )
        
        self.db.add(character)
        self.db.commit()
        self.db.refresh(character)
        
        # Copy template equipment if any
        if template.equipment:
            self._copy_template_equipment(template, character)
        
        # Copy template skills if any
        if template.character_skills:
            self._copy_template_skills(template, character)
        
        return {
            "success": True,
            "errors": [],
            "character": character
        }
    
    def convert_character_to_template(self, 
                                    character_id: int, 
                                    user_id: int,
                                    template_name: Optional[str] = None,
                                    is_public: bool = False) -> Dict[str, any]:
        """
        Convert an existing character into a template.
        """
        # Get character
        character = self.db.get(PlayerCharacter, character_id)
        if not character:
            return {
                "success": False,
                "errors": ["Character not found"],
                "template": None
            }
        
        if character.user_id != user_id:
            return {
                "success": False,
                "errors": ["Not authorized to convert this character"],
                "template": None
            }
        
        if character.is_template:
            return {
                "success": False,
                "errors": ["Character is already a template"],
                "template": None
            }
        
        # Create template from character
        template_data = PlayerCharacterCreate(
            name=template_name or f"{character.name} Template",
            strength=character.strength,
            dexterity=character.dexterity,
            intelligence=character.intelligence,
            charisma=character.charisma,
            personality_traits=character.personality_traits,
            skills=character.skills,
            inventory=character.inventory
        )
        
        return self.create_character_template(
            user_id=user_id,
            template_data=template_data,
            is_public=is_public
        )
    
    def get_user_templates(self, user_id: int) -> List[PlayerCharacter]:
        """Get all templates created by a user"""
        return self.db.query(PlayerCharacter).filter(
            PlayerCharacter.user_id == user_id,
            PlayerCharacter.is_template == True
        ).all()
    
    def get_public_templates(self, 
                           category_filter: Optional[str] = None,
                           search_term: Optional[str] = None) -> List[PlayerCharacter]:
        """Get public templates with optional filtering"""
        query = self.db.query(PlayerCharacter).filter(
            PlayerCharacter.is_template == True,
            PlayerCharacter.is_public == True
        )
        
        if search_term:
            query = query.filter(
                PlayerCharacter.name.contains(search_term)
            )
        
        return query.all()
    
    def update_template(self, 
                       template_id: int, 
                       user_id: int,
                       update_data: PlayerCharacterUpdate) -> Dict[str, any]:
        """Update a character template"""
        template = self.db.get(PlayerCharacter, template_id)
        if not template:
            return {
                "success": False,
                "errors": ["Template not found"],
                "template": None
            }
        
        if template.user_id != user_id:
            return {
                "success": False,
                "errors": ["Not authorized to update this template"],
                "template": None
            }
        
        if not template.is_template:
            return {
                "success": False,
                "errors": ["Specified character is not a template"],
                "template": None
            }
        
        # Validate template update (more lenient than character updates)
        validation = self._validate_template_update(template, update_data)
        if not validation["valid"]:
            return {
                "success": False,
                "errors": validation["errors"],
                "template": None
            }
        
        # Apply updates
        for field, value in update_data.dict(exclude_unset=True).items():
            if hasattr(template, field):
                setattr(template, field, value)
        
        template.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(template)
        
        return {
            "success": True,
            "errors": [],
            "template": template
        }
    
    def delete_template(self, template_id: int, user_id: int) -> Dict[str, any]:
        """Delete a character template"""
        template = self.db.get(PlayerCharacter, template_id)
        if not template:
            return {
                "success": False,
                "errors": ["Template not found"]
            }
        
        if template.user_id != user_id:
            return {
                "success": False,
                "errors": ["Not authorized to delete this template"]
            }
        
        if not template.is_template:
            return {
                "success": False,
                "errors": ["Specified character is not a template"]
            }
        
        # Delete associated equipment and skills
        for equipment in template.equipment:
            self.db.delete(equipment)
        
        for skill in template.character_skills:
            self.db.delete(skill)
        
        # Delete template
        self.db.delete(template)
        self.db.commit()
        
        return {
            "success": True,
            "errors": []
        }
    
    def share_template(self, template_id: int, user_id: int, is_public: bool) -> Dict[str, any]:
        """Update template sharing status"""
        template = self.db.get(PlayerCharacter, template_id)
        if not template:
            return {
                "success": False,
                "errors": ["Template not found"]
            }
        
        if template.user_id != user_id:
            return {
                "success": False,
                "errors": ["Not authorized to modify this template"]
            }
        
        if not template.is_template:
            return {
                "success": False,
                "errors": ["Specified character is not a template"]
            }
        
        template.is_public = is_public
        template.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(template)
        
        return {
            "success": True,
            "errors": [],
            "template": template
        }
    
    # Private helper methods
    
    def _validate_template_creation(self, template_data: PlayerCharacterCreate) -> Dict[str, any]:
        """Validate template creation (more lenient than character validation)"""
        errors = []
        warnings = []
        
        # Basic name validation
        if not template_data.name or len(template_data.name.strip()) < 2:
            errors.append("Template name must be at least 2 characters long")
        elif len(template_data.name) > 50:
            errors.append("Template name cannot exceed 50 characters")
        
        # Basic stat validation (allow more flexibility for templates)
        stats = {
            "strength": template_data.strength,
            "dexterity": template_data.dexterity,
            "intelligence": template_data.intelligence,
            "charisma": template_data.charisma
        }
        
        for stat_name, value in stats.items():
            if value < 1:
                errors.append(f"{stat_name.capitalize()} cannot be below 1")
            elif value > 20:  # Allow higher stats for templates
                warnings.append(f"{stat_name.capitalize()} is very high ({value})")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _validate_template_update(self, 
                                template: PlayerCharacter, 
                                update_data: PlayerCharacterUpdate) -> Dict[str, any]:
        """Validate template updates (more lenient than character updates)"""
        errors = []
        warnings = []
        
        # Name validation
        if update_data.name is not None:
            if not update_data.name or len(update_data.name.strip()) < 2:
                errors.append("Template name must be at least 2 characters long")
            elif len(update_data.name) > 50:
                errors.append("Template name cannot exceed 50 characters")
        
        # Basic stat validation for templates
        stats_to_check = {}
        if update_data.strength is not None:
            stats_to_check["strength"] = update_data.strength
        if update_data.dexterity is not None:
            stats_to_check["dexterity"] = update_data.dexterity
        if update_data.intelligence is not None:
            stats_to_check["intelligence"] = update_data.intelligence
        if update_data.charisma is not None:
            stats_to_check["charisma"] = update_data.charisma
        
        for stat_name, value in stats_to_check.items():
            if value < 1:
                errors.append(f"{stat_name.capitalize()} cannot be below 1")
            elif value > 20:
                warnings.append(f"{stat_name.capitalize()} is very high ({value})")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _copy_template_equipment(self, template: PlayerCharacter, character: PlayerCharacter):
        """Copy equipment from template to new character"""
        for equipment in template.equipment:
            new_equipment = Equipment(
                character_id=character.id,
                name=equipment.name,
                description=equipment.description,
                item_type=equipment.item_type,
                stat_modifiers=equipment.stat_modifiers,
                is_equipped=equipment.is_equipped
            )
            self.db.add(new_equipment)
        
        self.db.commit()
    
    def _copy_template_skills(self, template: PlayerCharacter, character: PlayerCharacter):
        """Copy skills from template to new character"""
        for char_skill in template.character_skills:
            new_char_skill = CharacterSkill(
                character_id=character.id,
                skill_id=char_skill.skill_id,
                proficiency_level=char_skill.proficiency_level,
                experience_points=char_skill.experience_points
            )
            self.db.add(new_char_skill)
        
        self.db.commit()


class CharacterSharingService:
    """Service for managing character sharing and public character browsing"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.validation_service = CharacterValidationService(db_session)
    
    def share_character(self, 
                       character_id: int, 
                       user_id: int, 
                       is_public: bool) -> Dict[str, any]:
        """
        Update character sharing status (public/private).
        """
        character = self.db.get(PlayerCharacter, character_id)
        if not character:
            return {
                "success": False,
                "errors": ["Character not found"],
                "character": None
            }
        
        if character.user_id != user_id:
            return {
                "success": False,
                "errors": ["Not authorized to modify this character"],
                "character": None
            }
        
        if character.is_template:
            return {
                "success": False,
                "errors": ["Use template sharing service for character templates"],
                "character": None
            }
        
        character.is_public = is_public
        character.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(character)
        
        return {
            "success": True,
            "errors": [],
            "character": character
        }
    
    def get_public_characters(self, 
                            search_term: Optional[str] = None,
                            level_min: Optional[int] = None,
                            level_max: Optional[int] = None,
                            stat_filter: Optional[Dict[str, int]] = None,
                            limit: int = 50,
                            offset: int = 0) -> Dict[str, any]:
        """
        Get public characters with optional filtering and pagination.
        """
        query = self.db.query(PlayerCharacter).filter(
            PlayerCharacter.is_public == True,
            PlayerCharacter.is_template == False
        )
        
        # Apply filters
        if search_term:
            query = query.filter(
                PlayerCharacter.name.contains(search_term)
            )
        
        if level_min is not None:
            query = query.filter(PlayerCharacter.character_level >= level_min)
        
        if level_max is not None:
            query = query.filter(PlayerCharacter.character_level <= level_max)
        
        if stat_filter:
            for stat_name, min_value in stat_filter.items():
                if hasattr(PlayerCharacter, stat_name):
                    query = query.filter(getattr(PlayerCharacter, stat_name) >= min_value)
        
        # Get total count for pagination
        total_count = query.count()
        
        # Apply pagination
        characters = query.offset(offset).limit(limit).all()
        
        return {
            "success": True,
            "characters": characters,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(characters) < total_count
        }
    
    def get_character_for_viewing(self, 
                                character_id: int, 
                                viewer_user_id: Optional[int] = None) -> Dict[str, any]:
        """
        Get character details for viewing with proper access control.
        Allows viewing if:
        - Character is owned by the viewer
        - Character is public
        - Character is a public template
        """
        character = self.db.get(PlayerCharacter, character_id)
        if not character:
            return {
                "success": False,
                "errors": ["Character not found"],
                "character": None
            }
        
        # Check access permissions
        can_view = False
        access_reason = ""
        
        if viewer_user_id and character.user_id == viewer_user_id:
            can_view = True
            access_reason = "owner"
        elif character.is_public:
            can_view = True
            access_reason = "public"
        
        if not can_view:
            return {
                "success": False,
                "errors": ["Character is not accessible"],
                "character": None
            }
        
        return {
            "success": True,
            "errors": [],
            "character": character,
            "access_reason": access_reason
        }
    
    def get_user_shared_characters(self, user_id: int) -> List[PlayerCharacter]:
        """Get all public characters shared by a specific user"""
        return self.db.query(PlayerCharacter).filter(
            PlayerCharacter.user_id == user_id,
            PlayerCharacter.is_public == True,
            PlayerCharacter.is_template == False
        ).all()
    
    def get_character_inspiration(self, 
                                character_id: int, 
                                user_id: int) -> Dict[str, any]:
        """
        Get a simplified view of a public character for inspiration.
        Removes sensitive information while keeping useful data.
        """
        result = self.get_character_for_viewing(character_id, user_id)
        if not result["success"]:
            return result
        
        character = result["character"]
        
        # Create inspiration data (simplified character view)
        inspiration_data = {
            "name": character.name,
            "level": character.character_level,
            "stats": {
                "strength": character.strength,
                "dexterity": character.dexterity,
                "intelligence": character.intelligence,
                "charisma": character.charisma
            },
            "personality_traits": character.personality_traits,
            "skills": character.skills,
            "equipment_summary": self._get_equipment_summary(character),
            "skill_summary": self._get_skill_summary(character),
            "owner_id": character.user_id,
            "created_at": character.created_at
        }
        
        return {
            "success": True,
            "errors": [],
            "inspiration": inspiration_data
        }
    
    def copy_public_character(self, 
                            source_character_id: int, 
                            user_id: int,
                            new_character_name: str) -> Dict[str, any]:
        """
        Create a copy of a public character for the user.
        Similar to template system but for regular characters.
        """
        # Get source character
        result = self.get_character_for_viewing(source_character_id, user_id)
        if not result["success"]:
            return result
        
        source_character = result["character"]
        
        if source_character.user_id == user_id:
            return {
                "success": False,
                "errors": ["Cannot copy your own character - use the character duplication feature instead"],
                "character": None
            }
        
        # Create character data from source
        character_data = PlayerCharacterCreate(
            name=new_character_name,
            strength=source_character.strength,
            dexterity=source_character.dexterity,
            intelligence=source_character.intelligence,
            charisma=source_character.charisma,
            personality_traits=source_character.personality_traits,
            skills=source_character.skills,
            inventory=source_character.inventory
        )
        
        # Validate character creation
        validation = self.validation_service.validate_character_creation(character_data)
        if not validation["valid"]:
            return {
                "success": False,
                "errors": validation["errors"],
                "character": None
            }
        
        # Create new character
        new_character = PlayerCharacter(
            user_id=user_id,
            name=character_data.name,
            strength=character_data.strength,
            dexterity=character_data.dexterity,
            intelligence=character_data.intelligence,
            charisma=character_data.charisma,
            personality_traits=character_data.personality_traits,
            skills=character_data.skills,
            inventory=character_data.inventory,
            is_template=False,
            is_public=False,  # Copies are private by default
            version=1,
            experience_points=0,  # Reset XP and level for copies
            character_level=1
        )
        
        self.db.add(new_character)
        self.db.commit()
        self.db.refresh(new_character)
        
        # Copy basic equipment (not unique/magical items)
        self._copy_basic_equipment(source_character, new_character)
        
        return {
            "success": True,
            "errors": [],
            "character": new_character,
            "source_character_id": source_character_id
        }
    
    def get_character_sharing_stats(self, user_id: int) -> Dict[str, any]:
        """Get statistics about user's character sharing"""
        user_characters = self.db.query(PlayerCharacter).filter(
            PlayerCharacter.user_id == user_id,
            PlayerCharacter.is_template == False
        ).all()
        
        public_count = sum(1 for char in user_characters if char.is_public)
        private_count = len(user_characters) - public_count
        
        # Get view statistics (simplified - would need a views tracking system)
        stats = {
            "total_characters": len(user_characters),
            "public_characters": public_count,
            "private_characters": private_count,
            "sharing_ratio": round(public_count / len(user_characters) * 100, 1) if user_characters else 0
        }
        
        return {
            "success": True,
            "stats": stats
        }
    
    # Private helper methods
    
    def _get_equipment_summary(self, character: PlayerCharacter) -> List[Dict[str, str]]:
        """Get simplified equipment summary for inspiration"""
        equipment_summary = []
        for equipment in character.equipment:
            if equipment.is_equipped:
                equipment_summary.append({
                    "name": equipment.name,
                    "type": equipment.item_type.value,
                    "description": equipment.description[:100] + "..." if len(equipment.description) > 100 else equipment.description
                })
        return equipment_summary
    
    def _get_skill_summary(self, character: PlayerCharacter) -> List[Dict[str, any]]:
        """Get simplified skill summary for inspiration"""
        skill_summary = []
        for char_skill in character.character_skills:
            if char_skill.skill:
                skill_summary.append({
                    "name": char_skill.skill.name,
                    "category": char_skill.skill.category.value,
                    "proficiency_level": char_skill.proficiency_level
                })
        return skill_summary
    
    def _copy_basic_equipment(self, source_character: PlayerCharacter, new_character: PlayerCharacter):
        """Copy basic equipment from source to new character (excluding unique items)"""
        for equipment in source_character.equipment:
            # Only copy basic equipment types, not unique or magical items
            if equipment.item_type in [EquipmentType.WEAPON, EquipmentType.ARMOR, EquipmentType.TOOL]:
                # Check if it's a basic item (no stat modifiers indicating special properties)
                if not equipment.stat_modifiers or equipment.stat_modifiers == "{}":
                    new_equipment = Equipment(
                        character_id=new_character.id,
                        name=equipment.name,
                        description=equipment.description,
                        item_type=equipment.item_type,
                        stat_modifiers=equipment.stat_modifiers,
                        is_equipped=False  # Copies start unequipped
                    )
                    self.db.add(new_equipment)
        
        self.db.commit()


class CharacterVersioningService:
    """Service for managing character version history and snapshots"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.validation_service = CharacterValidationService(db_session)
    
    def create_character_snapshot(self, 
                                character_id: int, 
                                user_id: int,
                                change_description: str,
                                auto_increment_version: bool = True) -> Dict[str, any]:
        """
        Create a snapshot of the current character state.
        """
        character = self.db.get(PlayerCharacter, character_id)
        if not character:
            return {
                "success": False,
                "errors": ["Character not found"],
                "version": None
            }
        
        if character.user_id != user_id:
            return {
                "success": False,
                "errors": ["Not authorized to version this character"],
                "version": None
            }
        
        # Create complete character snapshot
        character_snapshot = self._create_character_snapshot_data(character)
        
        # Get next version number
        if auto_increment_version:
            latest_version = self.db.query(CharacterVersion).filter(
                CharacterVersion.character_id == character_id
            ).order_by(CharacterVersion.version_number.desc()).first()
            
            next_version = (latest_version.version_number + 1) if latest_version else 1
        else:
            next_version = character.version
        
        # Create version record
        version = CharacterVersion(
            character_id=character_id,
            user_id=user_id,
            version_number=next_version,
            character_data=json.dumps(character_snapshot),
            change_description=change_description
        )
        
        self.db.add(version)
        
        # Update character version if auto-incrementing
        if auto_increment_version:
            character.version = next_version
            character.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(version)
        
        return {
            "success": True,
            "errors": [],
            "version": version
        }
    
    def get_character_version_history(self, 
                                    character_id: int, 
                                    user_id: int,
                                    limit: Optional[int] = 20) -> Dict[str, any]:
        """
        Get version history for a character.
        """
        character = self.db.get(PlayerCharacter, character_id)
        if not character:
            return {
                "success": False,
                "errors": ["Character not found"],
                "versions": []
            }
        
        if character.user_id != user_id:
            return {
                "success": False,
                "errors": ["Not authorized to view this character's history"],
                "versions": []
            }
        
        query = self.db.query(CharacterVersion).filter(
            CharacterVersion.character_id == character_id
        ).order_by(CharacterVersion.version_number.desc())
        
        if limit:
            query = query.limit(limit)
        
        versions = query.all()
        
        # Add summary information for each version
        version_summaries = []
        for version in versions:
            try:
                snapshot_data = json.loads(version.character_data)
                summary = self._create_version_summary(version, snapshot_data)
                version_summaries.append(summary)
            except json.JSONDecodeError:
                # Handle corrupted version data
                version_summaries.append({
                    "version_id": version.id,
                    "version_number": version.version_number,
                    "change_description": version.change_description,
                    "created_at": version.created_at,
                    "error": "Corrupted version data"
                })
        
        return {
            "success": True,
            "errors": [],
            "versions": version_summaries,
            "total_versions": len(versions)
        }
    
    def restore_character_to_version(self, 
                                   character_id: int, 
                                   user_id: int,
                                   version_number: int,
                                   create_backup: bool = True) -> Dict[str, any]:
        """
        Restore character to a specific version.
        Optionally creates a backup of current state before restoring.
        """
        character = self.db.get(PlayerCharacter, character_id)
        if not character:
            return {
                "success": False,
                "errors": ["Character not found"],
                "character": None
            }
        
        if character.user_id != user_id:
            return {
                "success": False,
                "errors": ["Not authorized to restore this character"],
                "character": None
            }
        
        # Get target version
        target_version = self.db.query(CharacterVersion).filter(
            CharacterVersion.character_id == character_id,
            CharacterVersion.version_number == version_number
        ).first()
        
        if not target_version:
            return {
                "success": False,
                "errors": [f"Version {version_number} not found"],
                "character": None
            }
        
        # Create backup if requested
        if create_backup:
            backup_result = self.create_character_snapshot(
                character_id=character_id,
                user_id=user_id,
                change_description=f"Auto-backup before restoring to version {version_number}",
                auto_increment_version=True
            )
            if not backup_result["success"]:
                return {
                    "success": False,
                    "errors": ["Failed to create backup: " + str(backup_result["errors"])],
                    "character": None
                }
        
        # Restore character data
        try:
            snapshot_data = json.loads(target_version.character_data)
            restoration_result = self._restore_character_from_snapshot(character, snapshot_data)
            
            if not restoration_result["success"]:
                return restoration_result
            
            # Update version tracking
            character.version = target_version.version_number
            character.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(character)
            
            return {
                "success": True,
                "errors": [],
                "character": character,
                "restored_from_version": version_number
            }
            
        except json.JSONDecodeError:
            return {
                "success": False,
                "errors": ["Corrupted version data - cannot restore"],
                "character": None
            }
    
    def compare_character_versions(self, 
                                 character_id: int, 
                                 user_id: int,
                                 version_a: int, 
                                 version_b: int) -> Dict[str, any]:
        """
        Compare two character versions and return differences.
        """
        character = self.db.get(PlayerCharacter, character_id)
        if not character:
            return {
                "success": False,
                "errors": ["Character not found"],
                "comparison": None
            }
        
        if character.user_id != user_id:
            return {
                "success": False,
                "errors": ["Not authorized to compare versions for this character"],
                "comparison": None
            }
        
        # Get both versions
        version_a_record = self.db.query(CharacterVersion).filter(
            CharacterVersion.character_id == character_id,
            CharacterVersion.version_number == version_a
        ).first()
        
        version_b_record = self.db.query(CharacterVersion).filter(
            CharacterVersion.character_id == character_id,
            CharacterVersion.version_number == version_b
        ).first()
        
        if not version_a_record or not version_b_record:
            return {
                "success": False,
                "errors": ["One or both versions not found"],
                "comparison": None
            }
        
        try:
            data_a = json.loads(version_a_record.character_data)
            data_b = json.loads(version_b_record.character_data)
            
            comparison = self._compare_character_data(data_a, data_b, version_a, version_b)
            
            return {
                "success": True,
                "errors": [],
                "comparison": comparison
            }
            
        except json.JSONDecodeError:
            return {
                "success": False,
                "errors": ["Corrupted version data - cannot compare"],
                "comparison": None
            }
    
    def delete_character_version(self, 
                               character_id: int, 
                               user_id: int,
                               version_number: int) -> Dict[str, any]:
        """
        Delete a specific character version (except the current version).
        """
        character = self.db.get(PlayerCharacter, character_id)
        if not character:
            return {
                "success": False,
                "errors": ["Character not found"]
            }
        
        if character.user_id != user_id:
            return {
                "success": False,
                "errors": ["Not authorized to delete versions for this character"]
            }
        
        # Prevent deletion of current version
        if version_number == character.version:
            return {
                "success": False,
                "errors": ["Cannot delete the current character version"]
            }
        
        # Find and delete version
        version_to_delete = self.db.query(CharacterVersion).filter(
            CharacterVersion.character_id == character_id,
            CharacterVersion.version_number == version_number
        ).first()
        
        if not version_to_delete:
            return {
                "success": False,
                "errors": [f"Version {version_number} not found"]
            }
        
        self.db.delete(version_to_delete)
        self.db.commit()
        
        return {
            "success": True,
            "errors": []
        }
    
    def cleanup_old_versions(self, 
                           character_id: int, 
                           user_id: int,
                           keep_latest: int = 10) -> Dict[str, any]:
        """
        Clean up old character versions, keeping only the most recent ones.
        """
        character = self.db.get(PlayerCharacter, character_id)
        if not character:
            return {
                "success": False,
                "errors": ["Character not found"],
                "deleted_count": 0
            }
        
        if character.user_id != user_id:
            return {
                "success": False,
                "errors": ["Not authorized to clean up versions for this character"],
                "deleted_count": 0
            }
        
        # Get versions to delete (older than keep_latest, excluding current version)
        versions_to_delete = self.db.query(CharacterVersion).filter(
            CharacterVersion.character_id == character_id,
            CharacterVersion.version_number != character.version
        ).order_by(CharacterVersion.version_number.desc()).offset(keep_latest).all()
        
        deleted_count = len(versions_to_delete)
        
        for version in versions_to_delete:
            self.db.delete(version)
        
        self.db.commit()
        
        return {
            "success": True,
            "errors": [],
            "deleted_count": deleted_count
        }
    
    # Private helper methods
    
    def _create_character_snapshot_data(self, character: PlayerCharacter) -> Dict[str, any]:
        """Create a complete snapshot of character state"""
        snapshot = {
            "basic_info": {
                "name": character.name,
                "character_level": character.character_level,
                "experience_points": character.experience_points,
                "version": character.version,
                "is_template": character.is_template,
                "is_public": character.is_public
            },
            "stats": {
                "strength": character.strength,
                "dexterity": character.dexterity,
                "intelligence": character.intelligence,
                "charisma": character.charisma
            },
            "details": {
                "personality_traits": character.personality_traits,
                "skills": character.skills,
                "inventory": character.inventory
            },
            "equipment": [],
            "character_skills": [],
            "metadata": {
                "snapshot_created_at": datetime.utcnow().isoformat(),
                "character_created_at": character.created_at.isoformat(),
                "character_updated_at": character.updated_at.isoformat()
            }
        }
        
        # Include equipment
        for equipment in character.equipment:
            snapshot["equipment"].append({
                "name": equipment.name,
                "description": equipment.description,
                "item_type": equipment.item_type.value,
                "stat_modifiers": equipment.stat_modifiers,
                "is_equipped": equipment.is_equipped,
                "created_at": equipment.created_at.isoformat()
            })
        
        # Include character skills
        for char_skill in character.character_skills:
            skill_data = {
                "skill_id": char_skill.skill_id,
                "proficiency_level": char_skill.proficiency_level,
                "experience_points": char_skill.experience_points,
                "acquired_at": char_skill.acquired_at.isoformat()
            }
            if char_skill.last_used:
                skill_data["last_used"] = char_skill.last_used.isoformat()
            if char_skill.skill:
                skill_data["skill_name"] = char_skill.skill.name
                skill_data["skill_category"] = char_skill.skill.category.value
            
            snapshot["character_skills"].append(skill_data)
        
        return snapshot
    
    def _create_version_summary(self, version: CharacterVersion, snapshot_data: Dict) -> Dict[str, any]:
        """Create a summary of a character version"""
        basic_info = snapshot_data.get("basic_info", {})
        stats = snapshot_data.get("stats", {})
        
        return {
            "version_id": version.id,
            "version_number": version.version_number,
            "change_description": version.change_description,
            "created_at": version.created_at,
            "character_level": basic_info.get("character_level"),
            "experience_points": basic_info.get("experience_points"),
            "stats_total": sum(stats.values()) if stats else 0,
            "equipment_count": len(snapshot_data.get("equipment", [])),
            "skills_count": len(snapshot_data.get("character_skills", []))
        }
    
    def _restore_character_from_snapshot(self, character: PlayerCharacter, snapshot_data: Dict) -> Dict[str, any]:
        """Restore character data from a snapshot"""
        try:
            basic_info = snapshot_data.get("basic_info", {})
            stats = snapshot_data.get("stats", {})
            details = snapshot_data.get("details", {})
            
            # Restore basic character data
            character.name = basic_info.get("name", character.name)
            character.character_level = basic_info.get("character_level", character.character_level)
            character.experience_points = basic_info.get("experience_points", character.experience_points)
            character.is_template = basic_info.get("is_template", character.is_template)
            character.is_public = basic_info.get("is_public", character.is_public)
            
            # Restore stats
            character.strength = stats.get("strength", character.strength)
            character.dexterity = stats.get("dexterity", character.dexterity)
            character.intelligence = stats.get("intelligence", character.intelligence)
            character.charisma = stats.get("charisma", character.charisma)
            
            # Restore details
            character.personality_traits = details.get("personality_traits", character.personality_traits)
            character.skills = details.get("skills", character.skills)
            character.inventory = details.get("inventory", character.inventory)
            
            # Note: Equipment and character skills restoration would require more complex logic
            # For now, we'll restore the basic character data only
            # Full equipment/skills restoration could be added as an advanced feature
            
            return {
                "success": True,
                "errors": []
            }
            
        except Exception as e:
            return {
                "success": False,
                "errors": [f"Error restoring character: {str(e)}"]
            }
    
    def _compare_character_data(self, data_a: Dict, data_b: Dict, version_a: int, version_b: int) -> Dict[str, any]:
        """Compare two character data snapshots"""
        comparison = {
            "version_a": version_a,
            "version_b": version_b,
            "differences": {
                "basic_info": {},
                "stats": {},
                "details": {},
                "equipment": {"added": [], "removed": [], "modified": []},
                "skills": {"added": [], "removed": [], "modified": []}
            }
        }
        
        # Compare basic info
        basic_a = data_a.get("basic_info", {})
        basic_b = data_b.get("basic_info", {})
        for key in set(basic_a.keys()) | set(basic_b.keys()):
            if basic_a.get(key) != basic_b.get(key):
                comparison["differences"]["basic_info"][key] = {
                    "from": basic_a.get(key),
                    "to": basic_b.get(key)
                }
        
        # Compare stats
        stats_a = data_a.get("stats", {})
        stats_b = data_b.get("stats", {})
        for key in set(stats_a.keys()) | set(stats_b.keys()):
            if stats_a.get(key) != stats_b.get(key):
                comparison["differences"]["stats"][key] = {
                    "from": stats_a.get(key),
                    "to": stats_b.get(key)
                }
        
        # Compare details
        details_a = data_a.get("details", {})
        details_b = data_b.get("details", {})
        for key in set(details_a.keys()) | set(details_b.keys()):
            if details_a.get(key) != details_b.get(key):
                comparison["differences"]["details"][key] = {
                    "from": details_a.get(key),
                    "to": details_b.get(key)
                }
        
        return comparison


class CharacterImportExportService:
    """Service for importing and exporting character data with JSON serialization"""
    
    EXPORT_FORMAT_VERSION = "1.0.0"
    SUPPORTED_IMPORT_VERSIONS = ["1.0.0"]
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.validation_service = CharacterValidationService(db_session)
        self.versioning_service = CharacterVersioningService(db_session)
    
    def export_character(self, 
                        character_id: int, 
                        user_id: int,
                        include_equipment: bool = True,
                        include_skills: bool = True,
                        include_history: bool = False) -> Dict[str, any]:
        """
        Export character data to JSON format for sharing or backup.
        """
        character = self.db.get(PlayerCharacter, character_id)
        if not character:
            return {
                "success": False,
                "errors": ["Character not found"],
                "export_data": None
            }
        
        if character.user_id != user_id:
            return {
                "success": False,
                "errors": ["Not authorized to export this character"],
                "export_data": None
            }
        
        # Create export data structure
        export_data = {
            "format_version": self.EXPORT_FORMAT_VERSION,
            "exported_at": datetime.utcnow().isoformat(),
            "exported_by_user_id": user_id,
            "character": self._create_character_export_data(character, include_equipment, include_skills),
            "metadata": {
                "original_character_id": character.id,
                "export_options": {
                    "include_equipment": include_equipment,
                    "include_skills": include_skills,
                    "include_history": include_history
                }
            }
        }
        
        # Include version history if requested
        if include_history:
            history_result = self.versioning_service.get_character_version_history(
                character_id, user_id, limit=50
            )
            if history_result["success"]:
                export_data["version_history"] = history_result["versions"]
        
        return {
            "success": True,
            "errors": [],
            "export_data": export_data
        }
    
    def export_character_to_json_string(self, 
                                      character_id: int, 
                                      user_id: int,
                                      include_equipment: bool = True,
                                      include_skills: bool = True,
                                      include_history: bool = False,
                                      indent: int = 2) -> Dict[str, any]:
        """
        Export character to JSON string format.
        """
        export_result = self.export_character(
            character_id, user_id, include_equipment, include_skills, include_history
        )
        
        if not export_result["success"]:
            return export_result
        
        try:
            json_string = json.dumps(export_result["export_data"], indent=indent, default=str)
            return {
                "success": True,
                "errors": [],
                "json_string": json_string,
                "size_bytes": len(json_string.encode('utf-8'))
            }
        except Exception as e:
            return {
                "success": False,
                "errors": [f"Failed to serialize to JSON: {str(e)}"],
                "json_string": None
            }
    
    def import_character(self, 
                        user_id: int,
                        import_data: Dict[str, any],
                        character_name_override: Optional[str] = None,
                        import_as_template: bool = False) -> Dict[str, any]:
        """
        Import character from JSON data with validation.
        """
        # Validate import format
        format_validation = self._validate_import_format(import_data)
        if not format_validation["valid"]:
            return {
                "success": False,
                "errors": format_validation["errors"],
                "character": None
            }
        
        character_data = import_data["character"]
        
        # Create character creation data
        character_name = character_name_override or character_data["basic_info"]["name"]
        
        character_create_data = PlayerCharacterCreate(
            name=character_name,
            strength=character_data["stats"]["strength"],
            dexterity=character_data["stats"]["dexterity"],
            intelligence=character_data["stats"]["intelligence"],
            charisma=character_data["stats"]["charisma"],
            personality_traits=character_data["details"].get("personality_traits"),
            skills=character_data["details"].get("skills"),
            inventory=character_data["details"].get("inventory")
        )
        
        # Validate character creation
        validation = self.validation_service.validate_character_creation(character_create_data)
        if not validation["valid"]:
            return {
                "success": False,
                "errors": ["Character validation failed:"] + validation["errors"],
                "character": None
            }
        
        # Create character
        imported_character = PlayerCharacter(
            user_id=user_id,
            name=character_create_data.name,
            strength=character_create_data.strength,
            dexterity=character_create_data.dexterity,
            intelligence=character_create_data.intelligence,
            charisma=character_create_data.charisma,
            personality_traits=character_create_data.personality_traits,
            skills=character_create_data.skills,
            inventory=character_create_data.inventory,
            is_template=import_as_template,
            is_public=False,  # Imported characters are private by default
            version=1,
            experience_points=0,  # Reset XP and level for copies
            character_level=1
        )
        
        self.db.add(imported_character)
        self.db.commit()
        self.db.refresh(imported_character)
        
        # Import equipment if present
        equipment_errors = []
        if "equipment" in character_data and character_data["equipment"]:
            equipment_errors = self._import_character_equipment(imported_character, character_data["equipment"])
        
        # Import skills if present
        skill_errors = []
        if "character_skills" in character_data and character_data["character_skills"]:
            skill_errors = self._import_character_skills(imported_character, character_data["character_skills"])
        
        # Create initial snapshot
        self.versioning_service.create_character_snapshot(
            imported_character.id,
            user_id,
            f"Character imported from external data",
            auto_increment_version=False
        )
        
        # Compile any import warnings
        warnings = equipment_errors + skill_errors
        
        return {
            "success": True,
            "errors": [],
            "warnings": warnings,
            "character": imported_character
        }
    
    def import_character_from_json_string(self, 
                                        user_id: int,
                                        json_string: str,
                                        character_name_override: Optional[str] = None,
                                        import_as_template: bool = False) -> Dict[str, any]:
        """
        Import character from JSON string.
        """
        try:
            import_data = json.loads(json_string)
            return self.import_character(
                user_id, import_data, character_name_override, import_as_template
            )
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "errors": [f"Invalid JSON format: {str(e)}"],
                "character": None
            }
        except Exception as e:
            return {
                "success": False,
                "errors": [f"Import failed: {str(e)}"],
                "character": None
            }
    
    def validate_import_data(self, import_data: Dict[str, any]) -> Dict[str, any]:
        """
        Validate import data without actually importing.
        """
        format_validation = self._validate_import_format(import_data)
        if not format_validation["valid"]:
            return format_validation
        
        character_data = import_data["character"]
        
        # Validate character data
        try:
            character_create_data = PlayerCharacterCreate(
                name=character_data["basic_info"]["name"],
                strength=character_data["stats"]["strength"],
                dexterity=character_data["stats"]["dexterity"],
                intelligence=character_data["stats"]["intelligence"],
                charisma=character_data["stats"]["charisma"],
                personality_traits=character_data["details"].get("personality_traits"),
                skills=character_data["details"].get("skills"),
                inventory=character_data["details"].get("inventory")
            )
            
            validation = self.validation_service.validate_character_creation(character_create_data)
            return {
                "valid": validation["valid"],
                "errors": validation["errors"],
                "warnings": validation["warnings"]
            }
            
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"Character data validation failed: {str(e)}"],
                "warnings": []
            }
    
    def get_export_summary(self, character_id: int, user_id: int) -> Dict[str, any]:
        """
        Get a summary of what would be exported for a character.
        """
        character = self.db.get(PlayerCharacter, character_id)
        if not character:
            return {
                "success": False,
                "errors": ["Character not found"],
                "summary": None
            }
        
        if character.user_id != user_id:
            return {
                "success": False,
                "errors": ["Not authorized to view this character"],
                "summary": None
            }
        
        summary = {
            "character_name": character.name,
            "character_level": character.character_level,
            "experience_points": character.experience_points,
            "equipment_count": len(character.equipment),
            "skills_count": len(character.character_skills),
            "is_template": character.is_template,
            "version": character.version,
            "estimated_export_size_kb": self._estimate_export_size(character)
        }
        
        return {
            "success": True,
            "errors": [],
            "summary": summary
        }
    
    # Private helper methods
    
    def _create_character_export_data(self, 
                                    character: PlayerCharacter, 
                                    include_equipment: bool,
                                    include_skills: bool) -> Dict[str, any]:
        """Create character export data structure"""
        export_data = {
            "basic_info": {
                "name": character.name,
                "character_level": character.character_level,
                "experience_points": character.experience_points,
                "version": character.version,
                "is_template": character.is_template,
                "created_at": character.created_at.isoformat(),
                "updated_at": character.updated_at.isoformat()
            },
            "stats": {
                "strength": character.strength,
                "dexterity": character.dexterity,
                "intelligence": character.intelligence,
                "charisma": character.charisma
            },
            "details": {
                "personality_traits": character.personality_traits,
                "skills": character.skills,
                "inventory": character.inventory
            }
        }
        
        # Include equipment if requested
        if include_equipment:
            export_data["equipment"] = []
            for equipment in character.equipment:
                export_data["equipment"].append({
                    "name": equipment.name,
                    "description": equipment.description,
                    "item_type": equipment.item_type.value,
                    "stat_modifiers": equipment.stat_modifiers,
                    "is_equipped": equipment.is_equipped,
                    "created_at": equipment.created_at.isoformat()
                })
        
        # Include character skills if requested
        if include_skills:
            export_data["character_skills"] = []
            for char_skill in character.character_skills:
                skill_export = {
                    "proficiency_level": char_skill.proficiency_level,
                    "experience_points": char_skill.experience_points,
                    "acquired_at": char_skill.acquired_at.isoformat()
                }
                if char_skill.last_used:
                    skill_export["last_used"] = char_skill.last_used.isoformat()
                
                # Include skill reference data
                if char_skill.skill:
                    skill_export["skill_reference"] = {
                        "name": char_skill.skill.name,
                        "description": char_skill.skill.description,
                        "category": char_skill.skill.category.value,
                        "prerequisite_skills": char_skill.skill.prerequisite_skills,
                        "minimum_level": char_skill.skill.minimum_level,
                        "stat_requirements": char_skill.skill.stat_requirements
                    }
                
                export_data["character_skills"].append(skill_export)
        
        return export_data
    
    def _validate_import_format(self, import_data: Dict[str, any]) -> Dict[str, any]:
        """Validate import data format and version compatibility"""
        errors = []
        
        # Check required top-level fields
        required_fields = ["format_version", "character"]
        for field in required_fields:
            if field not in import_data:
                errors.append(f"Missing required field: {field}")
        
        if errors:
            return {"valid": False, "errors": errors, "warnings": []}
        
        # Check format version compatibility
        format_version = import_data["format_version"]
        if format_version not in self.SUPPORTED_IMPORT_VERSIONS:
            errors.append(
                f"Unsupported format version: {format_version}. "
                f"Supported versions: {', '.join(self.SUPPORTED_IMPORT_VERSIONS)}"
            )
        
        # Validate character structure
        character_data = import_data["character"]
        required_character_fields = ["basic_info", "stats", "details"]
        for field in required_character_fields:
            if field not in character_data:
                errors.append(f"Missing character field: {field}")
        
        # Validate basic_info structure
        if "basic_info" in character_data:
            required_basic_fields = ["name"]
            for field in required_basic_fields:
                if field not in character_data["basic_info"]:
                    errors.append(f"Missing basic_info field: {field}")
        
        # Validate stats structure
        if "stats" in character_data:
            required_stat_fields = ["strength", "dexterity", "intelligence", "charisma"]
            for field in required_stat_fields:
                if field not in character_data["stats"]:
                    errors.append(f"Missing stats field: {field}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": []
        }
    
    def _import_character_equipment(self, character: PlayerCharacter, equipment_data: List[Dict]) -> List[str]:
        """Import equipment for character, returns any errors"""
        errors = []
        
        for eq_data in equipment_data:
            try:
                # Validate equipment type
                item_type_str = eq_data.get("item_type", "misc")
                try:
                    item_type = EquipmentType(item_type_str)
                except ValueError:
                    item_type = EquipmentType.MISC
                    errors.append(f"Unknown equipment type '{item_type_str}', defaulted to misc")
                
                equipment = Equipment(
                    character_id=character.id,
                    name=eq_data.get("name", "Unknown Item"),
                    description=eq_data.get("description", ""),
                    item_type=item_type,
                    stat_modifiers=eq_data.get("stat_modifiers"),
                    is_equipped=eq_data.get("is_equipped", False)
                )
                
                self.db.add(equipment)
                
            except Exception as e:
                errors.append(f"Failed to import equipment '{eq_data.get('name', 'Unknown')}': {str(e)}")
        
        if equipment_data:
            self.db.commit()
        
        return errors
    
    def _import_character_skills(self, character: PlayerCharacter, skills_data: List[Dict]) -> List[str]:
        """Import character skills, returns any errors"""
        errors = []
        
        for skill_data in skills_data:
            try:
                # Try to find matching skill by name
                skill_ref = skill_data.get("skill_reference", {})
                skill_name = skill_ref.get("name")
                
                if skill_name:
                    # Try to find existing skill
                    existing_skill = self.db.query(Skill).filter(Skill.name == skill_name).first()
                    
                    if existing_skill:
                        char_skill = CharacterSkill(
                            character_id=character.id,
                            skill_id=existing_skill.id,
                            proficiency_level=skill_data.get("proficiency_level", 1),
                            experience_points=skill_data.get("experience_points", 0)
                        )
                        self.db.add(char_skill)
                    else:
                        errors.append(f"Skill '{skill_name}' not found in system, skipped")
                else:
                    errors.append("Skill data missing name reference, skipped")
                
            except Exception as e:
                skill_name = skill_data.get("skill_reference", {}).get("name", "Unknown")
                errors.append(f"Failed to import skill '{skill_name}': {str(e)}")
        
        if skills_data:
            self.db.commit()
        
        return errors
    
    def _estimate_export_size(self, character: PlayerCharacter) -> float:
        """Estimate export size in KB"""
        # Rough estimation based on character complexity
        base_size = 2  # Base character data
        equipment_size = len(character.equipment) * 0.5  # ~0.5KB per equipment
        skills_size = len(character.character_skills) * 0.3  # ~0.3KB per skill
        
        return round(base_size + equipment_size + skills_size, 1)


class CharacterSearchService:
    """Service for searching and filtering characters with advanced criteria"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def search_characters(self, 
                         user_id: int,
                         search_criteria: Dict[str, any],
                         include_public: bool = False,
                         include_templates: bool = False,
                         sort_by: str = "name",
                         sort_direction: str = "asc",
                         limit: int = 50,
                         offset: int = 0) -> Dict[str, any]:
        """Comprehensive character search with multiple filtering criteria."""
        try:
            # Build base query
            query = self._build_base_query(user_id, include_public, include_templates)
            
            # Apply search filters
            query = self._apply_text_filters(query, search_criteria)
            query = self._apply_stat_filters(query, search_criteria)
            query = self._apply_level_filters(query, search_criteria)
            query = self._apply_meta_filters(query, search_criteria)
            
            # Get total count before pagination
            total_count = query.count()
            
            # Apply sorting
            query = self._apply_sorting(query, sort_by, sort_direction)
            
            # Apply pagination
            characters = query.offset(offset).limit(limit).all()
            
            return {
                "success": True,
                "characters": characters,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(characters) < total_count,
                "search_criteria": search_criteria
            }
            
        except Exception as e:
            return {
                "success": False,
                "errors": [f"Search failed: {str(e)}"],
                "characters": [],
                "total_count": 0
            }
    
    def search_user_characters(self, user_id: int, search_criteria: Dict[str, any]) -> Dict[str, any]:
        """Search characters owned by a specific user."""
        return self.search_characters(
            user_id=user_id,
            search_criteria=search_criteria,
            include_public=False,
            include_templates=True,
            sort_by="updated_at",
            sort_direction="desc",
            limit=20,
            offset=0
        )
    
    def search_public_characters(self, user_id: Optional[int], search_criteria: Dict[str, any]) -> Dict[str, any]:
        """Search public characters with guest access support."""
        return self.search_characters(
            user_id=user_id or 0,
            search_criteria=search_criteria,
            include_public=True,
            include_templates=True,
            sort_by="created_at",
            sort_direction="desc",
            limit=50,
            offset=0
        )
    
    def get_character_suggestions(self, user_id: int, partial_name: str, limit: int = 10) -> Dict[str, any]:
        """Get character name suggestions for autocomplete."""
        try:
            query = self._build_base_query(user_id, include_public=True, include_templates=True)
            
            if partial_name:
                query = query.filter(PlayerCharacter.name.ilike(f"%{partial_name}%"))
            
            characters = query.order_by(PlayerCharacter.name).limit(limit).all()
            
            suggestions = [
                {
                    "id": char.id,
                    "name": char.name,
                    "level": char.character_level,
                    "is_template": char.is_template,
                    "is_public": char.is_public,
                    "is_owned": char.user_id == user_id
                }
                for char in characters
            ]
            
            return {"success": True, "suggestions": suggestions}
            
        except Exception as e:
            return {"success": False, "errors": [f"Suggestion search failed: {str(e)}"], "suggestions": []}
    
    # Private helper methods
    
    def _build_base_query(self, user_id: int, include_public: bool, include_templates: bool):
        """Build the base query for character search"""
        query = self.db.query(PlayerCharacter)
        
        # Access control filters
        if include_public and user_id > 0:
            query = query.filter((PlayerCharacter.user_id == user_id) | (PlayerCharacter.is_public == True))
        elif include_public:
            query = query.filter(PlayerCharacter.is_public == True)
        else:
            query = query.filter(PlayerCharacter.user_id == user_id)
        
        # Template filter
        if not include_templates:
            query = query.filter(PlayerCharacter.is_template == False)
        
        return query
    
    def _apply_text_filters(self, query, criteria: Dict[str, any]):
        """Apply text-based search filters"""
        if "name" in criteria and criteria["name"]:
            query = query.filter(PlayerCharacter.name.ilike(f"%{criteria['name']}%"))
        
        if "personality_traits" in criteria and criteria["personality_traits"]:
            query = query.filter(PlayerCharacter.personality_traits.ilike(f"%{criteria['personality_traits']}%"))
        
        return query
    
    def _apply_stat_filters(self, query, criteria: Dict[str, any]):
        """Apply stat-based filters"""
        stat_filters = criteria.get("stats", {})
        
        for stat_name, requirements in stat_filters.items():
            if hasattr(PlayerCharacter, stat_name):
                stat_attr = getattr(PlayerCharacter, stat_name)
                
                if isinstance(requirements, dict):
                    if "min" in requirements:
                        query = query.filter(stat_attr >= requirements["min"])
                    if "max" in requirements:
                        query = query.filter(stat_attr <= requirements["max"])
                elif isinstance(requirements, (int, float)):
                    query = query.filter(stat_attr == requirements)
        
        return query
    
    def _apply_level_filters(self, query, criteria: Dict[str, any]):
        """Apply level and experience filters"""
        if "level_min" in criteria:
            query = query.filter(PlayerCharacter.character_level >= criteria["level_min"])
        if "level_max" in criteria:
            query = query.filter(PlayerCharacter.character_level <= criteria["level_max"])
        
        return query
    
    def _apply_meta_filters(self, query, criteria: Dict[str, any]):
        """Apply metadata filters"""
        if "is_template" in criteria:
            query = query.filter(PlayerCharacter.is_template == criteria["is_template"])
        if "is_public" in criteria:
            query = query.filter(PlayerCharacter.is_public == criteria["is_public"])
        
        return query
    
    def _apply_sorting(self, query, sort_by: str, sort_direction: str):
        """Apply sorting to the query"""
        sort_mapping = {
            "name": PlayerCharacter.name,
            "level": PlayerCharacter.character_level,
            "experience": PlayerCharacter.experience_points,
            "created_at": PlayerCharacter.created_at,
            "updated_at": PlayerCharacter.updated_at,
        }
        
        sort_field = sort_mapping.get(sort_by, PlayerCharacter.name)
        
        if sort_direction.lower() == "desc":
            query = query.order_by(sort_field.desc())
        else:
            query = query.order_by(sort_field.asc())
        
        return query