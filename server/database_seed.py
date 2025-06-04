import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select
from faker import Faker

from database import engine
from models import (
    User, PlayerCharacter, Equipment, EquipmentType, Skill, SkillCategory, 
    CharacterSkill, CharacterVersion
)
from auth import get_password_hash

fake = Faker()


class DatabaseSeeder:
    """
    Database seeding utility for development and testing.
    """
    
    def __init__(self, session: Optional[Session] = None):
        """
        Initialize the database seeder.
        
        Args:
            session: Optional database session (will create one if not provided)
        """
        self.session = session or Session(engine)
        self.close_session = session is None  # Only close if we created it
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.close_session:
            self.session.close()
    
    def seed_all(self, clear_existing: bool = False) -> Dict[str, Any]:
        """
        Seed all data types in the correct order.
        
        Args:
            clear_existing: Whether to clear existing data first
            
        Returns:
            Summary of seeded data
        """
        if clear_existing:
            self.clear_all_data()
        
        summary = {
            "users": 0,
            "skills": 0,
            "characters": 0,
            "equipment": 0,
            "character_skills": 0,
            "character_versions": 0,
            "templates": 0
        }
        
        try:
            # Seed in dependency order
            summary["users"] = self.seed_users()
            summary["skills"] = self.seed_skills()
            summary["characters"] = self.seed_characters()
            summary["equipment"] = self.seed_equipment()
            summary["character_skills"] = self.seed_character_skills()
            summary["character_versions"] = self.seed_character_versions()
            summary["templates"] = self.seed_character_templates()
            
            self.session.commit()
            return summary
            
        except Exception as e:
            self.session.rollback()
            raise e
    
    def clear_all_data(self):
        """Clear all seeded data (in reverse dependency order)"""
        # Clear in reverse dependency order by deleting all records
        
        # Delete character skills first (depends on characters and skills)
        char_skills = self.session.exec(select(CharacterSkill)).all()
        for cs in char_skills:
            self.session.delete(cs)
        
        # Delete equipment (depends on characters)
        equipment = self.session.exec(select(Equipment)).all()
        for eq in equipment:
            self.session.delete(eq)
        
        # Delete character versions (depends on characters and users)
        versions = self.session.exec(select(CharacterVersion)).all()
        for cv in versions:
            self.session.delete(cv)
        
        # Delete characters (depends on users)
        characters = self.session.exec(select(PlayerCharacter)).all()
        for char in characters:
            self.session.delete(char)
        
        # Delete skills (no dependencies)
        skills = self.session.exec(select(Skill)).all()
        for skill in skills:
            self.session.delete(skill)
        
        # Delete users (no dependencies remaining)
        users = self.session.exec(select(User)).all()
        for user in users:
            self.session.delete(user)
        
        self.session.commit()
    
    def seed_users(self, count: int = 10) -> int:
        """
        Seed sample users.
        
        Args:
            count: Number of users to create
            
        Returns:
            Number of users created
        """
        existing_users = self.session.exec(select(User)).all()
        existing_usernames = {user.username for user in existing_users}
        existing_emails = {user.email for user in existing_users}
        
        users_created = 0
        
        # Create a known admin user for testing
        if "admin" not in existing_usernames and "admin@example.com" not in existing_emails:
            admin_user = User(
                username="admin",
                email="admin@example.com",
                hashed_password=get_password_hash("admin123"),
                email_verified=True,
                is_active=True,
                last_login=datetime.now()
            )
            self.session.add(admin_user)
            users_created += 1
        
        # Create a known test user
        if "testuser" not in existing_usernames and "test@example.com" not in existing_emails:
            test_user = User(
                username="testuser",
                email="test@example.com",
                hashed_password=get_password_hash("test123"),
                email_verified=True,
                is_active=True,
                last_login=datetime.now() - timedelta(days=1)
            )
            self.session.add(test_user)
            users_created += 1
        
        # Create random users
        attempts = 0
        max_attempts = count * 3  # Allow some failed attempts
        
        while users_created < count and attempts < max_attempts:
            attempts += 1
            username = fake.user_name()
            email = fake.email()
            
            if username in existing_usernames or email in existing_emails:
                continue
                
            user = User(
                username=username,
                email=email,
                hashed_password=get_password_hash("password123"),
                email_verified=fake.boolean(chance_of_getting_true=80),
                is_active=fake.boolean(chance_of_getting_true=95),
                last_login=fake.date_time_between(start_date="-30d", end_date="now") if fake.boolean() else None,
                created_at=fake.date_time_between(start_date="-180d", end_date="-1d"),
                failed_login_attempts=fake.random_int(min=0, max=2) if fake.boolean(chance_of_getting_true=10) else 0
            )
            self.session.add(user)
            existing_usernames.add(username)
            existing_emails.add(email)
            users_created += 1
        
        return users_created
    
    def seed_skills(self) -> int:
        """
        Seed sample skills across all categories.
        
        Returns:
            Number of skills created
        """
        existing_skills = self.session.exec(select(Skill)).all()
        existing_skill_names = {skill.name for skill in existing_skills}
        
        # Define comprehensive skill sets by category
        skill_definitions = {
            SkillCategory.COMBAT: [
                {"name": "Sword Fighting", "description": "Mastery of blade combat techniques", "min_level": 1, "stat_req": {"strength": 12}},
                {"name": "Archery", "description": "Precision with ranged weapons", "min_level": 1, "stat_req": {"dexterity": 13}},
                {"name": "Shield Defense", "description": "Expert use of shields for protection", "min_level": 2, "stat_req": {"strength": 11}},
                {"name": "Dual Wielding", "description": "Fighting with two weapons simultaneously", "min_level": 5, "stat_req": {"dexterity": 15}, "prereq": ["Sword Fighting"]},
                {"name": "Combat Tactics", "description": "Strategic combat planning and execution", "min_level": 3, "stat_req": {"intelligence": 14}},
                {"name": "Berserker Rage", "description": "Channel fury for increased combat effectiveness", "min_level": 4, "stat_req": {"strength": 16}},
            ],
            SkillCategory.SOCIAL: [
                {"name": "Persuasion", "description": "Convince others through compelling arguments", "min_level": 1, "stat_req": {"charisma": 12}},
                {"name": "Deception", "description": "The art of lies and misdirection", "min_level": 1, "stat_req": {"charisma": 11}},
                {"name": "Intimidation", "description": "Use presence and threats to influence others", "min_level": 1, "stat_req": {"strength": 12, "charisma": 10}},
                {"name": "Leadership", "description": "Inspire and guide groups effectively", "min_level": 3, "stat_req": {"charisma": 15}, "prereq": ["Persuasion"]},
                {"name": "Diplomatic Immunity", "description": "Navigate complex political situations", "min_level": 5, "stat_req": {"charisma": 16, "intelligence": 14}, "prereq": ["Leadership", "Persuasion"]},
                {"name": "Barter", "description": "Negotiate favorable deals and trades", "min_level": 1, "stat_req": {"charisma": 11}},
            ],
            SkillCategory.EXPLORATION: [
                {"name": "Lockpicking", "description": "Open locked doors and containers", "min_level": 1, "stat_req": {"dexterity": 13}},
                {"name": "Stealth", "description": "Move unseen and unheard", "min_level": 1, "stat_req": {"dexterity": 12}},
                {"name": "Climbing", "description": "Scale walls and difficult terrain", "min_level": 1, "stat_req": {"strength": 11, "dexterity": 11}},
                {"name": "Trap Detection", "description": "Identify and disarm dangerous mechanisms", "min_level": 2, "stat_req": {"intelligence": 13, "dexterity": 12}},
                {"name": "Master Thief", "description": "Ultimate infiltration and theft skills", "min_level": 7, "stat_req": {"dexterity": 18}, "prereq": ["Lockpicking", "Stealth", "Trap Detection"]},
                {"name": "Pathfinding", "description": "Navigate wilderness and unknown areas", "min_level": 1, "stat_req": {"intelligence": 11}},
            ],
            SkillCategory.CRAFTING: [
                {"name": "Blacksmithing", "description": "Forge weapons and armor from metal", "min_level": 2, "stat_req": {"strength": 13}},
                {"name": "Alchemy", "description": "Create potions and magical compounds", "min_level": 2, "stat_req": {"intelligence": 14}},
                {"name": "Enchanting", "description": "Imbue items with magical properties", "min_level": 4, "stat_req": {"intelligence": 16}, "prereq": ["Alchemy"]},
                {"name": "Leatherworking", "description": "Craft armor and goods from hides", "min_level": 1, "stat_req": {"dexterity": 12}},
                {"name": "Jewelcrafting", "description": "Create valuable ornaments and accessories", "min_level": 3, "stat_req": {"dexterity": 15, "intelligence": 12}},
                {"name": "Master Craftsman", "description": "Peak expertise in all crafting disciplines", "min_level": 8, "stat_req": {"intelligence": 17, "dexterity": 16}, "prereq": ["Blacksmithing", "Alchemy", "Leatherworking"]},
            ],
            SkillCategory.MAGIC: [
                {"name": "Fire Magic", "description": "Harness the power of flames", "min_level": 2, "stat_req": {"intelligence": 13}},
                {"name": "Water Magic", "description": "Control water and ice", "min_level": 2, "stat_req": {"intelligence": 13}},
                {"name": "Earth Magic", "description": "Manipulate stone and soil", "min_level": 2, "stat_req": {"intelligence": 13}},
                {"name": "Air Magic", "description": "Command wind and lightning", "min_level": 2, "stat_req": {"intelligence": 13}},
                {"name": "Healing Magic", "description": "Restore health and cure ailments", "min_level": 1, "stat_req": {"intelligence": 12, "charisma": 11}},
                {"name": "Arcane Mastery", "description": "Ultimate understanding of magical forces", "min_level": 10, "stat_req": {"intelligence": 20}, "prereq": ["Fire Magic", "Water Magic", "Earth Magic", "Air Magic"]},
            ],
            SkillCategory.KNOWLEDGE: [
                {"name": "History", "description": "Knowledge of past events and civilizations", "min_level": 1, "stat_req": {"intelligence": 12}},
                {"name": "Arcana", "description": "Understanding of magical theory and practice", "min_level": 1, "stat_req": {"intelligence": 13}},
                {"name": "Nature", "description": "Knowledge of flora, fauna, and natural phenomena", "min_level": 1, "stat_req": {"intelligence": 11}},
                {"name": "Religion", "description": "Understanding of divine powers and theology", "min_level": 1, "stat_req": {"intelligence": 11, "charisma": 10}},
                {"name": "Investigation", "description": "Systematic gathering and analysis of information", "min_level": 2, "stat_req": {"intelligence": 14}},
                {"name": "Scholar", "description": "Vast expertise across multiple knowledge domains", "min_level": 6, "stat_req": {"intelligence": 18}, "prereq": ["History", "Arcana", "Investigation"]},
            ],
            SkillCategory.SURVIVAL: [
                {"name": "Hunting", "description": "Track and hunt wild game", "min_level": 1, "stat_req": {"dexterity": 11, "intelligence": 10}},
                {"name": "Foraging", "description": "Find edible plants and resources in the wild", "min_level": 1, "stat_req": {"intelligence": 11}},
                {"name": "Animal Handling", "description": "Interact with and train animals", "min_level": 1, "stat_req": {"charisma": 12}},
                {"name": "Weather Prediction", "description": "Forecast weather patterns and changes", "min_level": 2, "stat_req": {"intelligence": 13}},
                {"name": "Medicine", "description": "Treat wounds and illnesses without magic", "min_level": 2, "stat_req": {"intelligence": 13, "dexterity": 11}},
                {"name": "Wilderness Master", "description": "Ultimate survival skills in any environment", "min_level": 7, "stat_req": {"intelligence": 16, "dexterity": 15}, "prereq": ["Hunting", "Foraging", "Medicine"]},
            ]
        }
        
        skills_created = 0
        
        for category, skills_list in skill_definitions.items():
            for skill_def in skills_list:
                if skill_def["name"] in existing_skill_names:
                    continue
                
                skill = Skill(
                    name=skill_def["name"],
                    description=skill_def["description"],
                    category=category,
                    minimum_level=skill_def["min_level"],
                    stat_requirements=json.dumps(skill_def.get("stat_req", {})),
                    prerequisite_skills=json.dumps(skill_def.get("prereq", [])),
                    created_at=fake.date_time_between(start_date="-90d", end_date="-30d")
                )
                self.session.add(skill)
                existing_skill_names.add(skill_def["name"])
                skills_created += 1
        
        return skills_created
    
    def seed_characters(self, count_per_user: int = 3) -> int:
        """
        Seed sample characters for existing users.
        
        Args:
            count_per_user: Average number of characters per user
            
        Returns:
            Number of characters created
        """
        users = self.session.exec(select(User)).all()
        if not users:
            return 0
        
        existing_characters = self.session.exec(select(PlayerCharacter)).all()
        existing_char_names = {(char.user_id, char.name) for char in existing_characters}
        
        characters_created = 0
        
        # Character archetypes for varied creation
        archetypes = [
            {"name": "Warrior", "stats": {"strength": 16, "dexterity": 12, "intelligence": 10, "charisma": 12}, 
             "traits": "Brave and honorable fighter", "skills": "Combat training, weapon mastery"},
            {"name": "Rogue", "stats": {"strength": 10, "dexterity": 16, "intelligence": 13, "charisma": 11}, 
             "traits": "Sneaky and resourceful", "skills": "Stealth, lockpicking, sleight of hand"},
            {"name": "Mage", "stats": {"strength": 8, "dexterity": 10, "intelligence": 18, "charisma": 14}, 
             "traits": "Scholarly and wise", "skills": "Arcane knowledge, spellcasting, research"},
            {"name": "Paladin", "stats": {"strength": 15, "dexterity": 10, "intelligence": 12, "charisma": 16}, 
             "traits": "Righteous and devoted", "skills": "Divine magic, healing, leadership"},
            {"name": "Ranger", "stats": {"strength": 13, "dexterity": 15, "intelligence": 12, "charisma": 10}, 
             "traits": "Independent wilderness expert", "skills": "Tracking, survival, archery"},
            {"name": "Bard", "stats": {"strength": 10, "dexterity": 14, "intelligence": 13, "charisma": 16}, 
             "traits": "Charismatic performer and storyteller", "skills": "Music, persuasion, lore"},
        ]
        
        for user in users:
            num_characters = fake.random_int(min=1, max=count_per_user + 2)
            
            for i in range(num_characters):
                archetype = fake.random_element(archetypes)
                base_name = archetype["name"]
                
                # Generate unique character name
                character_name = f"{fake.first_name()} the {base_name}"
                counter = 1
                while (user.id, character_name) in existing_char_names:
                    character_name = f"{fake.first_name()} the {base_name} {counter}"
                    counter += 1
                
                # Add some randomness to stats while keeping archetype feel
                stats = archetype["stats"].copy()
                for stat in stats:
                    variation = fake.random_int(min=-2, max=2)
                    stats[stat] = max(8, min(20, stats[stat] + variation))
                
                # Create character with varying experience and levels
                exp_multiplier = fake.random_int(min=0, max=10)
                experience = exp_multiplier * 100
                level = min(10, 1 + (experience // 100))
                
                character = PlayerCharacter(
                    user_id=user.id,
                    name=character_name,
                    strength=stats["strength"],
                    dexterity=stats["dexterity"],
                    intelligence=stats["intelligence"],
                    charisma=stats["charisma"],
                    personality_traits=archetype["traits"] + f". {fake.sentence()}",
                    skills=archetype["skills"],
                    inventory=self._generate_random_inventory(),
                    version=fake.random_int(min=1, max=5),
                    is_template=fake.boolean(chance_of_getting_true=15),
                    is_public=fake.boolean(chance_of_getting_true=25),
                    experience_points=experience,
                    character_level=level,
                    created_at=fake.date_time_between(start_date="-120d", end_date="-1d"),
                    updated_at=fake.date_time_between(start_date="-30d", end_date="now")
                )
                
                self.session.add(character)
                existing_char_names.add((user.id, character_name))
                characters_created += 1
        
        return characters_created
    
    def _generate_random_inventory(self) -> str:
        """Generate a random inventory string for a character"""
        items = [
            "Health Potion", "Rope (50 ft)", "Torch", "Rations (3 days)", 
            "Bedroll", "Backpack", "Waterskin", "Flint and Steel",
            "Gold Coins", "Silver Coins", "Gemstone", "Map",
            "Lockpicks", "Bandages", "Antidote", "Scroll"
        ]
        
        inventory_items = fake.random_elements(elements=items, length=fake.random_int(min=3, max=8), unique=True)
        return ", ".join(inventory_items)
    
    def seed_equipment(self, count_per_character: int = 4) -> int:
        """
        Seed equipment for existing characters.
        
        Args:
            count_per_character: Average number of equipment items per character
            
        Returns:
            Number of equipment items created
        """
        characters = self.session.exec(select(PlayerCharacter)).all()
        if not characters:
            return 0
        
        equipment_created = 0
        
        # Equipment templates by type
        equipment_templates = {
            EquipmentType.WEAPON: [
                {"name": "Iron Sword", "desc": "A well-balanced blade", "mods": {"strength": 2}},
                {"name": "Steel Dagger", "desc": "Quick and precise", "mods": {"dexterity": 1, "speed": 1}},
                {"name": "War Hammer", "desc": "Devastating two-handed weapon", "mods": {"strength": 3, "armor_pierce": 2}},
                {"name": "Longbow", "desc": "Ranged weapon for skilled archers", "mods": {"dexterity": 2, "range": 3}},
                {"name": "Staff of Power", "desc": "Focuses magical energy", "mods": {"intelligence": 2, "magic_power": 2}},
            ],
            EquipmentType.ARMOR: [
                {"name": "Leather Armor", "desc": "Light protection", "mods": {"defense": 2, "dexterity": -1}},
                {"name": "Chain Mail", "desc": "Flexible metal protection", "mods": {"defense": 4, "dexterity": -2}},
                {"name": "Plate Armor", "desc": "Heavy full-body protection", "mods": {"defense": 6, "strength": -1, "dexterity": -3}},
                {"name": "Mage Robes", "desc": "Cloth armor for spellcasters", "mods": {"defense": 1, "intelligence": 1, "mana": 2}},
                {"name": "Studded Leather", "desc": "Reinforced leather armor", "mods": {"defense": 3, "dexterity": -1}},
            ],
            EquipmentType.ACCESSORY: [
                {"name": "Ring of Strength", "desc": "Increases physical power", "mods": {"strength": 1}},
                {"name": "Amulet of Wisdom", "desc": "Enhances mental faculties", "mods": {"intelligence": 1}},
                {"name": "Cloak of Stealth", "desc": "Aids in remaining hidden", "mods": {"stealth": 2}},
                {"name": "Boots of Speed", "desc": "Increases movement rate", "mods": {"dexterity": 1, "speed": 2}},
                {"name": "Bracers of Defense", "desc": "Magical protection", "mods": {"defense": 1, "magic_resist": 1}},
            ],
            EquipmentType.CONSUMABLE: [
                {"name": "Health Potion", "desc": "Restores health when consumed", "mods": {"healing": 25}},
                {"name": "Mana Potion", "desc": "Restores magical energy", "mods": {"mana_restore": 20}},
                {"name": "Antidote", "desc": "Cures poison effects", "mods": {"poison_cure": 1}},
                {"name": "Strength Elixir", "desc": "Temporarily boosts strength", "mods": {"strength": 3, "duration": 10}},
                {"name": "Invisibility Potion", "desc": "Grants temporary invisibility", "mods": {"invisibility": 1, "duration": 5}},
            ],
            EquipmentType.TOOL: [
                {"name": "Lockpick Set", "desc": "Tools for opening locks", "mods": {"lockpicking": 2}},
                {"name": "Thieves' Tools", "desc": "Complete set for infiltration", "mods": {"lockpicking": 1, "trap_disable": 1}},
                {"name": "Climbing Gear", "desc": "Ropes and hooks for scaling", "mods": {"climbing": 2}},
                {"name": "Smithing Tools", "desc": "Equipment for metalworking", "mods": {"crafting": 2, "smithing": 1}},
                {"name": "Alchemy Kit", "desc": "Apparatus for potion making", "mods": {"alchemy": 2, "intelligence": 1}},
            ],
            EquipmentType.MISC: [
                {"name": "Spell Component Pouch", "desc": "Holds magical reagents", "mods": {"spell_components": 1}},
                {"name": "Holy Symbol", "desc": "Focus for divine magic", "mods": {"divine_power": 1}},
                {"name": "Traveler's Pack", "desc": "Essential adventuring supplies", "mods": {"carrying_capacity": 2}},
                {"name": "Musical Instrument", "desc": "For entertainment and bardic magic", "mods": {"charisma": 1, "performance": 2}},
                {"name": "Spellbook", "desc": "Contains magical knowledge", "mods": {"spell_slots": 2, "intelligence": 1}},
            ]
        }
        
        for character in characters:
            num_items = fake.random_int(min=2, max=count_per_character + 2)
            
            for _ in range(num_items):
                # Choose equipment type with some bias toward weapons and armor
                equipment_type = fake.random_element(elements=[
                    EquipmentType.WEAPON, EquipmentType.ARMOR, EquipmentType.ACCESSORY,
                    EquipmentType.CONSUMABLE, EquipmentType.TOOL, EquipmentType.MISC,
                    EquipmentType.WEAPON, EquipmentType.ARMOR  # Extra weight for weapons/armor
                ])
                
                template = fake.random_element(equipment_templates[equipment_type])
                
                # Add some variation to the base template
                name_variation = fake.random_element(["", "Fine ", "Crude ", "Magical ", "Ancient "])
                item_name = name_variation + template["name"]
                
                equipment = Equipment(
                    character_id=character.id,
                    name=item_name,
                    description=template["desc"],
                    item_type=equipment_type,
                    stat_modifiers=json.dumps(template["mods"]),
                    is_equipped=fake.boolean(chance_of_getting_true=30),
                    created_at=fake.date_time_between(
                        start_date=character.created_at, 
                        end_date=character.updated_at or datetime.utcnow()
                    )
                )
                
                self.session.add(equipment)
                equipment_created += 1
        
        return equipment_created
    
    def seed_character_skills(self, max_skills_per_character: int = 6) -> int:
        """
        Seed character skill relationships.
        
        Args:
            max_skills_per_character: Maximum skills per character
            
        Returns:
            Number of character-skill relationships created
        """
        characters = self.session.exec(select(PlayerCharacter)).all()
        skills = self.session.exec(select(Skill)).all()
        
        if not characters or not skills:
            return 0
        
        existing_char_skills = self.session.exec(select(CharacterSkill)).all()
        existing_pairs = {(cs.character_id, cs.skill_id) for cs in existing_char_skills}
        
        relationships_created = 0
        
        for character in characters:
            # Number of skills based on character level and randomness
            base_skills = min(character.character_level, max_skills_per_character)
            num_skills = fake.random_int(min=max(1, base_skills - 2), max=base_skills + 1)
            
            # Select appropriate skills based on character archetype (inferred from stats)
            available_skills = []
            
            # Prioritize skills based on character's highest stats
            stats = {
                "strength": character.strength,
                "dexterity": character.dexterity,
                "intelligence": character.intelligence,
                "charisma": character.charisma
            }
            primary_stat = max(stats, key=stats.get)
            
            # Map primary stats to preferred skill categories
            stat_to_categories = {
                "strength": [SkillCategory.COMBAT, SkillCategory.SURVIVAL],
                "dexterity": [SkillCategory.EXPLORATION, SkillCategory.COMBAT],
                "intelligence": [SkillCategory.MAGIC, SkillCategory.KNOWLEDGE, SkillCategory.CRAFTING],
                "charisma": [SkillCategory.SOCIAL, SkillCategory.MAGIC]
            }
            
            preferred_categories = stat_to_categories.get(primary_stat, [])
            
            # Add skills from preferred categories first
            for skill in skills:
                if skill.category in preferred_categories:
                    available_skills.append(skill)
            
            # Add other skills
            for skill in skills:
                if skill not in available_skills:
                    available_skills.append(skill)
            
            # Select skills ensuring level requirements are met
            selected_skills = []
            for skill in available_skills:
                if len(selected_skills) >= num_skills:
                    break
                
                if (character.id, skill.id) in existing_pairs:
                    continue
                
                # Check level requirement
                if skill.minimum_level > character.character_level:
                    continue
                
                # Check stat requirements
                if skill.stat_requirements:
                    try:
                        stat_reqs = json.loads(skill.stat_requirements)
                        meets_requirements = True
                        for stat, min_value in stat_reqs.items():
                            char_stat_value = getattr(character, stat, 0)
                            if char_stat_value < min_value:
                                meets_requirements = False
                                break
                        if not meets_requirements:
                            continue
                    except (json.JSONDecodeError, AttributeError):
                        continue
                
                selected_skills.append(skill)
            
            # Create character skill relationships
            for skill in selected_skills:
                # Proficiency level based on character level and randomness
                max_proficiency = min(5, character.character_level)
                proficiency = fake.random_int(min=1, max=max_proficiency)
                
                # Experience points in skill
                base_exp = proficiency * 50
                skill_exp = fake.random_int(min=base_exp, max=base_exp + 100)
                
                char_skill = CharacterSkill(
                    character_id=character.id,
                    skill_id=skill.id,
                    proficiency_level=proficiency,
                    experience_points=skill_exp,
                    acquired_at=fake.date_time_between(
                        start_date=character.created_at,
                        end_date=character.updated_at or datetime.utcnow()
                    ),
                    last_used=fake.date_time_between(
                        start_date=character.created_at,
                        end_date=datetime.utcnow()
                    ) if fake.boolean() else None
                )
                
                self.session.add(char_skill)
                existing_pairs.add((character.id, skill.id))
                relationships_created += 1
        
        return relationships_created
    
    def seed_character_versions(self, max_versions_per_character: int = 3) -> int:
        """
        Seed character version history.
        
        Args:
            max_versions_per_character: Maximum versions per character
            
        Returns:
            Number of character versions created
        """
        characters = self.session.exec(select(PlayerCharacter)).all()
        if not characters:
            return 0
        
        existing_versions = self.session.exec(select(CharacterVersion)).all()
        existing_char_versions = {cv.character_id for cv in existing_versions}
        
        versions_created = 0
        
        change_descriptions = [
            "Initial character creation",
            "Leveled up after adventure",
            "Acquired new equipment",
            "Learned new skills",
            "Stat improvements from training",
            "Updated personality traits",
            "Equipment enchantment",
            "Class advancement",
            "Completed quest milestone",
            "Character background expansion"
        ]
        
        for character in characters:
            if character.id in existing_char_versions:
                continue
            
            num_versions = fake.random_int(min=1, max=max_versions_per_character)
            
            for version_num in range(1, num_versions + 1):
                # Create character data snapshot (simplified)
                character_data = {
                    "version": version_num,
                    "name": character.name,
                    "level": max(1, character.character_level - (num_versions - version_num)),
                    "stats": {
                        "strength": max(8, character.strength - fake.random_int(0, 2)),
                        "dexterity": max(8, character.dexterity - fake.random_int(0, 2)),
                        "intelligence": max(8, character.intelligence - fake.random_int(0, 2)),
                        "charisma": max(8, character.charisma - fake.random_int(0, 2))
                    },
                    "experience_points": max(0, character.experience_points - ((num_versions - version_num) * 50)),
                    "personality_traits": character.personality_traits,
                    "skills": character.skills,
                    "inventory": character.inventory
                }
                
                version_date = character.created_at + timedelta(
                    days=(version_num - 1) * fake.random_int(1, 30)
                )
                
                char_version = CharacterVersion(
                    character_id=character.id,
                    user_id=character.user_id,
                    version_number=version_num,
                    character_data=json.dumps(character_data),
                    change_description=fake.random_element(change_descriptions),
                    created_at=version_date
                )
                
                self.session.add(char_version)
                versions_created += 1
        
        return versions_created
    
    def seed_character_templates(self, count: int = 5) -> int:
        """
        Create some public character templates.
        
        Args:
            count: Number of templates to create
            
        Returns:
            Number of templates created
        """
        # Get admin user for template ownership
        admin_user = self.session.exec(select(User).where(User.username == "admin")).first()
        if not admin_user:
            return 0
        
        existing_templates = self.session.exec(
            select(PlayerCharacter).where(PlayerCharacter.is_template == True)
        ).all()
        
        if len(existing_templates) >= count:
            return 0
        
        templates_created = 0
        
        # Template definitions
        template_definitions = [
            {
                "name": "Classic Fighter",
                "stats": {"strength": 16, "dexterity": 12, "intelligence": 10, "charisma": 12},
                "traits": "A traditional warrior focused on melee combat and physical prowess",
                "skills": "Sword combat, shield defense, armor mastery"
            },
            {
                "name": "Sneaky Rogue",
                "stats": {"strength": 10, "dexterity": 16, "intelligence": 13, "charisma": 11},
                "traits": "Master of stealth and precision, excels at infiltration and sabotage",
                "skills": "Stealth, lockpicking, trap detection, sleight of hand"
            },
            {
                "name": "Wise Wizard",
                "stats": {"strength": 8, "dexterity": 10, "intelligence": 18, "charisma": 14},
                "traits": "Scholar of the arcane arts with vast magical knowledge",
                "skills": "Elemental magic, arcane theory, spell research, enchantment"
            },
            {
                "name": "Holy Paladin",
                "stats": {"strength": 15, "dexterity": 10, "intelligence": 12, "charisma": 16},
                "traits": "Divine warrior dedicated to justice and protection of the innocent",
                "skills": "Divine magic, healing, leadership, combat righteousness"
            },
            {
                "name": "Wild Ranger",
                "stats": {"strength": 13, "dexterity": 15, "intelligence": 12, "charisma": 10},
                "traits": "Nature's guardian, expert tracker and wilderness survivor",
                "skills": "Tracking, archery, animal handling, survival, nature lore"
            }
        ]
        
        for template_def in template_definitions:
            if templates_created >= count:
                break
            
            template = PlayerCharacter(
                user_id=admin_user.id,
                name=template_def["name"],
                strength=template_def["stats"]["strength"],
                dexterity=template_def["stats"]["dexterity"],
                intelligence=template_def["stats"]["intelligence"],
                charisma=template_def["stats"]["charisma"],
                personality_traits=template_def["traits"],
                skills=template_def["skills"],
                inventory="Basic adventuring gear, appropriate weapons and armor",
                version=1,
                is_template=True,
                is_public=True,
                experience_points=0,
                character_level=1,
                created_at=fake.date_time_between(start_date="-60d", end_date="-30d"),
                updated_at=fake.date_time_between(start_date="-30d", end_date="-1d")
            )
            
            self.session.add(template)
            templates_created += 1
        
        return templates_created


# Convenience functions
def seed_database(clear_existing: bool = False) -> Dict[str, Any]:
    """
    Seed the database with sample data.
    
    Args:
        clear_existing: Whether to clear existing data first
        
    Returns:
        Summary of seeded data
    """
    with DatabaseSeeder() as seeder:
        return seeder.seed_all(clear_existing=clear_existing)


def clear_database():
    """Clear all seeded data from the database"""
    with DatabaseSeeder() as seeder:
        seeder.clear_all_data()


if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Database Seeding Utility")
    parser.add_argument("action", choices=["seed", "clear"], help="Action to perform")
    parser.add_argument("--clear", action="store_true", help="Clear existing data before seeding")
    parser.add_argument("--users", type=int, default=10, help="Number of users to create")
    
    args = parser.parse_args()
    
    try:
        if args.action == "seed":
            result = seed_database(clear_existing=args.clear)
            print("Database seeding completed:")
            print(json.dumps(result, indent=2))
            
        elif args.action == "clear":
            clear_database()
            print("Database cleared successfully")
            
    except Exception as e:
        print(f"Error: {e}")
        exit(1) 