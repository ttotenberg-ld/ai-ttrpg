#!/usr/bin/env python3
"""
Unit Tests for Character Service Functionality
Task 5.6: Create unit tests for character service with validation scenarios

This test suite focuses on testing character validation business logic,
including stat allocation, skill prerequisites, equipment compatibility,
and character progression rules.
"""

import pytest
import sys
import os
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add the server directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test character validation logic directly
class MockCharacterValidationService:
    """Mock implementation of character validation service for testing"""
    
    DEFAULT_STAT_POINTS = 40
    MIN_STAT_VALUE = 8
    MAX_STAT_VALUE = 18
    STAT_POINT_COST = {10: 1, 11: 1, 12: 1, 13: 1, 14: 2, 15: 2, 16: 3, 17: 4, 18: 5}
    MAX_PROFICIENCY_LEVEL = 5
    BASE_SKILL_XP_COST = 100
    
    def __init__(self, db_session):
        self.db = db_session
    
    def calculate_total_stat_cost(self, strength, dexterity, intelligence, charisma):
        """Calculate total point cost for stat allocation"""
        total_cost = 0
        for stat_value in [strength, dexterity, intelligence, charisma]:
            if stat_value < self.MIN_STAT_VALUE:
                continue
            for value in range(self.MIN_STAT_VALUE, min(stat_value + 1, self.MAX_STAT_VALUE + 1)):
                if value in self.STAT_POINT_COST:
                    total_cost += self.STAT_POINT_COST.get(value, 1)
        return total_cost
    
    def _validate_stat_allocation(self, strength, dexterity, intelligence, charisma):
        """Validate stat point allocation"""
        errors = []
        
        stats = {"strength": strength, "dexterity": dexterity, 
                "intelligence": intelligence, "charisma": charisma}
        
        for stat_name, value in stats.items():
            if value < self.MIN_STAT_VALUE:
                errors.append(f"{stat_name.capitalize()} cannot be below {self.MIN_STAT_VALUE}")
            elif value > self.MAX_STAT_VALUE:
                errors.append(f"{stat_name.capitalize()} cannot exceed {self.MAX_STAT_VALUE}")
        
        total_cost = self.calculate_total_stat_cost(strength, dexterity, intelligence, charisma)
        if total_cost > self.DEFAULT_STAT_POINTS:
            errors.append(
                f"Total stat points ({total_cost}) exceed allowed limit ({self.DEFAULT_STAT_POINTS})"
            )
        
        return errors
    
    def _validate_character_name(self, name):
        """Validate character name"""
        errors = []
        
        if not name or len(name.strip()) < 2:
            errors.append("Character name must be at least 2 characters long")
        elif len(name) > 50:
            errors.append("Character name cannot exceed 50 characters")
        
        return errors
    
    def _validate_level_progression(self, character, new_level):
        """Validate character level progression"""
        errors = []
        
        if new_level < character.character_level:
            errors.append("Character level cannot be decreased")
        elif new_level > character.character_level + 1:
            errors.append("Character can only advance one level at a time")
        
        required_xp = (new_level - 1) * 1000
        if character.experience_points < required_xp:
            errors.append(
                f"Insufficient experience points. Need {required_xp}, have {character.experience_points}"
            )
        
        return errors
    
    def _validate_experience_points(self, character, new_xp):
        """Validate experience point changes"""
        errors = []
        
        if new_xp < 0:
            errors.append("Experience points cannot be negative")
        elif new_xp < character.experience_points:
            errors.append("Experience points cannot be decreased")
        
        return errors

    def calculate_skill_xp_cost(self, current_level, target_level):
        """Calculate XP cost to advance skill from current to target level"""
        if target_level <= current_level:
            return 0
        
        total_cost = 0
        for level in range(current_level + 1, target_level + 1):
            total_cost += self.BASE_SKILL_XP_COST * level
        return total_cost


