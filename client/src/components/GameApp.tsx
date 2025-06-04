import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import HomeScreen from './HomeScreen';
import AdventureInterface from './AdventureInterface';
import RewardScreen from './RewardScreen';
import type { AdventureDefinition, AdventureEncounter, Reward, PlayerCharacterRead } from '../types/api';
import axios from 'axios';

interface ActiveAdventureState {
  id: string;
  definition: AdventureDefinition;
  initialEncounter: AdventureEncounter;
  character: PlayerCharacterRead;
}

const GameApp: React.FC = () => {
  const { accessToken, logout } = useAuth();
  const [activeAdventure, setActiveAdventure] = useState<ActiveAdventureState | null>(null);
  const [currentReward, setCurrentReward] = useState<Reward | null>(null);
  const [showRewardScreen, setShowRewardScreen] = useState<boolean>(false);
  const [activeCharacterForReward, setActiveCharacterForReward] = useState<PlayerCharacterRead | null>(null);

  const handleStartAdventure = (adventureId: string, adventureDefinition: AdventureDefinition, character: PlayerCharacterRead) => {
    if (adventureDefinition.encounters && adventureDefinition.encounters.length > 0) {
      setActiveAdventure({
        id: adventureId,
        definition: adventureDefinition,
        initialEncounter: adventureDefinition.encounters[0],
        character: character,
      });
      setShowRewardScreen(false);
      setCurrentReward(null);
    } else {
      console.error("Cannot start adventure: No encounters defined or encounters array is empty.");
      alert("Failed to start adventure: Adventure has no encounters!");
    }
  };

  const handleAdventureActuallyComplete = async (adventureId: string) => {
    if (!activeAdventure || !accessToken) return;
    
    try {
      console.log(`Completing adventure ${adventureId} and fetching reward.`);
      const response = await axios.post<Reward>(
        `/api/adventures/${adventureId}/complete`,
        null,
        { 
          headers: { 
            'Authorization': `Bearer ${accessToken}` 
          } 
        }
      );
      setCurrentReward(response.data);
      setActiveCharacterForReward(activeAdventure.character);
      setShowRewardScreen(true);
      setActiveAdventure(null);
    } catch (error) {
      console.error("Failed to fetch reward:", error);
      
      // Check if it's an authentication error
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        console.log("Authentication failed, logging out...");
        await logout();
        return;
      }
      
      alert("Failed to fetch reward. Please try again.");
      setActiveAdventure(null);
    }
  };

  const handleRewardAppliedAndClosed = (updatedCharacter: PlayerCharacterRead) => {
    setShowRewardScreen(false);
    setCurrentReward(null);
    setActiveCharacterForReward(null);
    console.log("Reward applied. Updated character:", updatedCharacter.name);
  };

  const handleRewardScreenCloseOnly = () => {
    setShowRewardScreen(false);
    setCurrentReward(null);
    setActiveCharacterForReward(null);
    console.log("Reward screen closed without applying (or after applying and another close action).");
  };

  // If we don't have an access token, this shouldn't render (ProtectedRoute should handle this)
  if (!accessToken) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '50vh',
        color: '#666'
      }}>
        <p>Authentication required...</p>
      </div>
    );
  }

  return (
    <>
      {activeAdventure && !showRewardScreen ? (
        <AdventureInterface 
          adventureId={activeAdventure.id}
          adventureDefinition={activeAdventure.definition}
          initialEncounter={activeAdventure.initialEncounter}
          authToken={accessToken}
          onAdventureEnd={() => handleAdventureActuallyComplete(activeAdventure.id)}
        />
      ) : showRewardScreen && currentReward && activeCharacterForReward ? (
        <RewardScreen 
          reward={currentReward} 
          character={activeCharacterForReward} 
          authToken={accessToken}
          onRewardApplied={handleRewardAppliedAndClosed}
          onClose={handleRewardScreenCloseOnly}
        />
      ) : (
        <HomeScreen 
          authToken={accessToken} 
          onStartAdventure={handleStartAdventure}
        />
      )}
    </>
  );
};

export default GameApp; 