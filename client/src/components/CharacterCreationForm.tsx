import React, { useState } from 'react';
import axios from 'axios';
import type { PlayerCharacterCreate, PlayerCharacterRead, APIError } from '../types/api';

interface CharacterCreationFormProps {
  // TODO: Remove dummy token once auth is in place
  dummyAuthToken: string;
  onCharacterCreated?: (character: PlayerCharacterRead) => void; // Optional callback
}

// Basic styling - can be expanded or moved to a CSS file
const styles: { [key: string]: React.CSSProperties } = {
  form: { display: 'flex', flexDirection: 'column', gap: '10px', maxWidth: '400px', margin: '20px auto' },
  label: { display: 'flex', flexDirection: 'column', gap: '5px' },
  input: { padding: '8px', border: '1px solid #ccc', borderRadius: '4px' },
  button: { padding: '10px', backgroundColor: '#007bff', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' },
  error: { color: 'red', marginTop: '10px' },
  success: { color: 'green', marginTop: '10px' },
};

const CharacterCreationForm: React.FC<CharacterCreationFormProps> = ({ dummyAuthToken, onCharacterCreated }) => {
  const [formData, setFormData] = useState<PlayerCharacterCreate>({
    name: '',
    strength: 10,
    dexterity: 10,
    intelligence: 10,
    charisma: 10,
    personality_traits: '',
    skills: '',
    inventory: '',
  });
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name === 'strength' || name === 'dexterity' || name === 'intelligence' || name === 'charisma' 
              ? parseInt(value, 10) || 0 
              : value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (!dummyAuthToken) {
      setError("Authentication token is missing. Please log in.");
      return;
    }

    try {
      const response = await axios.post<PlayerCharacterRead>(
        '/api/pcs/', 
        formData,
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${dummyAuthToken}` 
          }
        }
      );
      setSuccessMessage(`Character '${response.data.name}' created successfully! ID: ${response.data.id}`);
      if (onCharacterCreated) {
        onCharacterCreated(response.data);
      }
      // Optionally reset form
      setFormData({
        name: '',
        strength: 10,
        dexterity: 10,
        intelligence: 10,
        charisma: 10,
        personality_traits: '',
        skills: '',
        inventory: '',
      });
    } catch (err) {
      if (axios.isAxiosError(err) && err.response) {
        const apiError = err.response.data as APIError;
        if (typeof apiError.detail === 'string') {
          setError(apiError.detail);
        } else if (Array.isArray(apiError.detail)) {
          setError(apiError.detail.map(d => `${d.msg} (in ${d.type})`).join(', '));
        } else {
          setError('An unexpected error occurred.');
        }
      } else {
        setError('An unexpected error occurred during character creation.');
      }
      console.error('Character creation error:', err);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={styles.form}>
      <h2>Create New Player Character</h2>
      
      <label style={styles.label}>
        Name:
        <input type="text" name="name" value={formData.name} onChange={handleChange} required style={styles.input} />
      </label>

      <label style={styles.label}>
        Strength:
        <input type="number" name="strength" value={formData.strength} onChange={handleChange} style={styles.input} />
      </label>

      <label style={styles.label}>
        Dexterity:
        <input type="number" name="dexterity" value={formData.dexterity} onChange={handleChange} style={styles.input} />
      </label>

      <label style={styles.label}>
        Intelligence:
        <input type="number" name="intelligence" value={formData.intelligence} onChange={handleChange} style={styles.input} />
      </label>

      <label style={styles.label}>
        Charisma:
        <input type="number" name="charisma" value={formData.charisma} onChange={handleChange} style={styles.input} />
      </label>

      <label style={styles.label}>
        Personality Traits (comma-separated):
        <textarea name="personality_traits" value={formData.personality_traits || ''} onChange={handleChange} style={styles.input} />
      </label>

      <label style={styles.label}>
        Skills (comma-separated):
        <textarea name="skills" value={formData.skills || ''} onChange={handleChange} style={styles.input} />
      </label>

      <label style={styles.label}>
        Inventory (comma-separated):
        <textarea name="inventory" value={formData.inventory || ''} onChange={handleChange} style={styles.input} />
      </label>

      <button type="submit" style={styles.button}>Create Character</button>

      {error && <p style={styles.error}>Error: {error}</p>}
      {successMessage && <p style={styles.success}>{successMessage}</p>}
    </form>
  );
};

export default CharacterCreationForm; 