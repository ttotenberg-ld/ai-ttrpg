from datetime import timedelta, datetime
from typing import List, Optional
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, status, Body, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select, SQLModel
from fastapi.staticfiles import StaticFiles

from database import engine, create_db_and_tables
from models import User, UserCreate, UserProfile, UserProfileUpdate, PlayerCharacter, PlayerCharacterCreate, PlayerCharacterRead, PlayerCharacterUpdate, AdventureDefinition, PlayerActionRequest, ActionOutcomeResponse, Reward, PlayerPreferences, AdventureEncounter
from auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES, 
    MAX_LOGIN_ATTEMPTS,
    create_access_token, 
    get_current_active_user, 
    get_password_hash, 
    verify_password,
    create_user_session,
    validate_refresh_token,
    blacklist_refresh_token,
    cleanup_expired_sessions,
    check_and_handle_account_lockout,
    is_account_locked,
    unlock_account_if_expired,
    create_password_reset_token,
    validate_password_reset_token,
    mark_password_reset_token_as_used,
    cleanup_expired_password_reset_tokens
)
from services import (
    CharacterValidationService,
    CharacterValidationError,
    CharacterTemplateService,
    CharacterSharingService,
    CharacterVersioningService,
    CharacterImportExportService,
    CharacterSearchService
)
from adventure_coordinator import gather_pc_info_for_adventure, construct_adventure_generation_prompt
from gm_ai import generate_adventure_from_prompt, narrate_action_outcome, perform_skill_check, SkillCheckResult, transcribe_audio_file_to_text, generate_speech_audio
from game_state_manager import parse_adventure_text_to_definition, start_adventure, get_adventure_state, get_current_encounter, end_adventure
from reward_manager import generate_adventure_reward
from media_generation import generate_encounter_image, generate_sound_effect, generate_background_music
from database_backup import DatabaseBackupManager, DatabaseBackupError

# Import security middleware and password validation
from middleware import (
    RateLimitMiddleware,
    ErrorHandlerMiddleware,
    setup_error_handlers,
    RequestLoggerMiddleware
)
from middleware.rate_limiter import auth_rate_limit, api_rate_limit, strict_rate_limit
from middleware.password_validator import validate_password_strength, get_password_policy

import shutil # For saving the uploaded file

