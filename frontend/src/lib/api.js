import axios from 'axios';
export const API_URL = process.env.REACT_APP_BACKEND_URL;
export const api = axios.create({baseURL: `${API_URL}/api`, withCredentials: true, timeout: 30000});
export const errorText = (error) => {
  const detail = error.response?.data?.detail;
  return typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(e => `${e.loc.at(-1)}: ${e.msg}`).join('. ') : 'Unable to connect. Please try again.';
};
export const money = (amount) => `KSh ${Number(amount || 0).toLocaleString('en-KE', {maximumFractionDigits: 2})}`;
export const imageUrl = (url) => url?.startsWith('/api/') ? `${API_URL}${url}` : url;
export const unit = (category) => ({Rent: '/ month', Vacation: '/ night', Outings: '/ person / day', Land: ''}[category]);
export const HERO = 'https://images.unsplash.com/photo-1596178067639-5c6e68aea6dc?auto=format&fit=crop&w=2400&q=85';