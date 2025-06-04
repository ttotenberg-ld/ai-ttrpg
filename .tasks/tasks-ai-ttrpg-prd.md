## Relevant Files

- `src/components/HomeScreen.tsx` - Main component for the home screen, handling PC management and adventure initiation.
- `src/components/AdventureInterface.tsx` - Component for displaying adventure content, imagery, and handling user interaction during gameplay.
- `src/services/AIService.ts` - Service for interacting with the AI GM, including sending player input and receiving AI responses.
- `src/services/CharacterService.ts` - Service for managing player character data (creation, loading, progression).
- `src/services/AdventureService.ts` - Service for adventure generation and management.
- `server/main.py` - Main Python backend file.
- `server/adventure_coordinator.py` - Module for collecting PC info and constructing prompts for AI.
- `server/gm_ai.py` - Module for processing audio, generating narrative, managing game state, and handling dice rolls.
- `server/media_generation.py` - Module for integrating with media generation AIs.
- `server/models.py` - Database models for users, PCs, etc.
- `server/auth.py` - Authentication system.

### Notes

- Unit tests should typically be placed alongside the code files they are testing (e.g., `MyComponent.tsx` and `MyComponent.test.tsx` in the same directory).
- Use `npx jest [optional/path/to/test/file]` to run tests. Running without a path executes all tests found by the Jest configuration.
- For Python, use a testing framework like `pytest`. Tests can be placed in a `tests/` directory or alongside modules.

## Tasks

- [x] 1.0 Setup Project Structure and Core Backend Systems
  - [x] 1.1 Initialize Python backend project (e.g., Flask, FastAPI).
  - [x] 1.2 Set up database schema (user accounts, PC data).
  - [x] 1.3 Implement basic authentication system (user login/signup).
  - [x] 1.4 Initialize React frontend project.
  - [x] 1.5 Define API contracts between frontend and backend.
- [x] 2.0 Implement Player Character (PC) Management
  - [x] 2.1 Backend: Create API endpoints for PC creation (stats, personality, skills, inventory).
  - [x] 2.2 Backend: Create API endpoints for loading existing PCs.
  - [x] 2.3 Backend: Create API endpoints for updating PC character sheets (rewards, progression).
  - [x] 2.4 Backend: Implement logic for PC data persistence in the database.
  - [x] 2.5 Frontend: Develop UI for character creation form.
  - [x] 2.6 Frontend: Develop UI for displaying character sheets.
  - [x] 2.7 Frontend: Develop UI for selecting/loading existing PCs.
- [x] 3.0 Develop Core Adventure Loop and AI GM Integration
  - [x] 3.1 Backend: Design and implement Adventure Coordination Module.
    - [x] 3.1.1 Develop logic to collect PC information and player preferences.
    - [x] 3.1.2 Develop prompt engineering strategies for dynamic adventure generation (story, goal, 1-3 encounters).
  - [x] 3.2 Backend: Develop GM AI Module.
    - [x] 3.2.1 Integrate with chosen AI model for narrative and dialogue generation.
    - [x] 3.2.2 Implement logic for managing game state and encounter progression.
    - [x] 3.2.3 Implement dice roll/skill check mechanism (simulating rolls, applying modifiers based on PC stats/skills).
    - [x] 3.2.4 Implement logic for determining action outcomes based on rolls and PC capabilities.
    - [x] 3.2.5 Develop capabilities for the GM to voice NPCs distinctly.
  - [x] 3.3 Backend: Design and implement reward system logic.
  - [x] 3.4 Backend: API endpoint for initiating adventure generation based on PC and preferences.
  - [x] 3.5 Backend: API endpoints for player actions and GM responses during an adventure.
- [x] 4.0 Build Frontend User Interface (React)
  - [x] 4.1 Develop Home Screen UI.
    - [x] 4.1.1 Frontend: Integrate PC management features (create, view, select).
    - [x] 4.1.2 Implement adventure initiation button/flow.
  - [x] 4.2 Develop Adventure Interface UI.
    - [x] 4.2.1 Implement display area for AI-generated encounter imagery.
    - [x] 4.2.2 Implement "Begin Adventure" call to action.
    - [x] 4.2.3 (Optional) Implement display for audio transcript.
    - [x] 4.2.4 (Optional, but recommended) Implement visual display for dice roll results and implications.
    - [x] 4.2.5 Implement UI for applying rewards/changes to PC post-adventure.
    - [x] 4.3 Connect frontend components to backend API endpoints for PC management and adventure gameplay.
- [x] 5.0 Implement Audio Interaction and Media Generation
  - [x] 5.1 Backend: Integrate audio input processing (Speech-to-Text).
  - [x] 5.2 Backend: Integrate voice output synthesis (Text-to-Speech for GM and NPCs).
  - [x] 5.3 Backend: Develop Media Generation AIs integration.
    - [x] 5.3.1 Integrate AI for generating static imagery for encounters.
    - [x] 5.3.2 Integrate AI for generating sound effects.
    - [x] 5.3.3 Integrate AI for generating background music.
  - [x] 5.4 Frontend: Implement microphone access and voice input streaming to backend.
  - [x] 5.5 Frontend: Implement audio playback for GM's synthesized speech and media. 