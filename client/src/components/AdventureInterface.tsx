import React, { useEffect, useState } from 'react';
import type { AdventureDefinition, AdventureEncounter, PlayerActionRequest, ActionOutcomeResponse, APIError } from '../types/api';
import axios from 'axios';

interface AdventureInterfaceProps {
  adventureId: string;
  adventureDefinition: AdventureDefinition;
  initialEncounter: AdventureEncounter; // The first encounter to display
  authToken: string; // For API calls
  onAdventureEnd: () => void; // Callback when adventure is considered over
}

const styles: { [key: string]: React.CSSProperties } = {
  container: { margin: '20px', padding: '20px', border: '1px solid #007bff', borderRadius: '8px' },
  header: { borderBottom: '2px solid #007bff', paddingBottom: '10px', marginBottom: '15px' },
  imagePlaceholder: {
    width: '100%',
    height: '300px',
    backgroundColor: '#e9ecef',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    textAlign: 'center',
    borderRadius: '4px',
    marginBottom: '15px',
    border: '1px dashed #ced4da',
    color: '#6c757d',
  },
  encounterDetails: { marginBottom: '15px' },
  narrationArea: { 
    minHeight: '100px', 
    maxHeight: '300px',
    overflowY: 'auto',
    border: '1px solid #eee', 
    padding: '10px', 
    marginBottom: '15px', 
    backgroundColor: '#fdfdfd', 
    borderRadius: '4px',
    whiteSpace: 'pre-wrap'
  },
  actionInputArea: { display: 'flex', gap: '10px', marginBottom: '15px' },
  input: { flexGrow: 1, padding: '10px', border: '1px solid #ccc', borderRadius: '4px' },
  button: { padding: '10px 15px', backgroundColor: '#28a745', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' },
  error: { color: 'red' },
  skillCheckInfo: { fontSize: '0.9em', color: '#444', marginTop: '5px', fontStyle: 'italic' }
};

const AdventureInterface: React.FC<AdventureInterfaceProps> = ({
  adventureId,
  adventureDefinition,
  initialEncounter,
  authToken,
  onAdventureEnd
}) => {
  const [currentEncounterIndex, setCurrentEncounterIndex] = useState<number>(() => adventureDefinition.encounters.findIndex(enc => enc === initialEncounter) || 0);
  const [currentEncounter, setCurrentEncounter] = useState<AdventureEncounter>(initialEncounter);
  const [narration, setNarration] = useState<string>(initialEncounter.description); // Initial narration is the encounter description
  const [playerAction, setPlayerAction] = useState<string>('');
  const [loadingAction, setLoadingAction] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [skillCheckResultText, setSkillCheckResultText] = useState<string | null>(null);
  const [skillCheckSuccess, setSkillCheckSuccess] = useState<boolean | null>(null);

  // TODO: Logic to fetch image based on encounter details (task 5.3.1)
  const [encounterImageUrl, setEncounterImageUrl] = useState<string | null>(null); 

  // Reset narration when encounter changes (if we implement encounter advancement here)
  useEffect(() => {
    // Update currentEncounter based on currentEncounterIndex
    const newEncounter = adventureDefinition.encounters[currentEncounterIndex];
    if (newEncounter) {
        setCurrentEncounter(newEncounter);
        setNarration(newEncounter.description); // Reset narration to the new encounter's description
        setEncounterImageUrl(null); // Reset image
        // TODO: Fetch image for newEncounter
    }
  }, [currentEncounterIndex, adventureDefinition.encounters]);

  const handlePlayerActionSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!playerAction.trim()) return;

    setLoadingAction(true);
    setActionError(null);
    setSkillCheckResultText(null);
    setSkillCheckSuccess(null);

    const actionRequest: PlayerActionRequest = { action_text: playerAction };
    // TODO: Add logic for suggesting stat_to_check or suggested_dc based on player input parsing or UI

    try {
      const response = await axios.post<ActionOutcomeResponse>(
        `/api/adventures/${adventureId}/action`,
        actionRequest,
        {
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json'
          }
        }
      );
      setNarration(prev => prev + "\n\n> " + playerAction + "\n\n" + response.data.narration);
      if (response.data.skill_check_result_desc) {
        setSkillCheckResultText(response.data.skill_check_result_desc);
      }
      if (response.data.skill_check_success !== null && response.data.skill_check_success !== undefined) {
        setSkillCheckSuccess(response.data.skill_check_success);
      }
      setPlayerAction(''); // Clear input field

      // TODO: Add logic here to check if the adventure/encounter has advanced or ended
      // based on response.data or by calling another endpoint.
      // Example: if (response.data.encounterAdvanced) { setCurrentEncounter(response.data.newEncounterDetails); }
      // If adventureDefinition.conclusion is part of narration, call onAdventureEnd()
      if (response.data.narration.includes(adventureDefinition.conclusion)) {
        // This is a very basic check. A more robust system is needed.
        // setTimeout(onAdventureEnd, 3000); // Delay to let player read final narration
        console.log("Adventure conclusion might have been reached.")
      }

    } catch (err) {
      if (axios.isAxiosError(err) && err.response) {
        const apiError = err.response.data as APIError;
        setActionError(typeof apiError.detail === 'string' ? apiError.detail : JSON.stringify(apiError.detail));
      } else {
        setActionError('An unexpected error occurred while performing the action.');
      }
      console.error('Player action error:', err);
    }
    setLoadingAction(false);
  };

  const handleNextEncounter = () => {
    if (currentEncounterIndex < adventureDefinition.encounters.length - 1) {
      setCurrentEncounterIndex(prevIndex => prevIndex + 1);
    } else {
      // Already at the last encounter, or no more encounters.
      // Potentially show adventure conclusion here or trigger onAdventureEnd
      setNarration(prev => prev + "\n\nThere are no more direct paths from here. The adventure might be nearing its end or a different approach is needed.");
      if(adventureDefinition.conclusion && !narration.includes(adventureDefinition.conclusion)){
        setNarration(prev => prev + "\n\nFINAL CONCLUSION:\n" + adventureDefinition.conclusion);
      }
      // Consider calling onAdventureEnd() here if appropriate
    }
  };

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h2>{adventureDefinition.title}</h2>
        <p><strong>Goal:</strong> {adventureDefinition.overall_goal}</p>
      </header>

      <div style={styles.imagePlaceholder}>
        {encounterImageUrl ? (
          <img src={encounterImageUrl} alt={currentEncounter.description.substring(0,50)} style={{maxWidth: '100%', maxHeight: '100%', borderRadius: '4px'}}/>
        ) : (
          <p>AI-Generated Encounter Image Area<br/>(Imagery for "{currentEncounter.challenge_objective.substring(0, 50)}..." would appear here)</p>
        )}
      </div>

      <div style={styles.encounterDetails}>
        <h3>Current Encounter ({currentEncounterIndex + 1} / {adventureDefinition.encounters.length}): {currentEncounter.challenge_objective}</h3>
      </div>
      
      <div style={styles.narrationArea}>
        {narration}
        {skillCheckResultText && (
          <div style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px dashed #ccc' }}>
            {skillCheckSuccess === true && <p style={{color: 'green', fontWeight: 'bold', margin: '0 0 5px 0'}}>SUCCESS!</p>}
            {skillCheckSuccess === false && <p style={{color: 'red', fontWeight: 'bold', margin: '0 0 5px 0'}}>FAILURE!</p>}
            <p style={styles.skillCheckInfo}><em>{skillCheckResultText}</em></p>
          </div>
        )}
      </div>

      <form onSubmit={handlePlayerActionSubmit}>
        <div style={styles.actionInputArea}>
          <input 
            type="text" 
            value={playerAction} 
            onChange={(e) => setPlayerAction(e.target.value)} 
            placeholder="What do you do?" 
            style={styles.input}
            disabled={loadingAction}
          />
          <button type="submit" disabled={loadingAction} style={styles.button}>
            {loadingAction ? 'Processing...' : 'Send Action'}
          </button>
        </div>
      </form>
      {actionError && <p style={styles.error}>{actionError}</p>}

      <button onClick={handleNextEncounter} style={{...styles.button, backgroundColor: '#ffc107', color: 'black', marginRight: '10px'}}>
        Next Encounter (Temp)
      </button>
      <button onClick={onAdventureEnd} style={{...styles.button, backgroundColor: '#dc3545'}}>End Adventure Manually</button>

    </div>
  );
};

export default AdventureInterface; 