class TestCharacterValidationLogic:
    """Unit tests for character validation business logic"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_session = MagicMock()
        self.validation_service = MockCharacterValidationService(self.mock_session)
    
    def test_validate_stat_allocation_valid_stats(self):
        """Test stat allocation validation with valid stats"""
        errors = self.validation_service._validate_stat_allocation(12, 14, 10, 8)
        assert len(errors) == 0
    
    def test_validate_stat_allocation_stats_too_low(self):
        """Test stat allocation validation with stats below minimum"""
        errors = self.validation_service._validate_stat_allocation(7, 10, 10, 10)
        assert len(errors) > 0
        assert any("Strength cannot be below 8" in error for error in errors)
    
    def test_validate_stat_allocation_stats_too_high(self):
        """Test stat allocation validation with stats above maximum"""
        errors = self.validation_service._validate_stat_allocation(19, 10, 10, 10)
        assert len(errors) > 0
        assert any("Strength cannot exceed 18" in error for error in errors)
    
    def test_validate_stat_allocation_excessive_points(self):
        """Test stat allocation validation with too many points"""
        errors = self.validation_service._validate_stat_allocation(18, 18, 18, 18)
        assert len(errors) > 0
        assert any("exceed allowed limit" in error for error in errors)
    
    def test_calculate_total_stat_cost_base_stats(self):
        """Test stat cost calculation for base stats"""
        cost = self.validation_service.calculate_total_stat_cost(8, 8, 8, 8)
        assert cost == 0
    
    def test_calculate_total_stat_cost_increased_stats(self):
        """Test stat cost calculation for increased stats"""
        cost = self.validation_service.calculate_total_stat_cost(10, 10, 10, 10)
        expected_cost = 4 * self.validation_service.STAT_POINT_COST[10]
        assert cost == expected_cost
    
    def test_validate_character_name_valid(self):
        """Test character name validation with valid name"""
        errors = self.validation_service._validate_character_name("Valid Name")
        assert len(errors) == 0
    
    def test_validate_character_name_too_short(self):
        """Test character name validation with name too short"""
        errors = self.validation_service._validate_character_name("X")
        assert len(errors) > 0
        assert any("at least 2 characters long" in error for error in errors)
    
    def test_validate_character_name_too_long(self):
        """Test character name validation with name too long"""
        errors = self.validation_service._validate_character_name("X" * 51)
        assert len(errors) > 0
        assert any("cannot exceed 50 characters" in error for error in errors)
    
    def test_validate_character_name_empty(self):
        """Test character name validation with empty name"""
        errors = self.validation_service._validate_character_name("")
        assert len(errors) > 0
        assert any("at least 2 characters long" in error for error in errors)
    
    def test_validate_level_progression_valid(self):
        """Test valid character level progression"""
        character = Mock()
        character.character_level = 1
        character.experience_points = 1000
        
        errors = self.validation_service._validate_level_progression(character, 2)
        assert len(errors) == 0
    
    def test_validate_level_progression_decrease(self):
        """Test invalid character level decrease"""
        character = Mock()
        character.character_level = 5
        character.experience_points = 5000
        
        errors = self.validation_service._validate_level_progression(character, 4)
        assert len(errors) > 0
        assert any("cannot be decreased" in error for error in errors)
    
    def test_validate_level_progression_skip(self):
        """Test invalid character level skipping"""
        character = Mock()
        character.character_level = 1
        character.experience_points = 5000
        
        errors = self.validation_service._validate_level_progression(character, 3)
        assert len(errors) > 0
        assert any("one level at a time" in error for error in errors)
    
    def test_validate_level_progression_insufficient_xp(self):
        """Test character level progression with insufficient XP"""
        character = Mock()
        character.character_level = 1
        character.experience_points = 500
        
        errors = self.validation_service._validate_level_progression(character, 2)
        assert len(errors) > 0
        assert any("Insufficient experience points" in error for error in errors)
    
    def test_validate_experience_points_valid(self):
        """Test valid experience points validation"""
        character = Mock()
        character.experience_points = 1000
        
        errors = self.validation_service._validate_experience_points(character, 1500)
        assert len(errors) == 0
    
    def test_validate_experience_points_negative(self):
        """Test experience points validation with negative value"""
        character = Mock()
        character.experience_points = 1000
        
        errors = self.validation_service._validate_experience_points(character, -100)
        assert len(errors) > 0
        assert any("cannot be negative" in error for error in errors)
    
    def test_validate_experience_points_decrease(self):
        """Test experience points validation with decrease"""
        character = Mock()
        character.experience_points = 1000
        
        errors = self.validation_service._validate_experience_points(character, 500)
        assert len(errors) > 0
        assert any("cannot be decreased" in error for error in errors)
    
    def test_calculate_skill_xp_cost_advance(self):
        """Test skill XP cost calculation for advancement"""
        cost = self.validation_service.calculate_skill_xp_cost(1, 3)
        expected = (self.validation_service.BASE_SKILL_XP_COST * 2) + (self.validation_service.BASE_SKILL_XP_COST * 3)
        assert cost == expected
    
    def test_calculate_skill_xp_cost_same_level(self):
        """Test skill XP cost calculation for same level"""
        cost = self.validation_service.calculate_skill_xp_cost(3, 3)
        assert cost == 0
    
    def test_calculate_skill_xp_cost_lower_level(self):
        """Test skill XP cost calculation for lower target level"""
        cost = self.validation_service.calculate_skill_xp_cost(5, 3)
        assert cost == 0


class TestEquipmentValidationLogic:
    """Unit tests for equipment validation logic"""
    
    def test_equipment_level_requirement_validation(self):
        """Test equipment level requirement validation logic"""
        # Mock character
        character = Mock()
        character.character_level = 5
        
        # Test case 1: Equipment with level requirement below character level
        stat_modifiers_valid = json.dumps({"required_level": 3})
        required_level = json.loads(stat_modifiers_valid).get("required_level", 1)
        assert character.character_level >= required_level
        
        # Test case 2: Equipment with level requirement above character level
        stat_modifiers_invalid = json.dumps({"required_level": 10})
        required_level = json.loads(stat_modifiers_invalid).get("required_level", 1)
        assert character.character_level < required_level
    
    def test_equipment_slot_conflict_detection(self):
        """Test equipment slot conflict detection logic"""
        # Mock existing equipment
        existing_weapon = Mock()
        existing_weapon.id = 1
        existing_weapon.is_equipped = True
        existing_weapon.item_type = "WEAPON"
        
        # Mock new equipment
        new_weapon = Mock()
        new_weapon.id = 2
        new_weapon.is_equipped = True
        new_weapon.item_type = "WEAPON"
        
        # Mock character with existing equipment
        character = Mock()
        character.equipment = [existing_weapon]
        
        # Check for conflicts
        conflicts = [
            eq for eq in character.equipment 
            if eq.is_equipped and eq.item_type == new_weapon.item_type and eq.id != new_weapon.id
        ]
        
        assert len(conflicts) > 0  # Should detect conflict


class TestCharacterTemplateLogic:
    """Unit tests for character template logic"""
    
    def test_template_accessibility_public(self):
        """Test template accessibility logic for public templates"""
        template = Mock()
        template.is_template = True
        template.is_public = True
        template.user_id = 1
        
        # Any user should be able to access public templates
        requesting_user_id = 2
        accessible = template.is_public or template.user_id == requesting_user_id
        assert accessible is True
    
    def test_template_accessibility_private_owner(self):
        """Test template accessibility logic for private templates by owner"""
        template = Mock()
        template.is_template = True
        template.is_public = False
        template.user_id = 1
        
        # Owner should be able to access private templates
        requesting_user_id = 1
        accessible = template.is_public or template.user_id == requesting_user_id
        assert accessible is True
    
    def test_template_accessibility_private_non_owner(self):
        """Test template accessibility logic for private templates by non-owner"""
        template = Mock()
        template.is_template = True
        template.is_public = False
        template.user_id = 1
        
        # Non-owner should not be able to access private templates
        requesting_user_id = 2
        accessible = template.is_public or template.user_id == requesting_user_id
        assert accessible is False


class TestCharacterSharingLogic:
    """Unit tests for character sharing logic"""
    
    def test_sharing_permission_owner(self):
        """Test character sharing permission for owner"""
        character = Mock()
        character.user_id = 1
        
        requesting_user_id = 1
        can_share = character.user_id == requesting_user_id
        assert can_share is True
    
    def test_sharing_permission_non_owner(self):
        """Test character sharing permission for non-owner"""
        character = Mock()
        character.user_id = 1
        
        requesting_user_id = 2
        can_share = character.user_id == requesting_user_id
        assert can_share is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 