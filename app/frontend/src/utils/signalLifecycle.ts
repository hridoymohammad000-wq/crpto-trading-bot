import type { Signal } from '../types';

export function evaluateSignalExpiry(sig: Signal, nowMs: number): Signal {
  if (!sig.signalTime || !sig.expiresAt) return sig;
  
  const signalTime = new Date(sig.signalTime).getTime();
  const expiresAt = new Date(sig.expiresAt).getTime();
  
  const ageSec = Math.max(0, (nowMs - signalTime) / 1000);
  const isExpired = nowMs >= expiresAt;
  
  let displayAge = `${Math.floor(ageSec)}s`;
  if (ageSec >= 60) {
    displayAge = `${Math.floor(ageSec / 60)}m ${Math.floor(ageSec % 60)}s`;
  }

  let newStatus = sig.status;
  if (isExpired && newStatus === 'New') {
    newStatus = 'Expired';
  }

  if (sig.isExpired === isExpired && sig.age === displayAge && sig.status === newStatus) {
    return sig;
  }
  
  return {
    ...sig,
    ageSeconds: ageSec,
    age: displayAge,
    isExpired,
    status: newStatus
  };
}