# Response models for authentication
class TokenResponse(SQLModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshTokenRequest(SQLModel):
    refresh_token: str

class LogoutRequest(SQLModel):
    refresh_token: str

class MessageResponse(SQLModel):
    message: str

class ForgotPasswordRequest(SQLModel):
    email: str

class ResetPasswordRequest(SQLModel):
    token: str
    new_password: str

class BackupRequest(SQLModel):
    backup_name: Optional[str] = None
    compress: bool = True

class RestoreRequest(SQLModel):
    backup_path: str
    confirm: bool = False

class PasswordPolicyResponse(SQLModel):
    min_length: int
    max_length: int
    requirements: dict
    restrictions: dict

app = FastAPI()

# Setup security middleware
setup_error_handlers(app)
RateLimitMiddleware(app)
app.add_middleware(RequestLoggerMiddleware)

TEMP_AUDIO_DIR = "temp_audio_files"
TTS_STATIC_DIR = "generated_audio_files/tts"
TTS_MOUNT_ROUTE = "/audio_narration"
IMAGE_GEN_STATIC_DIR = "generated_media/images"
IMAGE_GEN_MOUNT_ROUTE = "/generated_images"
SFX_STATIC_DIR = "generated_media/sfx"
SFX_MOUNT_ROUTE = "/generated_sfx"
MUSIC_STATIC_DIR = "generated_media/music"
MUSIC_MOUNT_ROUTE = "/generated_music"

# Dependency helpers for services
def get_session():
    with Session(engine) as session:
        yield session

def get_character_validation_service(session: Session = Depends(get_session)):
    return CharacterValidationService(session)

def get_character_template_service(session: Session = Depends(get_session)):
    return CharacterTemplateService(session)

def get_character_sharing_service(session: Session = Depends(get_session)):
    return CharacterSharingService(session)

def get_character_versioning_service(session: Session = Depends(get_session)):
    return CharacterVersioningService(session)

def get_character_import_export_service(session: Session = Depends(get_session)):
    return CharacterImportExportService(session)

def get_character_search_service(session: Session = Depends(get_session)):
    return CharacterSearchService(session)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    # Create a temporary directory for audio files if it doesn't exist
    if not os.path.exists(TEMP_AUDIO_DIR):
        os.makedirs(TEMP_AUDIO_DIR)
    # Create directory for generated TTS audio files if it doesn't exist
    if not os.path.exists(TTS_STATIC_DIR):
        os.makedirs(TTS_STATIC_DIR)
    
    # Mount the directory for serving generated TTS audio files
    app.mount(TTS_MOUNT_ROUTE, StaticFiles(directory=TTS_STATIC_DIR), name="tts_audio")
    print(f"Serving TTS audio from directory: {os.path.abspath(TTS_STATIC_DIR)} at {TTS_MOUNT_ROUTE}")

    # Create directory for generated encounter images if it doesn't exist
    if not os.path.exists(IMAGE_GEN_STATIC_DIR):
        os.makedirs(IMAGE_GEN_STATIC_DIR)
    app.mount(IMAGE_GEN_MOUNT_ROUTE, StaticFiles(directory=IMAGE_GEN_STATIC_DIR), name="generated_images")
    print(f"Serving generated images from directory: {os.path.abspath(IMAGE_GEN_STATIC_DIR)} at {IMAGE_GEN_MOUNT_ROUTE}")

    # Create directory for generated SFX if it doesn't exist
    if not os.path.exists(SFX_STATIC_DIR):
        os.makedirs(SFX_STATIC_DIR)
    app.mount(SFX_MOUNT_ROUTE, StaticFiles(directory=SFX_STATIC_DIR), name="generated_sfx")
    print(f"Serving generated SFX from directory: {os.path.abspath(SFX_STATIC_DIR)} at {SFX_MOUNT_ROUTE}")

    # Create directory for generated background music if it doesn't exist
    if not os.path.exists(MUSIC_STATIC_DIR):
        os.makedirs(MUSIC_STATIC_DIR)
    app.mount(MUSIC_MOUNT_ROUTE, StaticFiles(directory=MUSIC_STATIC_DIR), name="generated_music")
    print(f"Serving generated music from directory: {os.path.abspath(MUSIC_STATIC_DIR)} at {MUSIC_MOUNT_ROUTE}")

@app.post("/users/", response_model=User)
@auth_rate_limit()
async def create_user(user: UserCreate):
    with Session(engine) as session:
        db_user = session.exec(select(User).where(User.username == user.username)).first()
        if db_user:
            raise HTTPException(status_code=400, detail="Username already registered")
        db_user_email = session.exec(select(User).where(User.email == user.email)).first()
        if db_user_email:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Validate password strength
        password_result = validate_password_strength(user.password, user.username, user.email)
        if not password_result.is_valid:
            raise HTTPException(
                status_code=400, 
                detail={
                    "message": "Password does not meet security requirements",
                    "errors": password_result.errors,
                    "suggestions": password_result.suggestions,
                    "strength_score": password_result.score,
                    "strength_level": password_result.strength_level
                }
            )
        
        hashed_password = get_password_hash(user.password)
        db_user = User(username=user.username, email=user.email, hashed_password=hashed_password)
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        return db_user

@app.post("/token", response_model=TokenResponse)
@auth_rate_limit()
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == form_data.username)).first()
        
        # If user doesn't exist, still return generic error to prevent username enumeration
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if account lockout has expired and unlock if needed
        unlock_account_if_expired(user, session)
        
        # Check if account is currently locked
        if is_account_locked(user):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account temporarily locked due to too many failed login attempts. Please try again later.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify password
        if not verify_password(form_data.password, user.hashed_password):
            # Increment failed login attempts
            user.failed_login_attempts += 1
            user.updated_at = datetime.utcnow()
            
            # Check if this failed attempt should trigger account lockout
            check_and_handle_account_lockout(user, session)
            
            # Determine error message based on whether account was just locked
            if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
                detail_msg = "Account locked due to too many failed login attempts. Please try again later."
            else:
                remaining_attempts = MAX_LOGIN_ATTEMPTS - user.failed_login_attempts
                detail_msg = f"Incorrect username or password. {remaining_attempts} attempt(s) remaining before account lockout."
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=detail_msg,
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Successful login - reset failed attempts and update last_login
        user.failed_login_attempts = 0
        user.locked_until = None  # Clear any lockout
        user.last_login = datetime.utcnow()
        user.updated_at = datetime.utcnow()
        session.add(user)
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        
        # Create refresh token session
        user_session = create_user_session(user.id, session)
        
        # Clean up expired sessions periodically
        cleanup_expired_sessions(session)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=user_session.refresh_token
        )

