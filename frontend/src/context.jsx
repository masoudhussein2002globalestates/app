import {createContext, useContext, useEffect, useState, useCallback} from 'react';
import {api, errorText} from './lib/api';
import {toast} from 'sonner';
const Context = createContext(null);
export const useApp = () => useContext(Context);
export const AppProvider = ({children}) => {
  const [user, setUser] = useState(null), [loading, setLoading] = useState(true), [favorites, setFavorites] = useState([]), [meta, setMeta] = useState({countries: [], stripe_configured: false, rental_platform_fee: 0});
  const refreshFavorites = useCallback(async () => {try {setFavorites((await api.get('/favorites')).data);} catch {setFavorites([]);}}, []);
  useEffect(() => {
    api.get('/meta').then(r => setMeta(r.data)).catch(() => toast.error('Unable to load marketplace settings. Please refresh.'));
    if (window.location.hash.includes('session_id=')) {setLoading(false); return;}
    api.get('/auth/me').then(r => setUser(r.data)).catch(() => setUser(null)).finally(() => setLoading(false));
  }, []);
  useEffect(() => {if(user) refreshFavorites(); else setFavorites([]);}, [user, refreshFavorites]);
  const toggleFavorite = async (id) => {
    if (!user) return false;
    try {const saved = favorites.some(p => p.id === id); await api[saved ? 'delete' : 'put'](`/favorites/${id}`); await refreshFavorites(); toast.success(saved ? 'Removed from saved places' : 'Added to your saved places'); return true;} catch(e) {toast.error(errorText(e)); return true;}
  };
  const logout = async () => {try {await api.post('/auth/logout'); setUser(null); toast.success('Signed out');} catch(e) {toast.error(errorText(e));}};
  return <Context.Provider value={{user, setUser, loading, favorites, toggleFavorite, refreshFavorites, meta, logout}}>{children}</Context.Provider>;
};