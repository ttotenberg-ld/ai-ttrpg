import React, { useEffect, useState } from 'react';
import axios from 'axios';
import type { PlayerCharacterRead, APIError } from '../types/api';

interface CharacterSelectionProps {
  onCharacterSelect: (character: PlayerCharacterRead | null) => void;
  // TODO: Remove dummy token once auth is in place
  dummyAuthToken: string; 
}

const styles: { [key: string]: React.CSSProperties } = {
  container: { margin: '20px', padding: '15px', border: '1px solid #ccc', borderRadius: '8px' },
  list: { listStyle: 'none', padding: '0' },
  listItem: {
    padding: '10px',
    borderBottom: '1px solid #eee',
    cursor: 'pointer',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  listItemHover: { backgroundColor: '#f0f0f0' }, // For hover effect
  button: { 
    padding: '5px 10px', 
    backgroundColor: '#28a745', 
    color: 'white', 
    border: 'none', 
    borderRadius: '4px', 
    cursor: 'pointer' 
  },
  error: { color: 'red' },
};

const CharacterSelection: React.FC<CharacterSelectionProps> = ({ onCharacterSelect, dummyAuthToken }) => {
  const [characters, setCharacters] = useState<PlayerCharacterRead[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<number | null>(null);

  useEffect(() => {
    const fetchCharacters = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await axios.get<PlayerCharacterRead[]>('/api/pcs/', {
          headers: {
            'Authorization': `Bearer ${dummyAuthToken}`,
          },
        });
        setCharacters(response.data);
      } catch (err) {
        if (axios.isAxiosError(err) && err.response) {
          const apiError = err.response.data as APIError;
          setError(apiError.detail as string || 'Failed to fetch characters.');
        } else {
          setError('An unexpected error occurred while fetching characters.');
        }
        console.error('Fetch characters error:', err);
      }
      setLoading(false);
    };

    if (dummyAuthToken) { // Only fetch if token is provided
        fetchCharacters();
    }

  }, [dummyAuthToken]);

  if (loading) return <p>Loading characters...</p>;
  if (error) return <p style={styles.error}>Error: {error}</p>;
  if (!dummyAuthToken) return <p>Please log in to see your characters.</p>; // Basic check

  return (
    <div style={styles.container}>
      <h3>Select a Character:</h3>
      {characters.length === 0 ? (
        <p>No characters found. Create one below!</p>
      ) : (
        <ul style={styles.list}>
          {characters.map(char => (
            <li 
              key={char.id} 
              style={{
                ...styles.listItem, 
                ...(hoveredId === char.id ? styles.listItemHover : {})
              }}
              onMouseEnter={() => setHoveredId(char.id)}
              onMouseLeave={() => setHoveredId(null)}
              onClick={() => onCharacterSelect(char)} // Selects on whole LI click
            >
              {char.name} (ID: {char.id})
              {/* Optional: Button to specifically load/view */}
              {/* <button 
                style={styles.button} 
                onClick={(e) => { 
                  e.stopPropagation(); // Prevent LI click event if button is clicked
                  onCharacterSelect(char); 
                }}
              >
                Load
              </button> */}
            </li>
          ))}
        </ul>
      )}
      <button onClick={() => onCharacterSelect(null)} style={{marginTop: '10px'}}>Clear Selection</button>
    </div>
  );
};

export default CharacterSelection; 