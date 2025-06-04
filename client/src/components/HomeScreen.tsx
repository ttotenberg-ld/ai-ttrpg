import React, { useState } from 'react';
import axios from 'axios';
import CharacterCreationForm from './CharacterCreationForm';
import CharacterSheet from './CharacterSheet';
import CharacterSelection from './CharacterSelection';
import type { PlayerCharacterRead, StartAdventureResponse, AdventureDefinition, APIError } from '../types/api';

interface HomeScreenProps {
  authToken: string;
  onStartAdventure: (adventureId: string, adventureDefinition: AdventureDefinition, character: PlayerCharacterRead) => void;
}

// DUMMY_TOKEN is removed, will use authToken from props
// const DUMMY_TOKEN = "...";

const styles: { [key: string]: React.CSSProperties } = {
    adventureSection: { marginTop: '20px', padding: '10px', border: '1px solid #007bff', borderRadius: '8px' },
    button: { padding: '10px 15px', backgroundColor: '#007bff', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' },
    error: { color: 'red' },
    adventureDetails: { marginTop: '10px', padding: '10px', backgroundColor: '#f0f8ff', border: '1px dashed #ccc'}
  };

const HomeScreen: React.FC<HomeScreenProps> = ({ authToken, onStartAdventure }) => {
  const [selectedCharacter, setSelectedCharacter] = useState<PlayerCharacterRead | null>(null);
  // authTokenForSelection now uses the authToken prop for re-triggering CharacterSelection
  const [authTokenForSelection, setAuthTokenForSelection] = useState<string>(authToken); 
  
  const [generatedAdventureDefinition, setGeneratedAdventureDefinition] = useState<AdventureDefinition | null>(null);
  const [generatedAdventureId, setGeneratedAdventureId] = useState<string | null>(null);
  const [adventureLoading, setAdventureLoading] = useState<boolean>(false);
  const [adventureError, setAdventureError] = useState<string | null>(null);

  // Effect to update authTokenForSelection if the authToken prop changes (e.g., after login)
  React.useEffect(() => {
    setAuthTokenForSelection(authToken);
  }, [authToken]);

  const handleCharacterSelection = (character: PlayerCharacterRead | null) => {
    setSelectedCharacter(character);
    setGeneratedAdventureDefinition(null);
    setGeneratedAdventureId(null);
    setAdventureError(null);
  };

  const handleCharacterCreated = (character: PlayerCharacterRead) => {
    setAuthTokenForSelection(''); // Clear token momentarily to trigger re-fetch in CharacterSelection
    setTimeout(() => {
      setAuthTokenForSelection(authToken); // Re-assert with the current authToken prop
    }, 0);
    setSelectedCharacter(character);
    setGeneratedAdventureDefinition(null);
    setGeneratedAdventureId(null);
    setAdventureError(null);
  };

  const handleInitiateAdventure = async () => {
    if (!selectedCharacter) {
      setAdventureError("Please select a character first.");
      return;
    }
    setAdventureLoading(true);
    setAdventureError(null);
    setGeneratedAdventureDefinition(null);
    setGeneratedAdventureId(null);

    try {
      const response = await axios.post<StartAdventureResponse>(
        `/api/adventures/generate/${selectedCharacter.id}`,
        null, 
        {
          headers: {
            'Authorization': `Bearer ${authToken}`,
          },
        }
      );
      setGeneratedAdventureDefinition(response.data.adventure_definition);
      setGeneratedAdventureId(response.data.adventure_id);
      // Don't call onStartAdventure here directly yet, let user click "Begin Adventure"
    } catch (err) {
      if (axios.isAxiosError(err) && err.response) {
        const apiError = err.response.data as APIError;
        setAdventureError(typeof apiError.detail === 'string' ? apiError.detail : JSON.stringify(apiError.detail));
      } else {
        setAdventureError('An unexpected error occurred during adventure generation.');
      }
      console.error('Adventure generation error:', err);
    }
    setAdventureLoading(false);
  };

  const handleBeginAdventureClick = () => {
    if (generatedAdventureId && generatedAdventureDefinition && selectedCharacter) {
        onStartAdventure(generatedAdventureId, generatedAdventureDefinition, selectedCharacter);
    }
  };

  return (
    <div>
      <h2>Player Character Management</h2>
      {/* <p><em>Auth Token: {authToken ? "Present" : "Missing"}</em></p> */}
      <hr />

      <CharacterSelection 
        onCharacterSelect={handleCharacterSelection} 
        dummyAuthToken={authTokenForSelection} // CharacterSelection still uses dummyAuthToken prop name
      />
      <hr />

      {selectedCharacter && (
        <CharacterSheet character={selectedCharacter} />
      )}
      {!selectedCharacter && (
         <p>No character selected. Select one from the list above or create a new one below.</p>
      )}
      <hr />

      <CharacterCreationForm 
        dummyAuthToken={authToken} // Pass the authToken prop
        onCharacterCreated={handleCharacterCreated} 
      />
      
      {selectedCharacter && (
        <div style={styles.adventureSection}>
          <h3>Start Adventure for {selectedCharacter.name}</h3>
          <button onClick={handleInitiateAdventure} disabled={adventureLoading} style={styles.button}>
            {adventureLoading ? 'Generating Adventure...' : `Generate Adventure`}
          </button>
          {adventureError && <p style={styles.error}>Error: {adventureError}</p>}
          {generatedAdventureDefinition && generatedAdventureId && (
            <div style={styles.adventureDetails}>
              <h4>Adventure Generated! (ID: {generatedAdventureId})</h4>
              <p><strong>Title:</strong> {generatedAdventureDefinition.title}</p>
              <p><strong>Goal:</strong> {generatedAdventureDefinition.overall_goal}</p>
              <button onClick={handleBeginAdventureClick} style={{...styles.button, marginTop: '10px'}}>
                Begin Adventure
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default HomeScreen; 