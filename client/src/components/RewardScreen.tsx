import React, { useState } from 'react';
import axios from 'axios';
import type { Reward, PlayerCharacterRead, PlayerCharacterUpdate, APIError } from '../types/api';
import { RewardType } from '../types/api'; // Import RewardType as a value

interface RewardScreenProps {
  reward: Reward;
  character: PlayerCharacterRead;
  authToken: string;
  onRewardApplied: (updatedCharacter: PlayerCharacterRead) => void; // Callback after successful update
  onClose: () => void; // Callback to close the reward screen
}

const styles: { [key: string]: React.CSSProperties } = {
  overlay: {
    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.7)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 1000,
  },
  modal: {
    backgroundColor: 'white', padding: '20px', borderRadius: '8px',
    minWidth: '300px', maxWidth: '500px', textAlign: 'center',
    boxShadow: '0 4px 15px rgba(0,0,0,0.2)',
  },
  rewardName: { fontSize: '1.5em', color: '#007bff', marginBottom: '10px' },
  rewardDescription: { marginBottom: '20px' },
  buttonContainer: { display: 'flex', justifyContent: 'space-around', marginTop: '20px' },
  button: { padding: '10px 20px', border: 'none', borderRadius: '4px', cursor: 'pointer' },
  applyButton: { backgroundColor: '#28a745', color: 'white' },
  closeButton: { backgroundColor: '#6c757d', color: 'white' },
  error: { color: 'red', marginTop: '10px' },
  success: { color: 'green', marginTop: '10px' },
};

// Define a type for the keys of PlayerCharacterRead/Update that are numeric stats
type NumericStatKey = 'strength' | 'dexterity' | 'intelligence' | 'charisma';

const RewardScreen: React.FC<RewardScreenProps> = ({ reward, character, authToken, onRewardApplied, onClose }) => {
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleApplyReward = async () => {
    setIsLoading(true);
    setError(null);
    setSuccessMessage(null);

    const pcUpdate: PlayerCharacterUpdate = {}; 

    switch (reward.reward_type) {
      case RewardType.EQUIPMENT:
        pcUpdate.inventory = character.inventory 
          ? `${character.inventory}, ${reward.value}` 
          : reward.value || '';
        break;
      case RewardType.NEW_SKILL:
        pcUpdate.skills = character.skills
          ? `${character.skills}, ${reward.name}`
          : reward.name;
        break;
      case RewardType.STAT_UPGRADE:
        if (reward.target_stat && reward.value) {
          const statKey = reward.target_stat;
          // Check if the target_stat is a valid numeric stat key
          if (statKey === 'strength' || statKey === 'dexterity' || statKey === 'intelligence' || statKey === 'charisma') {
            const typedStatKey = statKey as NumericStatKey;
            const currentStatValue = character[typedStatKey]; // Accessing character[typedStatKey] which is number | undefined

            if (typeof currentStatValue === 'number') {
              const changeAmount = parseInt(reward.value, 10);
              if (!isNaN(changeAmount)) {
                pcUpdate[typedStatKey] = currentStatValue + changeAmount;
              } else {
                setError(`Invalid change value for stat upgrade: ${reward.value}`);
                setIsLoading(false); return;
              }
            } else {
              // If currentStatValue is undefined (e.g. character didn't have the stat set, though unlikely for core stats)
              // Or if somehow it was null (though our types say number | undefined)
              setError(`Cannot apply stat upgrade: Character base stat '${typedStatKey}' is ${currentStatValue === undefined ? 'missing' : 'not a number'}.`);
              setIsLoading(false);
              return;
            }
          } else {
            setError(`Invalid target_stat for stat upgrade: ${statKey}`);
            setIsLoading(false);
            return;
          }
        }
        break;
      default:
        setError("Unknown reward type.");
        setIsLoading(false);
        return;
    }

    if (Object.keys(pcUpdate).length === 0 && !error) { // also check !error
        setSuccessMessage("Reward noted, but no direct character sheet update was needed from this reward type.");
        setIsLoading(false);
        return;
    }
    if (error) { // If an error was set in the switch, don't proceed
        setIsLoading(false);
        return;
    }

    try {
      const response = await axios.patch<PlayerCharacterRead>(
        `/api/pcs/${character.id}`,
        pcUpdate,
        {
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json',
          },
        }
      );
      setSuccessMessage("Reward applied successfully!");
      onRewardApplied(response.data);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response) {
        const apiError = err.response.data as APIError;
        setError(typeof apiError.detail === 'string' ? apiError.detail : JSON.stringify(apiError.detail));
      } else {
        setError('An unexpected error occurred while applying the reward.');
      }
      console.error('Reward application error:', err);
    }
    setIsLoading(false);
  };

  return (
    <div style={styles.overlay}>
      <div style={styles.modal}>
        <h2>🎉 Adventure Complete! 🎉</h2>
        <h3>You received a reward:</h3>
        <p style={styles.rewardName}>{reward.name}</p>
        <p style={styles.rewardDescription}>{reward.description}</p>

        {error && <p style={styles.error}>{error}</p>}
        {successMessage && <p style={styles.success}>{successMessage}</p>}

        <div style={styles.buttonContainer}>
          {!successMessage && !error && (
            <button 
              onClick={handleApplyReward} 
              disabled={isLoading} 
              style={{...styles.button, ...styles.applyButton}}
            >
              {isLoading ? 'Applying...' : 'Apply Reward to Character'}
            </button>
          )}
          <button onClick={onClose} style={{...styles.button, ...styles.closeButton}}>
            {successMessage || error ? 'Close' : 'Claim Later / Close'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default RewardScreen; 