@app.post("/auth/logout", response_model=MessageResponse)
@auth_rate_limit()
async def logout(logout_request: LogoutRequest):
    """Logout user by blacklisting their refresh token"""
    with Session(engine) as session:
        success = blacklist_refresh_token(logout_request.refresh_token, session)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid refresh token"
            )
        return MessageResponse(message="Successfully logged out")

@app.post("/auth/refresh", response_model=TokenResponse)
@auth_rate_limit()
async def refresh_access_token(refresh_request: RefreshTokenRequest):
    """Generate new access and refresh tokens using a valid refresh token"""
    with Session(engine) as session:
        # Validate the refresh token
        user_session = validate_refresh_token(refresh_request.refresh_token, session)
        if not user_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get the user associated with the session
        user = session.get(User, user_session.user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user account is locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account temporarily locked",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Blacklist the old refresh token
        blacklist_refresh_token(refresh_request.refresh_token, session)
        
        # Create new access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        
        # Create new refresh token session
        new_user_session = create_user_session(user.id, session)
        
        # Clean up expired sessions
        cleanup_expired_sessions(session)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_user_session.refresh_token
        )

@app.post("/auth/cleanup-sessions", response_model=MessageResponse)
@api_rate_limit()
async def cleanup_expired_user_sessions():
    """Administrative endpoint to clean up expired user sessions"""
    with Session(engine) as session:
        cleaned_count = cleanup_expired_sessions(session)
        return MessageResponse(message=f"Cleaned up {cleaned_count} expired sessions")

@app.post("/auth/forgot-password", response_model=MessageResponse)
@strict_rate_limit()
async def forgot_password(request: ForgotPasswordRequest):
    """Request a password reset token for the given email address"""
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == request.email)).first()
        
        # Always return success message to prevent email enumeration attacks
        # Even if user doesn't exist, we pretend to send an email
        if not user:
            return MessageResponse(message="If an account with that email exists, a password reset link has been sent.")
        
        # Check if user account is active
        if not user.is_active:
            return MessageResponse(message="If an account with that email exists, a password reset link has been sent.")
        
        # Create password reset token
        reset_token = create_password_reset_token(user.id, session)
        
        # In a real application, you would send an email here with the reset link
        # For local development, we'll just log the token
        print(f"Password reset token for {user.email}: {reset_token.token}")
        print(f"Reset link would be: /auth/reset-password?token={reset_token.token}")
        
        # Clean up expired password reset tokens periodically
        cleanup_expired_password_reset_tokens(session)
        
        return MessageResponse(message="If an account with that email exists, a password reset link has been sent.")

@app.post("/auth/reset-password", response_model=MessageResponse)
@strict_rate_limit()
async def reset_password(request: ResetPasswordRequest):
    """Reset user password using a valid password reset token"""
    with Session(engine) as session:
        # Validate the password reset token
        reset_token = validate_password_reset_token(request.token, session)
        if not reset_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset token"
            )
        
        # Get the user associated with the token
        user = session.get(User, reset_token.user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset token"
            )
        
        # Validate new password strength
        password_result = validate_password_strength(request.new_password, user.username, user.email)
        if not password_result.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Password does not meet security requirements",
                    "errors": password_result.errors,
                    "suggestions": password_result.suggestions,
                    "strength_score": password_result.score,
                    "strength_level": password_result.strength_level
                }
            )
        
        # Update user password
        user.hashed_password = get_password_hash(request.new_password)
        user.failed_login_attempts = 0  # Reset failed attempts
        user.locked_until = None  # Clear any account lockout
        user.updated_at = datetime.utcnow()
        session.add(user)
        
        # Mark the password reset token as used
        mark_password_reset_token_as_used(request.token, session)
        
        # Invalidate all existing user sessions for security
        from models import UserSession
        existing_sessions = session.exec(
            select(UserSession).where(
                UserSession.user_id == user.id,
                UserSession.is_active == True
            )
        ).all()
        
        for user_session in existing_sessions:
            user_session.is_active = False
            session.add(user_session)
        
        session.commit()
        
        return MessageResponse(message="Password has been successfully reset. Please log in with your new password.")

@app.get("/auth/password-policy", response_model=PasswordPolicyResponse)
async def get_password_policy_info():
    """Get current password policy requirements"""
    policy = get_password_policy()
    return PasswordPolicyResponse(**policy)

@app.get("/users/profile", response_model=UserProfile)
async def get_user_profile(current_user: User = Depends(get_current_active_user)):
    """Get current user's profile information"""
    return UserProfile(
        username=current_user.username,
        email=current_user.email,
        email_verified=current_user.email_verified,
        is_active=current_user.is_active,
        last_login=current_user.last_login,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )

