import {BrowserRouter,Routes,Route,useLocation,Link} from 'react-router-dom';
import {Toaster} from 'sonner';
import {AppProvider} from './context';
import {Header,Footer} from './components/Layout';
import Home from './pages/Home';
import Properties from './pages/Properties';
import Details from './pages/Details';
import Auth,{Protected,AuthCallback} from './pages/Auth';
import ListingForm from './pages/ListingForm';
import Dashboard,{MyBookings} from './pages/Dashboard';
import {PlansPage,PaymentPage} from './pages/Payments';
import './App.css';

function AppRouter(){
  const location=useLocation();
  if(location.hash.includes('session_id='))return <AuthCallback/>;
  return <><Header/><Routes><Route path="/" element={<Home/>}/><Route path="/properties" element={<Properties/>}/><Route path="/properties/:id" element={<Details/>}/><Route path="/signin" element={<Auth/>}/><Route path="/saved" element={<Protected><Properties saved/></Protected>}/><Route path="/list-property" element={<Protected><ListingForm/></Protected>}/><Route path="/list-property/:id" element={<Protected><ListingForm/></Protected>}/><Route path="/dashboard" element={<Protected><Dashboard/></Protected>}/><Route path="/bookings" element={<Protected><MyBookings/></Protected>}/><Route path="/plans" element={<Protected><PlansPage/></Protected>}/><Route path="/payment/success" element={<PaymentPage/>}/><Route path="/payment/cancel" element={<PaymentPage cancelled/>}/><Route path="*" element={<main className="container page empty-state"><h1 data-testid="not-found-title">This place is off the map.</h1><Link to="/" className="action" data-testid="not-found-home">Back to home</Link></main>}/></Routes><Footer/></>;
}
export default function App(){return <BrowserRouter><AppProvider><AppRouter/><Toaster theme="dark" position="bottom-right" richColors closeButton/></AppProvider></BrowserRouter>;}