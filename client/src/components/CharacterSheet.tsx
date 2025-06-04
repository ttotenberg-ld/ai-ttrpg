import React from 'react';
import type { PlayerCharacterRead } from '../types/api';

interface CharacterSheetProps {
  character: PlayerCharacterRead;
}

const styles: { [key: string]: React.CSSProperties } = {
  sheet: {
    border: '1px solid #eee',
    padding: '15px',
    margin: '15px',
    borderRadius: '8px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
    maxWidth: '500px',
  },
  title: {
    borderBottom: '2px solid #007bff',
    paddingBottom: '5px',
    marginBottom: '10px',
    color: '#007bff',
  },
  section: {
    marginBottom: '10px',
  },
  label: {
    fontWeight: 'bold',
  },
  statBlock: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))',
    gap: '10px',
    marginBottom: '10px',
  },
  statItem: {
    padding: '5px',
    border: '1px solid #ddd',
    borderRadius: '4px',
    backgroundColor: '#f9f9f9',
  }
};

const CharacterSheet: React.FC<CharacterSheetProps> = ({ character }) => {
  return (
    <div style={styles.sheet}>
      <h2 style={styles.title}>{character.name} (ID: {character.id})</h2>

      <div style={styles.section}>
        <h3 style={styles.label}>Stats:</h3>
        <div style={styles.statBlock}>
          <div style={styles.statItem}>Strength: {character.strength ?? 'N/A'}</div>
          <div style={styles.statItem}>Dexterity: {character.dexterity ?? 'N/A'}</div>
          <div style={styles.statItem}>Intelligence: {character.intelligence ?? 'N/A'}</div>
          <div style={styles.statItem}>Charisma: {character.charisma ?? 'N/A'}</div>
        </div>
      </div>

      {character.personality_traits && (
        <div style={styles.section}>
          <p><span style={styles.label}>Personality Traits:</span> {character.personality_traits}</p>
        </div>
      )}

      {character.skills && (
        <div style={styles.section}>
          <p><span style={styles.label}>Skills:</span> {character.skills}</p>
        </div>
      )}

      {character.inventory && (
        <div style={styles.section}>
          <p><span style={styles.label}>Inventory:</span> {character.inventory}</p>
        </div>
      )}
    </div>
  );
};

export default CharacterSheet; 