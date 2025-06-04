import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../hooks/useAuth';
import type { PlayerCharacterRead } from '../../types/api';
import axios from 'axios';

interface SearchFilters {
  search: string;
  level_min: number | null;
  level_max: number | null;
  is_template: boolean | null;
  include_public: boolean;
}

interface CharacterManagerProps {
  onCharacterSelect?: (character: PlayerCharacterRead) => void;
  onCharacterCreate?: () => void;
  mode?: 'selection' | 'management';
}

export const CharacterManager: React.FC<CharacterManagerProps> = ({
  onCharacterSelect,
  onCharacterCreate,
  mode = 'management'
}) => {
  const { accessToken, user } = useAuth();
  const [characters, setCharacters] = useState<PlayerCharacterRead[]>([]);
  const [filteredCharacters, setFilteredCharacters] = useState<PlayerCharacterRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'my-characters' | 'templates' | 'public'>('my-characters');
  
  const [filters, setFilters] = useState<SearchFilters>({
    search: '',
    level_min: null,
    level_max: null,
    is_template: null,
    include_public: false
  });

  const [sortBy, setSortBy] = useState<'name' | 'level' | 'created_at'>('name');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  // Load characters based on current filters and tab
  const loadCharacters = useCallback(async () => {
    if (!accessToken) return;

    setLoading(true);
    setError(null);

    try {
      let endpoint = '/api/pcs/';
      let params: Record<string, string | number | boolean | undefined> = {};

      switch (activeTab) {
        case 'my-characters':
          endpoint = '/api/pcs/';
          params = {
            search: filters.search || undefined,
            level_min: filters.level_min || undefined,
            level_max: filters.level_max || undefined,
            is_template: false
          };
          break;
        case 'templates':
          endpoint = '/api/pcs/';
          params = {
            search: filters.search || undefined,
            level_min: filters.level_min || undefined,
            level_max: filters.level_max || undefined,
            is_template: true
          };
          break;
        case 'public':
          endpoint = '/api/pcs/search/public';
          params = {
            search: filters.search || undefined,
            level_min: filters.level_min || undefined,
            level_max: filters.level_max || undefined,
            limit: 50,
            offset: 0
          };
          break;
      }

      const response = await axios.get<PlayerCharacterRead[]>(endpoint, {
        headers: { Authorization: `Bearer ${accessToken}` },
        params
      });

      setCharacters(response.data);
      setFilteredCharacters(response.data);
    } catch (err) {
      console.error('Failed to load characters:', err);
      setError('Failed to load characters. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [accessToken, activeTab, filters]);

  // Load characters when component mounts or filters change
  useEffect(() => {
    loadCharacters();
  }, [loadCharacters]);

  // Apply client-side sorting (since backend doesn't handle all sorting options)
  useEffect(() => {
    const sorted = [...characters].sort((a, b) => {
      let comparison = 0;
      
      switch (sortBy) {
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
        case 'level':
          comparison = (a.character_level || 1) - (b.character_level || 1);
          break;
        case 'created_at':
          // Use created_at if available, otherwise fallback to ID
          if (a.created_at && b.created_at) {
            comparison = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
          } else {
            comparison = a.id - b.id;
          }
          break;
      }
      
      return sortDirection === 'desc' ? -comparison : comparison;
    });
    
    setFilteredCharacters(sorted);
  }, [characters, sortBy, sortDirection]);

  const handleFilterChange = (key: keyof SearchFilters, value: string | number | boolean | null) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const clearFilters = () => {
    setFilters({
      search: '',
      level_min: null,
      level_max: null,
      is_template: null,
      include_public: false
    });
  };

  const renderCharacterCard = (character: PlayerCharacterRead) => (
    <div 
      key={character.id} 
      style={styles.characterCard}
      className="character-card"
      onClick={() => onCharacterSelect?.(character)}
    >
      <div style={styles.characterHeader}>
        <h3 style={styles.characterName}>{character.name}</h3>
        <div style={styles.characterBadges}>
          {character.user_id !== user?.id && (
            <span style={styles.badge}>Public</span>
          )}
          {character.is_template && (
            <span style={styles.badge}>Template</span>
          )}
        </div>
      </div>
      
      <div style={styles.characterStats}>
        <div style={styles.statItem}>
          <span>STR: {character.strength || 10}</span>
          <span>DEX: {character.dexterity || 10}</span>
        </div>
        <div style={styles.statItem}>
          <span>INT: {character.intelligence || 10}</span>
          <span>CHA: {character.charisma || 10}</span>
        </div>
        {character.character_level && (
          <div style={styles.statItem}>
            <span>Level: {character.character_level}</span>
          </div>
        )}
      </div>
      
      {character.personality_traits && (
        <div style={styles.personalityTraits}>
          <strong>Traits:</strong> {character.personality_traits.slice(0, 100)}
          {character.personality_traits.length > 100 && '...'}
        </div>
      )}
      
      <div style={styles.characterActions}>
        {mode === 'selection' ? (
          <button 
            style={styles.selectButton}
            className="select-button"
            onClick={(e) => {
              e.stopPropagation();
              onCharacterSelect?.(character);
            }}
          >
            Select Character
          </button>
        ) : (
          <div style={styles.actionButtons}>
            <button style={styles.actionButton} className="action-button">
              Edit
            </button>
            <button style={styles.actionButton} className="action-button">
              Copy
            </button>
            <button style={styles.actionButton} className="action-button">
              Share
            </button>
          </div>
        )}
      </div>
    </div>
  );

  const renderFilters = () => (
    <div style={styles.filtersContainer}>
      <div style={styles.filterRow}>
        <input
          type="text"
          placeholder="Search characters..."
          value={filters.search}
          onChange={(e) => handleFilterChange('search', e.target.value)}
          style={styles.searchInput}
          className="search-input"
        />
        
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as 'name' | 'level' | 'created_at')}
          style={styles.sortSelect}
          className="sort-select"
        >
          <option value="name">Sort by Name</option>
          <option value="level">Sort by Level</option>
          <option value="created_at">Sort by Date</option>
        </select>
        
        <button
          onClick={() => setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')}
          style={styles.sortDirectionButton}
          className="sort-direction-button"
          title={`Sort ${sortDirection === 'asc' ? 'Descending' : 'Ascending'}`}
        >
          {sortDirection === 'asc' ? '↑' : '↓'}
        </button>
      </div>
      
      <div style={styles.filterRow}>
        <div style={styles.levelFilters}>
          <input
            type="number"
            placeholder="Min Level"
            value={filters.level_min || ''}
            onChange={(e) => handleFilterChange('level_min', e.target.value ? parseInt(e.target.value) : null)}
            style={styles.levelInput}
            min="1"
            max="20"
          />
          <input
            type="number"
            placeholder="Max Level"
            value={filters.level_max || ''}
            onChange={(e) => handleFilterChange('level_max', e.target.value ? parseInt(e.target.value) : null)}
            style={styles.levelInput}
            min="1"
            max="20"
          />
        </div>
        
        <button
          onClick={clearFilters}
          style={styles.clearFiltersButton}
          className="clear-filters-button"
        >
          Clear Filters
        </button>
      </div>
    </div>
  );

  const renderTabs = () => (
    <div style={styles.tabContainer}>
      <button
        onClick={() => setActiveTab('my-characters')}
        style={{
          ...styles.tab,
          ...(activeTab === 'my-characters' ? styles.activeTab : {})
        }}
        className="tab"
      >
        My Characters ({characters.filter(c => c.user_id === user?.id && !c.is_template).length})
      </button>
      <button
        onClick={() => setActiveTab('templates')}
        style={{
          ...styles.tab,
          ...(activeTab === 'templates' ? styles.activeTab : {})
        }}
        className="tab"
      >
        Templates ({characters.filter(c => c.is_template).length})
      </button>
      <button
        onClick={() => setActiveTab('public')}
        style={{
          ...styles.tab,
          ...(activeTab === 'public' ? styles.activeTab : {})
        }}
        className="tab"
      >
        Public Characters
      </button>
    </div>
  );

  if (loading) {
    return (
      <div style={styles.loadingContainer}>
        <div style={styles.spinner}></div>
        <p>Loading characters...</p>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <style>{`
        .character-card:hover {
          transform: translateY(-2px);
          box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
        }
        
        .search-input:focus, .sort-select:focus, .level-input:focus {
          outline: none;
          border-color: #667eea;
          box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        .select-button:hover, .action-button:hover {
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
        }
        
        .tab:hover {
          background-color: #f8fafc;
        }
        
        .clear-filters-button:hover, .sort-direction-button:hover {
          background-color: #e2e8f0;
        }
        
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
      
      <div style={styles.header}>
        <h2 style={styles.title}>Character Manager</h2>
        {onCharacterCreate && (
          <button
            onClick={onCharacterCreate}
            style={styles.createButton}
            className="create-button"
          >
            + Create New Character
          </button>
        )}
      </div>

      {renderTabs()}
      {renderFilters()}

      {error && (
        <div style={styles.errorContainer}>
          <p style={styles.errorText}>{error}</p>
          <button onClick={loadCharacters} style={styles.retryButton}>
            Retry
          </button>
        </div>
      )}

      <div style={styles.charactersGrid}>
        {filteredCharacters.length === 0 ? (
          <div style={styles.emptyState}>
            <p>No characters found matching your criteria.</p>
            {activeTab === 'my-characters' && onCharacterCreate && (
              <button
                onClick={onCharacterCreate}
                style={styles.createFirstButton}
                className="create-first-button"
              >
                Create Your First Character
              </button>
            )}
          </div>
        ) : (
          filteredCharacters.map(renderCharacterCard)
        )}
      </div>
    </div>
  );
};

const styles = {
  container: {
    padding: '20px',
    maxWidth: '1200px',
    margin: '0 auto',
  } as React.CSSProperties,
  
  loadingContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '60px 20px',
    color: '#666',
  } as React.CSSProperties,
  
  spinner: {
    width: '32px',
    height: '32px',
    border: '3px solid #f3f3f3',
    borderTop: '3px solid #667eea',
    borderRadius: '50%',
    animation: 'spin 1s linear infinite',
    marginBottom: '16px',
  } as React.CSSProperties,
  
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '24px',
  } as React.CSSProperties,
  
  title: {
    margin: 0,
    color: '#333',
    fontSize: '28px',
    fontWeight: '600',
  } as React.CSSProperties,
  
  createButton: {
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: 'white',
    border: 'none',
    padding: '12px 24px',
    borderRadius: '8px',
    fontSize: '16px',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  } as React.CSSProperties,
  
  tabContainer: {
    display: 'flex',
    borderBottom: '2px solid #e2e8f0',
    marginBottom: '24px',
  } as React.CSSProperties,
  
  tab: {
    background: 'none',
    border: 'none',
    padding: '12px 24px',
    fontSize: '16px',
    cursor: 'pointer',
    color: '#666',
    borderBottom: '3px solid transparent',
    transition: 'all 0.2s ease',
  } as React.CSSProperties,
  
  activeTab: {
    color: '#667eea',
    borderBottomColor: '#667eea',
    fontWeight: '600',
  } as React.CSSProperties,
  
  filtersContainer: {
    background: '#f8fafc',
    padding: '20px',
    borderRadius: '8px',
    marginBottom: '24px',
  } as React.CSSProperties,
  
  filterRow: {
    display: 'flex',
    gap: '16px',
    alignItems: 'center',
    marginBottom: '16px',
    flexWrap: 'wrap',
  } as React.CSSProperties,
  
  searchInput: {
    flex: 1,
    minWidth: '300px',
    padding: '10px 16px',
    border: '2px solid #e1e5e9',
    borderRadius: '6px',
    fontSize: '16px',
    transition: 'border-color 0.2s ease',
  } as React.CSSProperties,
  
  sortSelect: {
    padding: '10px 16px',
    border: '2px solid #e1e5e9',
    borderRadius: '6px',
    fontSize: '16px',
    cursor: 'pointer',
    transition: 'border-color 0.2s ease',
  } as React.CSSProperties,
  
  sortDirectionButton: {
    padding: '10px 16px',
    border: '2px solid #e1e5e9',
    borderRadius: '6px',
    background: 'white',
    fontSize: '18px',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    width: '44px',
    height: '44px',
  } as React.CSSProperties,
  
  levelFilters: {
    display: 'flex',
    gap: '12px',
    alignItems: 'center',
  } as React.CSSProperties,
  
  levelInput: {
    width: '120px',
    padding: '8px 12px',
    border: '2px solid #e1e5e9',
    borderRadius: '6px',
    fontSize: '14px',
    transition: 'border-color 0.2s ease',
  } as React.CSSProperties,
  
  clearFiltersButton: {
    padding: '8px 16px',
    border: '1px solid #d1d5db',
    borderRadius: '6px',
    background: 'white',
    color: '#666',
    fontSize: '14px',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  } as React.CSSProperties,
  
  charactersGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
    gap: '20px',
  } as React.CSSProperties,
  
  characterCard: {
    background: 'white',
    border: '1px solid #e2e8f0',
    borderRadius: '12px',
    padding: '20px',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    boxShadow: '0 2px 4px rgba(0, 0, 0, 0.05)',
  } as React.CSSProperties,
  
  characterHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '16px',
  } as React.CSSProperties,
  
  characterName: {
    margin: 0,
    fontSize: '18px',
    fontWeight: '600',
    color: '#333',
  } as React.CSSProperties,
  
  characterBadges: {
    display: 'flex',
    gap: '8px',
  } as React.CSSProperties,
  
  badge: {
    background: '#e0e7ff',
    color: '#5b21b6',
    padding: '4px 8px',
    borderRadius: '4px',
    fontSize: '12px',
    fontWeight: '500',
  } as React.CSSProperties,
  
  characterStats: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '12px',
    marginBottom: '16px',
  } as React.CSSProperties,
  
  statItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    fontSize: '14px',
    color: '#666',
  } as React.CSSProperties,
  
  personalityTraits: {
    fontSize: '14px',
    color: '#666',
    marginBottom: '16px',
    lineHeight: '1.4',
  } as React.CSSProperties,
  
  characterActions: {
    borderTop: '1px solid #e2e8f0',
    paddingTop: '16px',
  } as React.CSSProperties,
  
  selectButton: {
    width: '100%',
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: 'white',
    border: 'none',
    padding: '10px 16px',
    borderRadius: '6px',
    fontSize: '14px',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  } as React.CSSProperties,
  
  actionButtons: {
    display: 'flex',
    gap: '8px',
  } as React.CSSProperties,
  
  actionButton: {
    flex: 1,
    background: '#f8fafc',
    border: '1px solid #e2e8f0',
    color: '#667eea',
    padding: '8px 12px',
    borderRadius: '6px',
    fontSize: '14px',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
  } as React.CSSProperties,
  
  emptyState: {
    gridColumn: '1 / -1',
    textAlign: 'center',
    padding: '60px 20px',
    color: '#666',
  } as React.CSSProperties,
  
  createFirstButton: {
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: 'white',
    border: 'none',
    padding: '12px 24px',
    borderRadius: '8px',
    fontSize: '16px',
    fontWeight: '600',
    cursor: 'pointer',
    marginTop: '16px',
    transition: 'all 0.2s ease',
  } as React.CSSProperties,
  
  errorContainer: {
    background: '#fef2f2',
    border: '1px solid #fecaca',
    borderRadius: '8px',
    padding: '16px',
    marginBottom: '24px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  } as React.CSSProperties,
  
  errorText: {
    color: '#dc2626',
    margin: 0,
  } as React.CSSProperties,
  
  retryButton: {
    background: '#dc2626',
    color: 'white',
    border: 'none',
    padding: '8px 16px',
    borderRadius: '6px',
    fontSize: '14px',
    cursor: 'pointer',
  } as React.CSSProperties,
}; 