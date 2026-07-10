import { useState, useEffect } from 'react';

import { useNavigate } from 'react-router-dom';

import { apiFetch, parseApiResponse, primeCsrf } from '../api';

import {

  card, input, label, btnPrimary, subtext,

} from '../utils/theme';



function Alert({ type, children }) {

  const tones = {

    error: 'border-red-400/20 bg-red-500/10 text-red-300',

    success: 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200',

  };

  return (

    <div className={`rounded-xl border px-4 py-3 text-sm ${tones[type]}`}>

      {children}

    </div>

  );

}



export default function Settings() {

  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);

  const [username, setUsername] = useState('');

  const [email, setEmail] = useState('');

  const [profileSaving, setProfileSaving] = useState(false);

  const [profileMessage, setProfileMessage] = useState('');

  const [profileError, setProfileError] = useState('');



  const [currentPassword, setCurrentPassword] = useState('');

  const [newPassword, setNewPassword] = useState('');

  const [confirmPassword, setConfirmPassword] = useState('');

  const [passwordSaving, setPasswordSaving] = useState(false);

  const [passwordMessage, setPasswordMessage] = useState('');

  const [passwordError, setPasswordError] = useState('');



  useEffect(() => {
    primeCsrf();



    apiFetch('/api/check-auth')

      .then((r) => r.json())

      .then((d) => {

        if (!d.authenticated) {

          navigate('/');

          return;

        }

        return apiFetch('/api/profile');

      })

      .then((r) => {

        if (!r) return;

        if (r.status === 401) {

          navigate('/');

          return;

        }

        return r.json();

      })

      .then((d) => {

        if (!d) return;

        if (d.username) setUsername(d.username);

        if (d.email) setEmail(d.email);

      })

      .catch(() => navigate('/'))

      .finally(() => setLoading(false));

  }, [navigate]);



  const saveProfile = async () => {

    setProfileError('');

    setProfileMessage('');

    setProfileSaving(true);

    try {

      const res = await apiFetch('/api/profile', {

        method: 'PUT',

        body: JSON.stringify({ username, email }),

      });

      const { data, ok } = await parseApiResponse(res);

      if (ok) {

        setProfileMessage('Profile updated.');

        if (data.username) setUsername(data.username);

        if (data.email) setEmail(data.email);

      } else {

        setProfileError(data.error || 'Could not update profile.');

      }

    } catch {

      setProfileError('Could not reach the server.');

    } finally {

      setProfileSaving(false);

    }

  };



  const savePassword = async () => {

    setPasswordError('');

    setPasswordMessage('');

    if (newPassword !== confirmPassword) {

      setPasswordError('New passwords do not match.');

      return;

    }

    setPasswordSaving(true);

    try {

      const res = await apiFetch('/api/change-password', {

        method: 'POST',

        body: JSON.stringify({

          current_password: currentPassword,

          new_password: newPassword,

        }),

      });

      const { data, ok, status } = await parseApiResponse(res);

      if (status === 429) {

        setPasswordError(data.error || 'Too many attempts. Wait a few minutes and try again.');

        return;

      }

      if (ok) {

        setPasswordMessage(data.message || 'Password updated.');

        setCurrentPassword('');

        setNewPassword('');

        setConfirmPassword('');

      } else {

        setPasswordError(data.error || 'Could not update password.');

      }

    } catch {

      setPasswordError('Could not reach the server.');

    } finally {

      setPasswordSaving(false);

    }

  };



  if (loading) {
    return (
      <div className="flex min-h-[240px] items-center justify-center text-purple-soft">
        Loading settings…
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-2xl space-y-6">
      <section className={`${card} p-6`}>

        <h2 className="mb-1 text-base font-semibold text-purple-text">Profile</h2>

        <p className={`mb-5 ${subtext}`}>Your sign-in username and email</p>



        {profileError && <div className="mb-4"><Alert type="error">{profileError}</Alert></div>}

        {profileMessage && <div className="mb-4"><Alert type="success">{profileMessage}</Alert></div>}



        <div className="space-y-4">

          <div>

            <label className={label}>Username</label>

            <input

              className={input}

              value={username}

              onChange={(e) => setUsername(e.target.value)}

              autoComplete="username"

              placeholder="username"

            />

          </div>

          <div>

            <label className={label}>Email</label>

            <input

              type="email"

              className={input}

              value={email}

              onChange={(e) => setEmail(e.target.value)}

              autoComplete="email"

              placeholder="you@example.com"

            />

          </div>

        </div>



        <button

          type="button"

          disabled={profileSaving}

          onClick={saveProfile}

          className={`${btnPrimary} mt-5 w-full`}

        >

          {profileSaving ? 'Saving…' : 'Save profile'}

        </button>

      </section>



      <section className={`${card} p-6`}>

        <h2 className="mb-1 text-base font-semibold text-purple-text">Change password</h2>

        <p className={`mb-5 ${subtext}`}>

          At least 8 characters with uppercase, number, and special character.

        </p>



        {passwordError && <div className="mb-4"><Alert type="error">{passwordError}</Alert></div>}

        {passwordMessage && <div className="mb-4"><Alert type="success">{passwordMessage}</Alert></div>}



        <div className="space-y-4">

          <div>

            <label className={label}>Current password</label>

            <input

              type="password"

              className={input}

              value={currentPassword}

              onChange={(e) => setCurrentPassword(e.target.value)}

              autoComplete="current-password"

              placeholder="••••••••"

            />

          </div>

          <div>

            <label className={label}>New password</label>

            <input

              type="password"

              className={input}

              value={newPassword}

              onChange={(e) => setNewPassword(e.target.value)}

              autoComplete="new-password"

              placeholder="••••••••"

            />

          </div>

          <div>

            <label className={label}>Confirm new password</label>

            <input

              type="password"

              className={input}

              value={confirmPassword}

              onChange={(e) => setConfirmPassword(e.target.value)}

              onKeyDown={(e) => e.key === 'Enter' && savePassword()}

              autoComplete="new-password"

              placeholder="••••••••"

            />

          </div>

        </div>



        <button

          type="button"

          disabled={passwordSaving}

          onClick={savePassword}

          className={`${btnPrimary} mt-5 w-full`}

        >

          {passwordSaving ? 'Updating…' : 'Update password'}

        </button>

      </section>

    </div>

  );

}

