# AI Tabletop RPG

An interactive storytelling game powered by AI, where a Game Master (GM) AI dynamically generates adventures, narrates outcomes, and manages game state based on player choices.

## Project Overview

This project combines a Python (FastAPI) backend with a React frontend to create an immersive AI-driven tabletop RPG experience. Players can create characters, embark on adventures, and interact with the game world through text or voice commands. The AI GM handles narrative generation, NPC interactions, skill checks, and media generation (images, sound effects, music) to enhance the storytelling.

## Features

*   **Dynamic Adventure Generation:** AI crafts unique stories, goals, and encounters.
*   **Player Character Management:** Create, load, and update player characters.
*   **AI Game Master:** Handles narration, NPC dialogue, and game state progression.
*   **Skill Checks & Action Outcomes:** AI determines the results of player actions based on dice rolls and character abilities.
*   **Audio Interaction:** 
    *   Speech-to-Text for player input.
    *   Text-to-Speech for GM and NPC voices.
*   **Generated Media:** AI-generated imagery for encounters, sound effects, and background music.

## Project Structure

```
.ai-ttrpg/
├── client/         # React Frontend
│   ├── public/
│   └── src/
│       ├── components/
│       ├── services/
│       └── ...
├── server/         # Python FastAPI Backend
│   ├── generated_audio_files/ # Stores TTS audio (mounted at /audio_narration)
│   ├── generated_media/       # Stores images, sfx, music (mounted at /generated_images, etc.)
│   ├── temp_audio_files/    # Temporary storage for uploaded STT audio
│   ├── .env.example         # Example environment variables
│   ├── auth.py
│   ├── database.py
│   ├── gm_ai.py
│   ├── main.py
│   ├── media_generation.py
│   ├── models.py
│   └── requirements.txt
├── tasks/            # Task lists and PRDs
├── .gitignore
└── README.md
```

## Getting Started

### Prerequisites

*   Python 3.8+
*   Node.js 16+ and npm/yarn
*   An OpenAI API Key (for AI features)
*   (Optional) `pyttsx3` dependencies for Text-to-Speech (e.g., `espeak` on Linux, SAPI5 on Windows, NSSpeechSynthesizer on macOS).

### Backend Setup (server/)

1.  **Navigate to the server directory:**
    ```bash
    cd server
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    ```

3.  **Activate the virtual environment:**
    *   On macOS/Linux:
        ```bash
        source venv/bin/activate
        ```
    *   On Windows:
        ```bash
        .\venv\Scripts\activate
        ```

4.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Set up environment variables:**
    *   Copy `.env.example` to `.env` (if an example file exists, or create `.env` manually).
    *   Add your OpenAI API key to the `.env` file:
        ```env
        OPENAI_API_KEY="your_openai_api_key_here"
        # Other potential variables like DATABASE_URL if you switch from SQLite
        ```

6.  **Run the backend server:**
    ```bash
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
    ```
    The backend should now be running on `http://localhost:8000`.

### Frontend Setup (client/)

1.  **Navigate to the client directory:**
    ```bash
    cd ../client 
    # Or from root: cd client
    ```

2.  **Install Node.js dependencies:**
    ```bash
    npm install
    # or if you use yarn: yarn install
    ```

3.  **Set up environment variables (if any):**
    *   The frontend might use a `.env` file for settings like the API base URL (e.g., `REACT_APP_API_URL=http://localhost:8000`). Check your frontend code for specific requirements.
    *   If `AIService.ts` (or similar) uses `process.env.REACT_APP_API_URL`, create a `.env` file in the `client/` directory:
        ```env
        REACT_APP_API_URL=http://localhost:8000
        ```

4.  **Run the frontend development server:**
    ```bash
    npm start
    # or if you use yarn: yarn start
    ```
    The React app should now be running, typically on `http://localhost:3000`.

## Usage

1.  Ensure both backend and frontend servers are running.
2.  Open your browser and navigate to the frontend URL (usually `http://localhost:3000`).
3.  Create a user account, then create a player character.
4.  Start a new adventure from the home screen.
5.  Interact with the game using the provided interface (text input or voice recording).

## Further Development Ideas

*   Implement actual AI models for sound effect and background music generation.
*   Expand character creation options and progression systems.
*   Add more complex game mechanics (e.g., status effects, tactical combat).
*   Improve UI/UX for adventure display and interaction.
*   Add multiplayer capabilities.
*   Implement persistent storage for adventure state and history. 