@app.patch("/users/profile", response_model=UserProfile)
async def update_user_profile(
    profile_update: UserProfileUpdate,
    current_user: User = Depends(get_current_active_user)
):
    """Update current user's profile information"""
    with Session(engine) as session:
        # Get the user from the database to ensure we have the latest data
        user = session.get(User, current_user.id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get the update data, excluding unset fields
        update_data = profile_update.model_dump(exclude_unset=True)
        
        # Validate and apply updates
        for field, value in update_data.items():
            if field == "username":
                if value and len(value.strip()) == 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Username cannot be empty"
                    )
                
                # Check if username is already taken by another user
                existing_user = session.exec(
                    select(User).where(User.username == value, User.id != user.id)
                ).first()
                if existing_user:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Username already taken"
                    )
                
                user.username = value.strip()
            
            elif field == "email":
                if value and len(value.strip()) == 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email cannot be empty"
                    )
                
                # Basic email validation
                if value and "@" not in value:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid email format"
                    )
                
                # Check if email is already taken by another user
                existing_user = session.exec(
                    select(User).where(User.email == value, User.id != user.id)
                ).first()
                if existing_user:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email already taken"
                    )
                
                # If email is being changed, mark as unverified
                if value != user.email:
                    user.email_verified = False
                
                user.email = value.strip()
        
        # Update the updated_at timestamp
        user.updated_at = datetime.utcnow()
        
        session.add(user)
        session.commit()
        session.refresh(user)
        
        # Return updated profile
        return UserProfile(
            username=user.username,
            email=user.email,
            email_verified=user.email_verified,
            is_active=user.is_active,
            last_login=user.last_login,
            created_at=user.created_at,
            updated_at=user.updated_at
        )

@app.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

@app.post("/pcs/", response_model=PlayerCharacterRead)
async def create_player_character(
    *, 
    pc_in: PlayerCharacterCreate, 
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
    validation_service: CharacterValidationService = Depends(get_character_validation_service),
    versioning_service: CharacterVersioningService = Depends(get_character_versioning_service)
):
    """Create a new player character with validation and initial versioning"""
    
    # Validate character creation data
    validation_result = validation_service.validate_character_creation(pc_in)
    if not validation_result["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Character validation failed: {', '.join(validation_result['errors'])}"
        )
    
    # Create character with enhanced fields
    db_pc = PlayerCharacter(
        user_id=current_user.id,
        name=pc_in.name,
        strength=pc_in.strength,
        dexterity=pc_in.dexterity,
        intelligence=pc_in.intelligence,
        charisma=pc_in.charisma,
        personality_traits=pc_in.personality_traits,
        skills=pc_in.skills,
        inventory=pc_in.inventory,
        version=1,
        is_template=False,
        is_public=False,
        experience_points=0,
        character_level=1
    )
    
    session.add(db_pc)
    session.commit()
    session.refresh(db_pc)
    
    # Create initial character snapshot
    snapshot_result = versioning_service.create_character_snapshot(
        character_id=db_pc.id,
        user_id=current_user.id,
        change_description="Initial character creation",
        auto_increment_version=False
    )
    
    if not snapshot_result["success"]:
        print(f"Warning: Failed to create initial character snapshot: {snapshot_result['errors']}")
    
    return db_pc

@app.get("/pcs/", response_model=List[PlayerCharacterRead])
async def read_player_characters_for_user(
    *, 
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
    search_service: CharacterSearchService = Depends(get_character_search_service),
    search: Optional[str] = None,
    level_min: Optional[int] = None,
    level_max: Optional[int] = None,
    is_template: Optional[bool] = None
):
    """Get user's characters with optional search and filtering"""
    
    # Build search criteria
    search_criteria = {}
    if search:
        search_criteria["name"] = search
    if level_min is not None:
        search_criteria["level_min"] = level_min
    if level_max is not None:
        search_criteria["level_max"] = level_max
    if is_template is not None:
        search_criteria["is_template"] = is_template
    
    # Use search service if criteria provided, otherwise fallback to simple query
    if search_criteria:
        result = search_service.search_user_characters(current_user.id, search_criteria)
        if result["success"]:
            return result["characters"]
    
    # Fallback to simple query
    pcs = session.exec(select(PlayerCharacter).where(PlayerCharacter.user_id == current_user.id)).all()
    return pcs

