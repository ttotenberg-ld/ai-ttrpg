"""
Password Strength Validation - Task 5.3
Implements password strength validation with configurable policies
"""

import os
import re
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PasswordPolicy:
    """Password policy configuration"""
    min_length: int = 8
    max_length: int = 128
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digits: bool = True
    require_special_chars: bool = True
    min_uppercase: int = 1
    min_lowercase: int = 1
    min_digits: int = 1
    min_special_chars: int = 1
    allow_whitespace: bool = False
    forbidden_patterns: List[str] = None
    forbidden_words: List[str] = None
    max_consecutive_chars: int = 3
    prevent_username_similarity: bool = True
    prevent_email_similarity: bool = True

class PasswordStrengthResult:
    """Result of password strength validation"""
    
    def __init__(self, is_valid: bool, score: int = 0, errors: List[str] = None, suggestions: List[str] = None):
        self.is_valid = is_valid
        self.score = score  # 0-100 strength score
        self.errors = errors or []
        self.suggestions = suggestions or []
        self.strength_level = self._calculate_strength_level()
    
    def _calculate_strength_level(self) -> str:
        """Calculate strength level based on score"""
        if self.score >= 80:
            return "Very Strong"
        elif self.score >= 60:
            return "Strong"
        elif self.score >= 40:
            return "Medium"
        elif self.score >= 20:
            return "Weak"
        else:
            return "Very Weak"

