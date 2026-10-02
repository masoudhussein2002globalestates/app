import {useState, useEffect, useRef} from 'react';
import {useNavigate, useLocation, Link, Navigate} from 'react-router-dom';
import {ArrowRight, Building2, Mail, LockKeyhole} from 'lucide-react';
import {useApp} from '../context';
import {api, errorText, HERO} from '../lib/api';
import {Action, Field, Loading} from '../components/Common';
import {toast} from 'sonner';
export const Protected = ({children}) => {const {user,loading}=useApp(),location=useLocation(); if(loading)return <Loading/>;return user?children:<Navigate to="/signin" state={{from:location.pathname+location.search}} replace/>;};
export const AuthCallback = () => {
  const {setUser}=useApp(),navigate=useNavigate(),location=useLocation(),processed=useRef(false);
  useEffect(()=>{if(processed.current)return;processed.current=true;const session_id=new URLSearchParams(location.hash.slice(1)).get('session_id');api.post('/auth/session',{session_id}).then(r=>{setUser(r.data);navigate('/dashboard',{replace:true});}).catch(e=>{toast.error(errorText(e));navigate('/signin',{replace:true});});},[location.hash,navigate,setUser]);
  return null;
};
export default function AuthPage(){
  const {user,setUser}=useApp(),navigate=useNavigate(),location=useLocation(),[register,setRegister]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[form,setForm]=useState({name:'',email:'',password:''});
  if(user)return <Navigate to={location.state?.from||'/dashboard'} replace/>;
  const submit=async e=>{e.preventDefault();setBusy(true);setError('');try{const r=await api.post(register?'/auth/register':'/auth/login',form);setUser(r.data);toast.success(register?'Welcome to Global Estates':'Welcome back');navigate(location.state?.from||'/dashboard',{replace:true});}catch(e){setError(errorText(e));}finally{setBusy(false);}};
  const google=()=>{
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    window.location.href=`https://auth.emergentagent.com/?redirect=${encodeURIComponent(window.location.origin+'/dashboard')}`;
  };
  return <main className="auth-page"><div className="auth-image" style={{backgroundImage:`url(${HERO})`}}><div><Building2 size={40} strokeWidth={1}/><p data-testid="auth-image-heading">Every great story<br/>starts with a place.</p><span data-testid="auth-image-brand">GLOBAL ESTATES</span></div></div><div className="auth-form-wrap"><div className="auth-form"><div className="eyebrow muted" data-testid="auth-eyebrow">YOUR WORLD, A LITTLE CLOSER</div><h1 data-testid="auth-title">{register?'Find your belonging.':'Welcome back.'}</h1><p data-testid="auth-description">{register?'Create your account and start your next chapter.':'Sign in to save, discover, and share extraordinary places.'}</p><Action variant="outline" className="google-button" data-testid="google-signin" onClick={google}><span className="google-g">G</span>Continue with Google</Action><div className="or-divider"><span>or continue with email</span></div><form onSubmit={submit}>{register&&<Field label="Full name" id="auth-name" required minLength={2} maxLength={100} autoComplete="name" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/>}<Field label="Email address" id="auth-email" type="email" required autoComplete="email" placeholder="you@example.com" value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/><Field label="Password" id="auth-password" type="password" required minLength={8} maxLength={72} autoComplete={register?'new-password':'current-password'} placeholder="At least 8 characters" value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/>{error&&<p className="form-error" role="alert" data-testid="auth-error">{error}</p>}<Action type="submit" busy={busy} className="full-width" data-testid="auth-submit">{register?'Create account':'Sign in'}<ArrowRight size={17}/></Action></form><p className="auth-switch" data-testid="auth-switch-label">{register?'Already have an account?':'New to Global Estates?'} <button data-testid="auth-mode-toggle" onClick={()=>{setRegister(!register);setError('');}}>{register?'Sign in':'Create an account'}</button></p><Link to="/properties" className="auth-browse" data-testid="auth-browse">Just looking? Explore properties<ArrowRight size={14}/></Link></div></div></main>;
}