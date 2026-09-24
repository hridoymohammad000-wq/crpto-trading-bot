import { useState } from 'react';
import { apiClient } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { Key } from 'lucide-react';

export function ChangePassword() {
  const { logout } = useAuth();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setMessage('');
    
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setIsLoading(true);
    try {
      const res: any = await apiClient.post('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      setMessage(res.detail || 'Password changed successfully');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      // Force logout on password change as requested
      setTimeout(() => logout(), 2000);
    } catch (err: any) {
      setError(err?.message || 'Failed to change password');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 max-w-md mt-6">
      <div className="flex items-center gap-2 mb-4">
        <Key className="w-5 h-5 text-blue-400" />
        <h3 className="text-lg font-medium text-white">Change Password</h3>
      </div>
      
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <div className="text-sm text-red-400 bg-red-950/30 p-2 rounded">{error}</div>}
        {message && <div className="text-sm text-emerald-400 bg-emerald-950/30 p-2 rounded">{message}</div>}
        
        <div>
          <label className="block text-sm text-slate-400 mb-1">Current Password</label>
          <input
            type="password"
            required
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="block text-sm text-slate-400 mb-1">New Password</label>
          <input
            type="password"
            required
            minLength={8}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="block text-sm text-slate-400 mb-1">Confirm New Password</label>
          <input
            type="password"
            required
            minLength={8}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>
        
        <button
          type="submit"
          disabled={isLoading}
          className="w-full bg-slate-800 hover:bg-slate-700 text-white font-medium py-2 px-4 rounded text-sm transition-colors border border-slate-700"
        >
          {isLoading ? 'Updating...' : 'Update Password'}
        </button>
      </form>
    </div>
  );
}