class PasswordValidator:
    """Password strength validator with configurable policies"""
    
    def __init__(self, policy: Optional[PasswordPolicy] = None):
        self.policy = policy or self._load_default_policy()
        self._compile_patterns()
    
    def _load_default_policy(self) -> PasswordPolicy:
        """Load default password policy from environment variables"""
        return PasswordPolicy(
            min_length=int(os.getenv("PASSWORD_MIN_LENGTH", "8")),
            max_length=int(os.getenv("PASSWORD_MAX_LENGTH", "128")),
            require_uppercase=os.getenv("PASSWORD_REQUIRE_UPPERCASE", "true").lower() == "true",
            require_lowercase=os.getenv("PASSWORD_REQUIRE_LOWERCASE", "true").lower() == "true",
            require_digits=os.getenv("PASSWORD_REQUIRE_DIGITS", "true").lower() == "true",
            require_special_chars=os.getenv("PASSWORD_REQUIRE_SPECIAL", "true").lower() == "true",
            min_uppercase=int(os.getenv("PASSWORD_MIN_UPPERCASE", "1")),
            min_lowercase=int(os.getenv("PASSWORD_MIN_LOWERCASE", "1")),
            min_digits=int(os.getenv("PASSWORD_MIN_DIGITS", "1")),
            min_special_chars=int(os.getenv("PASSWORD_MIN_SPECIAL", "1")),
            allow_whitespace=os.getenv("PASSWORD_ALLOW_WHITESPACE", "false").lower() == "true",
            max_consecutive_chars=int(os.getenv("PASSWORD_MAX_CONSECUTIVE", "3")),
            prevent_username_similarity=os.getenv("PASSWORD_PREVENT_USERNAME_SIMILARITY", "true").lower() == "true",
            prevent_email_similarity=os.getenv("PASSWORD_PREVENT_EMAIL_SIMILARITY", "true").lower() == "true",
            forbidden_patterns=self._load_forbidden_patterns(),
            forbidden_words=self._load_forbidden_words()
        )
    
    def _load_forbidden_patterns(self) -> List[str]:
        """Load forbidden patterns from environment"""
        patterns_env = os.getenv("PASSWORD_FORBIDDEN_PATTERNS", "")
        if patterns_env:
            return [p.strip() for p in patterns_env.split(",") if p.strip()]
        
        # Default forbidden patterns
        return [
            r"(.)\1{2,}",  # 3+ consecutive identical characters
            r"123456|654321|abcdef|qwerty|password|admin|root",  # Common patterns
            r"^\d+$",  # Only digits
            r"^[a-zA-Z]+$",  # Only letters
        ]
    
    def _load_forbidden_words(self) -> List[str]:
        """Load forbidden words from environment"""
        words_env = os.getenv("PASSWORD_FORBIDDEN_WORDS", "")
        if words_env:
            return [w.strip().lower() for w in words_env.split(",") if w.strip()]
        
        # Default forbidden words
        return [
            "password", "admin", "root", "user", "guest", "test",
            "123456", "qwerty", "abc123", "welcome", "login",
            "pass", "secret", "master", "system", "default"
        ]
    
    def _compile_patterns(self):
        """Compile regex patterns for validation"""
        self.uppercase_pattern = re.compile(r"[A-Z]")
        self.lowercase_pattern = re.compile(r"[a-z]")
        self.digit_pattern = re.compile(r"\d")
        self.special_char_pattern = re.compile(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]")
        self.whitespace_pattern = re.compile(r"\s")
        
        # Compile forbidden patterns
        self.forbidden_regex_patterns = []
        if self.policy.forbidden_patterns:
            for pattern in self.policy.forbidden_patterns:
                try:
                    self.forbidden_regex_patterns.append(re.compile(pattern, re.IGNORECASE))
                except re.error as e:
                    logger.warning(f"Invalid regex pattern '{pattern}': {e}")
    
    def validate(self, password: str, username: str = None, email: str = None) -> PasswordStrengthResult:
        """
        Validate password strength according to policy
        
        Args:
            password: Password to validate
            username: Optional username to check similarity
            email: Optional email to check similarity
            
        Returns:
            PasswordStrengthResult with validation results
        """
        errors = []
        suggestions = []
        score = 0
        
        # Length validation
        if len(password) < self.policy.min_length:
            errors.append(f"Password must be at least {self.policy.min_length} characters long")
            suggestions.append(f"Add {self.policy.min_length - len(password)} more characters")
        
        if len(password) > self.policy.max_length:
            errors.append(f"Password must not exceed {self.policy.max_length} characters")
        
        # Character type validation
        uppercase_count = len(self.uppercase_pattern.findall(password))
        lowercase_count = len(self.lowercase_pattern.findall(password))
        digit_count = len(self.digit_pattern.findall(password))
        special_count = len(self.special_char_pattern.findall(password))
        
        if self.policy.require_uppercase and uppercase_count < self.policy.min_uppercase:
            errors.append(f"Password must contain at least {self.policy.min_uppercase} uppercase letter(s)")
            suggestions.append("Add uppercase letters (A-Z)")
        
        if self.policy.require_lowercase and lowercase_count < self.policy.min_lowercase:
            errors.append(f"Password must contain at least {self.policy.min_lowercase} lowercase letter(s)")
            suggestions.append("Add lowercase letters (a-z)")
        
        if self.policy.require_digits and digit_count < self.policy.min_digits:
            errors.append(f"Password must contain at least {self.policy.min_digits} digit(s)")
            suggestions.append("Add numbers (0-9)")
        
        if self.policy.require_special_chars and special_count < self.policy.min_special_chars:
            errors.append(f"Password must contain at least {self.policy.min_special_chars} special character(s)")
            suggestions.append("Add special characters (!@#$%^&*)")
        
        # Whitespace validation
        if not self.policy.allow_whitespace and self.whitespace_pattern.search(password):
            errors.append("Password cannot contain whitespace characters")
            suggestions.append("Remove spaces, tabs, and newlines")
        
        # Consecutive characters validation
        if self._has_excessive_consecutive_chars(password):
            errors.append(f"Password cannot have more than {self.policy.max_consecutive_chars} consecutive identical characters")
            suggestions.append("Avoid repeating the same character multiple times")
        
        # Forbidden patterns validation
        for pattern in self.forbidden_regex_patterns:
            if pattern.search(password):
                errors.append("Password contains forbidden pattern")
                suggestions.append("Avoid common patterns like '123456', 'qwerty', or repetitive characters")
                break
        
        # Forbidden words validation
        password_lower = password.lower()
        for word in (self.policy.forbidden_words or []):
            if word in password_lower:
                errors.append(f"Password cannot contain the word '{word}'")
                suggestions.append("Avoid common words and dictionary terms")
                break
        
        # Username similarity validation
        if username and self.policy.prevent_username_similarity:
            if self._is_too_similar(password, username):
                errors.append("Password is too similar to username")
                suggestions.append("Make password more different from your username")
        
        # Email similarity validation
        if email and self.policy.prevent_email_similarity:
            email_local = email.split("@")[0] if "@" in email else email
            if self._is_too_similar(password, email_local):
                errors.append("Password is too similar to email address")
                suggestions.append("Make password more different from your email")
        
        # Calculate strength score
        score = self._calculate_strength_score(password, uppercase_count, lowercase_count, digit_count, special_count)
        
        # Additional suggestions based on score
        if score < 60 and not suggestions:
            suggestions.extend([
                "Make password longer",
                "Use a mix of uppercase, lowercase, numbers, and symbols",
                "Avoid predictable patterns"
            ])
        
        is_valid = len(errors) == 0
        
        return PasswordStrengthResult(
            is_valid=is_valid,
            score=score,
            errors=errors,
            suggestions=suggestions
        )
    
    def _has_excessive_consecutive_chars(self, password: str) -> bool:
        """Check for excessive consecutive identical characters"""
        if self.policy.max_consecutive_chars <= 0:
            return False
        
        count = 1
        for i in range(1, len(password)):
            if password[i] == password[i-1]:
                count += 1
                if count > self.policy.max_consecutive_chars:
                    return True
            else:
                count = 1
        return False
    
    def _is_too_similar(self, password: str, reference: str, threshold: float = 0.7) -> bool:
        """Check if password is too similar to reference string"""
        if not reference:
            return False
        
        password_lower = password.lower()
        reference_lower = reference.lower()
        
        # Check if password contains reference or vice versa
        if reference_lower in password_lower or password_lower in reference_lower:
            return True
        
        # Simple character overlap check
        common_chars = set(password_lower) & set(reference_lower)
        similarity = len(common_chars) / max(len(set(password_lower)), len(set(reference_lower)))
        
        return similarity > threshold
    
    def _calculate_strength_score(self, password: str, uppercase: int, lowercase: int, digits: int, special: int) -> int:
        """Calculate password strength score (0-100)"""
        score = 0
        
        # Length scoring (up to 25 points)
        length_score = min(25, (len(password) - 8) * 2 + 10) if len(password) >= 8 else 0
        score += length_score
        
        # Character variety scoring (up to 40 points)
        if uppercase > 0:
            score += 10
        if lowercase > 0:
            score += 10
        if digits > 0:
            score += 10
        if special > 0:
            score += 10
        
        # Character count scoring (up to 20 points)
        score += min(5, uppercase)
        score += min(5, lowercase)
        score += min(5, digits)
        score += min(5, special)
        
        # Entropy bonus (up to 15 points)
        unique_chars = len(set(password))
        entropy_score = min(15, unique_chars)
        score += entropy_score
        
        return min(100, score)
    
    def get_policy_description(self) -> Dict[str, any]:
        """Get human-readable description of current password policy"""
        return {
            "min_length": self.policy.min_length,
            "max_length": self.policy.max_length,
            "requirements": {
                "uppercase_letters": f"At least {self.policy.min_uppercase}" if self.policy.require_uppercase else "Not required",
                "lowercase_letters": f"At least {self.policy.min_lowercase}" if self.policy.require_lowercase else "Not required",
                "digits": f"At least {self.policy.min_digits}" if self.policy.require_digits else "Not required",
                "special_characters": f"At least {self.policy.min_special_chars}" if self.policy.require_special_chars else "Not required",
            },
            "restrictions": {
                "whitespace_allowed": self.policy.allow_whitespace,
                "max_consecutive_chars": self.policy.max_consecutive_chars,
                "prevent_username_similarity": self.policy.prevent_username_similarity,
                "prevent_email_similarity": self.policy.prevent_email_similarity,
            }
        }

# Global password validator instance
password_validator = PasswordValidator()

def validate_password_strength(password: str, username: str = None, email: str = None) -> PasswordStrengthResult:
    """
    Convenience function to validate password strength
    
    Args:
        password: Password to validate
        username: Optional username to check similarity
        email: Optional email to check similarity
        
    Returns:
        PasswordStrengthResult with validation results
    """
    return password_validator.validate(password, username, email)

def get_password_policy() -> Dict[str, any]:
    """Get current password policy description"""
    return password_validator.get_policy_description() 