@app.get("/pcs/{pc_id}", response_model=PlayerCharacterRead)
async def read_player_character(
    *, 
    pc_id: int, 
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """Get a specific character by ID"""
    pc = session.get(PlayerCharacter, pc_id)
    if not pc:
        raise HTTPException(status_code=404, detail="Player Character not found")
    if pc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this character")
    return pc

@app.patch("/pcs/{pc_id}", response_model=PlayerCharacterRead)
async def update_player_character(
    *, 
    pc_id: int, 
    pc_update: PlayerCharacterUpdate, 
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
    validation_service: CharacterValidationService = Depends(get_character_validation_service),
    versioning_service: CharacterVersioningService = Depends(get_character_versioning_service)
):
    """Update a player character with validation and versioning"""
    
    db_pc = session.get(PlayerCharacter, pc_id)
    if not db_pc:
        raise HTTPException(status_code=404, detail="Player Character not found")
    if db_pc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this character")

    # Validate character update
    validation_result = validation_service.validate_character_update(db_pc, pc_update)
    if not validation_result["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Character update validation failed: {', '.join(validation_result['errors'])}"
        )

    # Create version snapshot before updating
    snapshot_result = versioning_service.create_character_snapshot(
        character_id=db_pc.id,
        user_id=current_user.id,
        change_description="Character update",
        auto_increment_version=True
    )
    
    if not snapshot_result["success"]:
        print(f"Warning: Failed to create character snapshot: {snapshot_result['errors']}")

    # Get the update data, excluding unset fields to prevent overwriting with None
    update_data = pc_update.model_dump(exclude_unset=True)
    
    # Update the model fields including updated_at timestamp
    for key, value in update_data.items():
        setattr(db_pc, key, value)
    
    db_pc.updated_at = datetime.utcnow()
    
    session.add(db_pc)
    session.commit()
    session.refresh(db_pc)
    return db_pc

@app.delete("/pcs/{pc_id}", response_model=MessageResponse)
async def delete_player_character(
    *, 
    pc_id: int, 
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """Delete a player character"""
    db_pc = session.get(PlayerCharacter, pc_id)
    if not db_pc:
        raise HTTPException(status_code=404, detail="Player Character not found")
    if db_pc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this character")

    session.delete(db_pc)
    session.commit()
    return MessageResponse(message="Character successfully deleted")

# Enhanced Character Endpoints

@app.get("/pcs/search/public", response_model=List[PlayerCharacterRead])
async def search_public_characters(
    *,
    search_service: CharacterSearchService = Depends(get_character_search_service),
    current_user: Optional[User] = Depends(get_current_active_user),
    search: Optional[str] = None,
    level_min: Optional[int] = None,
    level_max: Optional[int] = None,
    limit: int = 50,
    offset: int = 0
):
    """Search public characters"""
    search_criteria = {}
    if search:
        search_criteria["name"] = search
    if level_min is not None:
        search_criteria["level_min"] = level_min
    if level_max is not None:
        search_criteria["level_max"] = level_max
    
    user_id = current_user.id if current_user else None
    result = search_service.search_public_characters(user_id, search_criteria)
    
    if result["success"]:
        return result["characters"]
    else:
        raise HTTPException(status_code=500, detail=f"Search failed: {result['errors']}")

@app.patch("/pcs/{pc_id}/share", response_model=PlayerCharacterRead)
async def share_character(
    *,
    pc_id: int,
    is_public: bool,
    current_user: User = Depends(get_current_active_user),
    sharing_service: CharacterSharingService = Depends(get_character_sharing_service)
):
    """Share or unshare a character (make public/private)"""
    result = sharing_service.share_character(pc_id, current_user.id, is_public)
    
    if result["success"]:
        return result["character"]
    else:
        raise HTTPException(status_code=400, detail=f"Failed to update sharing: {result['errors']}")

@app.get("/pcs/{pc_id}/versions", response_model=List[dict])
async def get_character_version_history(
    *,
    pc_id: int,
    current_user: User = Depends(get_current_active_user),
    versioning_service: CharacterVersioningService = Depends(get_character_versioning_service),
    limit: int = 20
):
    """Get character version history"""
    result = versioning_service.get_character_version_history(pc_id, current_user.id, limit)
    
    if result["success"]:
        return result["versions"]
    else:
        raise HTTPException(status_code=400, detail=f"Failed to get version history: {result['errors']}")

@app.post("/pcs/{pc_id}/versions", response_model=dict)
async def create_character_snapshot(
    *,
    pc_id: int,
    change_description: str,
    current_user: User = Depends(get_current_active_user),
    versioning_service: CharacterVersioningService = Depends(get_character_versioning_service)
):
    """Create a manual character snapshot"""
    result = versioning_service.create_character_snapshot(
        pc_id, current_user.id, change_description, auto_increment_version=True
    )
    
    if result["success"]:
        return result["version"]
    else:
        raise HTTPException(status_code=400, detail=f"Failed to create snapshot: {result['errors']}")

@app.post("/pcs/{pc_id}/restore/{version_number}", response_model=PlayerCharacterRead)
async def restore_character_to_version(
    *,
    pc_id: int,
    version_number: int,
    current_user: User = Depends(get_current_active_user),
    versioning_service: CharacterVersioningService = Depends(get_character_versioning_service)
):
    """Restore character to a specific version"""
    result = versioning_service.restore_character_to_version(
        pc_id, current_user.id, version_number, create_backup=True
    )
    
    if result["success"]:
        return result["character"]
    else:
        raise HTTPException(status_code=400, detail=f"Failed to restore character: {result['errors']}")

@app.post("/templates/", response_model=PlayerCharacterRead)
async def create_character_template(
    *,
    template_data: PlayerCharacterCreate,
    is_public: bool = False,
    current_user: User = Depends(get_current_active_user),
    template_service: CharacterTemplateService = Depends(get_character_template_service)
):
    """Create a new character template"""
    result = template_service.create_character_template(
        current_user.id, template_data, is_public=is_public
    )
    
    if result["success"]:
        return result["template"]
    else:
        raise HTTPException(status_code=400, detail=f"Failed to create template: {result['errors']}")

@app.post("/templates/{template_id}/create-character", response_model=PlayerCharacterRead)
async def create_character_from_template(
    *,
    template_id: int,
    character_name: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    template_service: CharacterTemplateService = Depends(get_character_template_service)
):
    """Create a new character from a template"""
    result = template_service.create_character_from_template(
        template_id, current_user.id, character_name
    )
    
    if result["success"]:
        return result["character"]
    else:
        raise HTTPException(status_code=400, detail=f"Failed to create character from template: {result['errors']}")

@app.get("/templates/public", response_model=List[PlayerCharacterRead])
async def get_public_templates(
    *,
    template_service: CharacterTemplateService = Depends(get_character_template_service),
    search: Optional[str] = None
):
    """Get public character templates"""
    templates = template_service.get_public_templates(search_term=search)
    return templates

# Response model for starting an adventure
class StartAdventureResponse(SQLModel):
    adventure_id: str
    adventure_definition: AdventureDefinition
    # We could also include the first encounter details here directly

@app.post("/adventures/generate/{pc_id}", response_model=StartAdventureResponse)
async def generate_new_adventure(
    *, 
    pc_id: int, 
    preferences: Optional[PlayerPreferences] = Body(None),
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(lambda: Session(engine))
):
    pc = session.get(PlayerCharacter, pc_id)
    if not pc:
        raise HTTPException(status_code=404, detail="Player Character not found")
    if pc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to use this character for adventure generation")

    pc_info = gather_pc_info_for_adventure(pc)
    
    # Convert Pydantic model to dict if preferences are provided, else None
    preferences_dict = preferences.model_dump() if preferences else None
    
    adventure_prompt = construct_adventure_generation_prompt(pc_info, player_preferences=preferences_dict)
    generated_adventure_text = await generate_adventure_from_prompt(adventure_prompt)

    adventure_def: Optional[AdventureDefinition] = parse_adventure_text_to_definition(generated_adventure_text)
    if not adventure_def:
        # If parsing fails, try to use the fallback from the AI generation if it was an API error
        if "Error from AI" in generated_adventure_text and "Fallback Adventure:" in generated_adventure_text:
            fallback_text = generated_adventure_text.split("Fallback Adventure:", 1)[1].strip()
            adventure_def = parse_adventure_text_to_definition(fallback_text)
        
        if not adventure_def: # If still no definition, raise error
            raise HTTPException(status_code=500, detail="Failed to parse generated adventure content from AI.")

    # Generate images for each encounter before starting the adventure
    if adventure_def and adventure_def.encounters:
        for encounter in adventure_def.encounters:
            # Use a concise prompt based on description and challenge
            image_prompt = f"{encounter.description} {encounter.challenge_objective}"
            # The generate_encounter_image function returns a relative path like "generated_media/images/filename.png"
            relative_image_path = await generate_encounter_image(prompt_text=image_prompt)
            if relative_image_path:
                # Construct the full URL using the mount route and the filename
                image_filename = os.path.basename(relative_image_path)
                encounter.image_url = f"{IMAGE_GEN_MOUNT_ROUTE}/{image_filename}"
                print(f"Generated image for encounter, URL: {encounter.image_url}")
            else:
                print(f"Failed to generate image for encounter: {encounter.description[:50]}...")
            
            # Generate background music for the encounter (placeholder)
            # Prompt could be based on encounter description, theme, or overall adventure goal
            music_prompt = f"Background music for a D&D encounter: {encounter.description}"
            relative_music_path = await generate_background_music(prompt_text=music_prompt)
            if relative_music_path:
                music_filename = os.path.basename(relative_music_path)
                encounter.background_music_url = f"{MUSIC_MOUNT_ROUTE}/{music_filename}"
                print(f"Generated background music for encounter, URL: {encounter.background_music_url}")
            else:
                print(f"Failed to generate background music for encounter: {encounter.description[:50]}...")

    adventure_id = start_adventure(adventure_def, pc.id)
    
    return StartAdventureResponse(adventure_id=adventure_id, adventure_definition=adventure_def)

@app.post("/adventures/{adventure_id}/action", response_model=ActionOutcomeResponse)
async def take_player_action(
    *, 
    adventure_id: str,
    action_request: PlayerActionRequest,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(lambda: Session(engine))
):
    adventure_state = get_adventure_state(adventure_id)
    if not adventure_state:
        raise HTTPException(status_code=404, detail="Adventure not found or not active.")

    pc = session.get(PlayerCharacter, adventure_state.pc_id)
    if not pc or pc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Player character not found or not authorized for this adventure.")

    current_encounter_details = get_current_encounter(adventure_id)
    if not current_encounter_details:
        # This might mean the adventure is over or in an invalid state
        # For now, let's assume the AI can still narrate if there's no specific encounter object
        # A more robust system would handle adventure completion explicitly here.
        scene_desc = adventure_state.adventure_definition.conclusion if adventure_state.current_encounter_index >= len(adventure_state.adventure_definition.encounters) else "An unknown space..."
    else:
        scene_desc = current_encounter_details.description

    skill_check_performed: Optional[SkillCheckResult] = None

    if action_request.stat_to_check and action_request.suggested_dc is not None:
        modifier = 0
        stat_value = 0
        # Simplified stat to modifier conversion. A real system might have this on the PC model or a utility.
        if action_request.stat_to_check == "strength": stat_value = pc.strength
        elif action_request.stat_to_check == "dexterity": stat_value = pc.dexterity
        elif action_request.stat_to_check == "intelligence": stat_value = pc.intelligence
        elif action_request.stat_to_check == "charisma": stat_value = pc.charisma
        else:
            # If stat is not recognized, could default to 0 modifier or raise error
            # For now, we proceed without a specific stat modifier if not matched.
            pass 
        
        if stat_value > 0: # Check if stat_value was actually set
            modifier = (stat_value - 10) // 2

        skill_check_performed = perform_skill_check(
            pc_modifier=modifier, 
            dc=action_request.suggested_dc
            # dice_to_roll, advantage, disadvantage can be added later
        )
    
    narration = await narrate_action_outcome(
        scene_description=scene_desc,
        pc_action=action_request.action_text,
        skill_check_result=skill_check_performed
    )

    # Generate TTS audio for the narration
    audio_narration_file_path: Optional[str] = None
    audio_narration_url: Optional[str] = None
    sound_effect_url: Optional[str] = None

    if narration and not narration.startswith("Error from AI") and not narration.startswith("The story takes an unexpected turn..."):
        # We might want to extract just the main narration if there are also [voice cues] for frontend processing
        # For now, passing full narration to TTS
        audio_narration_file_path = await generate_speech_audio(text=narration)
        if audio_narration_file_path:
            # audio_narration_file_path is like "generated_audio_files/tts/filename.mp3"
            # We need to construct the URL based on the mount point
            # filename will be os.path.basename(audio_narration_file_path)
            audio_filename = os.path.basename(audio_narration_file_path)
            audio_narration_url = f"{TTS_MOUNT_ROUTE}/{audio_filename}"
    
    # Generate a sound effect based on the action or narration (placeholder)
    if narration: # Or base the prompt on action_request.action_text
        sfx_prompt = narration # Or a more targeted prompt derived from narration/action
        relative_sfx_path = await generate_sound_effect(prompt_text=sfx_prompt)
        if relative_sfx_path:
            sfx_filename = os.path.basename(relative_sfx_path)
            sound_effect_url = f"{SFX_MOUNT_ROUTE}/{sfx_filename}"
            print(f"Generated SFX, URL: {sound_effect_url}")
        else:
            print(f"Failed to generate SFX for prompt: {sfx_prompt[:50]}...")

    # TODO: Here, based on narration or explicit AI cues (not yet implemented):
    # - Advance encounter if appropriate (advance_to_next_encounter(adventure_id))
    # - Update PC state (HP, inventory) if narration implies changes
    # - Determine if adventure is over

    return ActionOutcomeResponse(
        narration=narration,
        skill_check_result_desc=skill_check_performed.description if skill_check_performed else None,
        skill_check_success=skill_check_performed.success if skill_check_performed else None,
        audio_narration_url=audio_narration_url,
        sound_effect_url=sound_effect_url
    )

@app.post("/adventures/{adventure_id}/complete", response_model=Reward)
async def complete_adventure_and_get_reward(
    *, 
    adventure_id: str,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(lambda: Session(engine))
):
    adventure_state = get_adventure_state(adventure_id)
    if not adventure_state:
        raise HTTPException(status_code=404, detail="Adventure not found or not active.")

    pc = session.get(PlayerCharacter, adventure_state.pc_id)
    if not pc or pc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to complete this adventure.")

    reward = generate_adventure_reward(pc=pc)
    
    end_adventure(adventure_id)
    
    return reward

@app.get("/")
async def root():
    return {"message": "Hello World"}

# New endpoint for Speech-to-Text
@app.post("/audio/stt/")
async def speech_to_text_endpoint(audio_file: UploadFile = File(...)):
    # Ensure the temp directory exists (it should from startup, but good to be safe)
    if not os.path.exists(TEMP_AUDIO_DIR):
        os.makedirs(TEMP_AUDIO_DIR)

    temp_file_path = os.path.join(TEMP_AUDIO_DIR, audio_file.filename)
    
    try:
        # Save the uploaded file to a temporary location
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
        
        # Transcribe the audio file
        transcribed_text = await transcribe_audio_file_to_text(temp_file_path)
        
        if transcribed_text.startswith("Error:"):
            raise HTTPException(status_code=500, detail=transcribed_text)
            
        return {"transcription": transcribed_text}
    except HTTPException: # Re-raise HTTPExceptions directly
        raise
    except Exception as e:
        # Catch any other exceptions during file handling or transcription call
        raise HTTPException(status_code=500, detail=f"Failed to process audio: {str(e)}")
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# Database Backup and Restore Endpoints (Admin only)

@app.post("/admin/backup", response_model=dict)
async def create_database_backup(
    backup_request: BackupRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Create a database backup (admin only)"""
    # Note: In a real application, you'd want to check if user is an admin
    # For now, any authenticated user can create backups
    
    try:
        manager = DatabaseBackupManager()
        result = manager.create_backup(
            backup_name=backup_request.backup_name,
            compress=backup_request.compress
        )
        return result
    except DatabaseBackupError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")

@app.post("/admin/restore", response_model=dict)
async def restore_database_backup(
    restore_request: RestoreRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Restore database from backup (admin only)"""
    # Note: In a real application, you'd want to check if user is an admin
    # This is a destructive operation that should be heavily restricted
    
    try:
        manager = DatabaseBackupManager()
        result = manager.restore_backup(
            backup_path=restore_request.backup_path,
            confirm=restore_request.confirm
        )
        return result
    except DatabaseBackupError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restore failed: {str(e)}")

@app.get("/admin/backups", response_model=List[dict])
async def list_database_backups(
    current_user: User = Depends(get_current_active_user)
):
    """List available database backups (admin only)"""
    try:
        manager = DatabaseBackupManager()
        return manager.list_backups()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list backups: {str(e)}")

@app.delete("/admin/backups/cleanup", response_model=dict)
async def cleanup_old_backups(
    keep_count: int = 10,
    current_user: User = Depends(get_current_active_user)
):
    """Clean up old backup files (admin only)"""
    try:
        manager = DatabaseBackupManager()
        deleted_count = manager.cleanup_old_backups(keep_count)
        return {"deleted_count": deleted_count, "kept_count": keep_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@app.get("/admin/database/info", response_model=dict)
async def get_database_information(
    current_user: User = Depends(get_current_active_user)
):
    """Get database configuration information (admin only)"""
    try:
        from database import get_database_info
        return get_database_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get database info: {str(e)}") 