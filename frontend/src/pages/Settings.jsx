import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import {
  apiFetch,
  checkAuth,
  clearCsrf,
  clearLoginSession,
  downloadAccountExport,
  parseApiResponse,
  primeCsrf,
} from '../api';
import { btnDanger, btnPrimary, card, input, label, subtext } from '../utils/theme';

function Alert({ type, children }) {
  const tones = {
    error: 'border-red-400/20 bg-red-500/10 text-red-300',
    success: 'border-emerald-400/20 bg-emerald-500/10 text-emerald-200',
  };
  return <div className={`rounded-xl border px-4 py-3 text-sm ${tones[type]}`}>{children}</div>;
}

export default function Settings() {
  const navigate = useNavigate();
  const deletePasswordRef = useRef(null);
  const deleteModalRef = useRef(null);
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
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState('');
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [deleteConfirmation, setDeleteConfirmation] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const requiredConfirmation = `DELETE ${username}`;
  const deletionReady = Boolean(deletePassword)
    && deleteConfirmation.trim() === requiredConfirmation;

  useEffect(() => {
    primeCsrf();
    checkAuth()
      .then((data) => {
        if (!data.authenticated) {
          navigate('/');
          return null;
        }
        return apiFetch('/api/profile');
      })
      .then((response) => {
        if (!response) return null;
        if (response.status === 401) {
          navigate('/');
          return null;
        }
        return response.json();
      })
      .then((data) => {
        if (!data) return;
        if (data.username) setUsername(data.username);
        if (data.email) setEmail(data.email);
      })
      .catch(() => navigate('/'))
      .finally(() => setLoading(false));
  }, [navigate]);

  useEffect(() => {
    if (!deleteOpen) return undefined;
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    deletePasswordRef.current?.focus();

    const handleModalKeyDown = (event) => {
      if (event.key === 'Escape' && !deleting) {
        setDeleteOpen(false);
        return;
      }
      if (event.key !== 'Tab') return;
      const focusable = deleteModalRef.current?.querySelectorAll(
        'button:not([disabled]), input:not([disabled])',
      );
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleModalKeyDown);
    return () => {
      document.removeEventListener('keydown', handleModalKeyDown);
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, [deleteOpen, deleting]);

  const saveProfile = async () => {
    setProfileError('');
    setProfileMessage('');
    setProfileSaving(true);
    try {
      const response = await apiFetch('/api/profile', {
        method: 'PUT',
        body: JSON.stringify({ username, email }),
      });
      const { data, ok } = await parseApiResponse(response);
      if (ok && data.verification_required) {
        clearLoginSession();
        clearCsrf();
        navigate('/verify-email-sent', {
          replace: true,
          state: { email: data.email, message: data.message },
        });
      } else if (ok) {
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
      const response = await apiFetch('/api/change-password', {
        method: 'POST',
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      const { data, ok, status } = await parseApiResponse(response);
      if (status === 429) {
        setPasswordError(data.error || 'Too many attempts. Wait a few minutes and try again.');
      } else if (ok) {
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

  const downloadData = async () => {
    if (exporting) return;
    setExportError('');
    setExporting(true);
    try {
      await downloadAccountExport();
    } catch (error) {
      setExportError(error.message || 'Could not download account data.');
    } finally {
      setExporting(false);
    }
  };

  const openDeleteModal = () => {
    setDeletePassword('');
    setDeleteConfirmation('');
    setDeleteError('');
    setDeleteOpen(true);
  };

  const closeDeleteModal = () => {
    if (!deleting) setDeleteOpen(false);
  };

  const deleteAccount = async () => {
    if (!deletionReady || deleting) return;
    setDeleteError('');
    setDeleting(true);
    try {
      const response = await apiFetch('/api/account', {
        method: 'DELETE',
        body: JSON.stringify({
          current_password: deletePassword,
          confirmation: deleteConfirmation,
        }),
      });
      const { data, ok, status } = await parseApiResponse(response);
      if (status === 429) {
        setDeleteError(data.error || 'Too many attempts. Try again later.');
      } else if (ok) {
        clearLoginSession();
        clearCsrf();
        navigate('/', { replace: true, state: { accountDeleted: true } });
      } else {
        setDeleteError(data.error || 'Could not delete account.');
      }
    } catch {
      setDeleteError('Could not reach the server.');
    } finally {
      setDeleting(false);
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
              onChange={(event) => setUsername(event.target.value)}
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
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              placeholder="you@example.com"
            />
          </div>
        </div>
        <button type="button" disabled={profileSaving} onClick={saveProfile} className={`${btnPrimary} mt-5 w-full`}>
          {profileSaving ? 'Saving…' : 'Save profile'}
        </button>
      </section>

      <section className={`${card} p-6`}>
        <h2 className="mb-1 text-base font-semibold text-purple-text">Change password</h2>
        <p className={`mb-5 ${subtext}`}>At least 8 characters with uppercase, number, and special character.</p>
        {passwordError && <div className="mb-4"><Alert type="error">{passwordError}</Alert></div>}
        {passwordMessage && <div className="mb-4"><Alert type="success">{passwordMessage}</Alert></div>}
        <div className="space-y-4">
          <div>
            <label className={label}>Current password</label>
            <input
              type="password"
              className={input}
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
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
              onChange={(event) => setNewPassword(event.target.value)}
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
              onChange={(event) => setConfirmPassword(event.target.value)}
              onKeyDown={(event) => event.key === 'Enter' && savePassword()}
              autoComplete="new-password"
              placeholder="••••••••"
            />
          </div>
        </div>
        <button type="button" disabled={passwordSaving} onClick={savePassword} className={`${btnPrimary} mt-5 w-full`}>
          {passwordSaving ? 'Updating…' : 'Update password'}
        </button>
      </section>

      <section className={`${card} p-6`}>
        <h2 className="mb-1 text-base font-semibold text-purple-text">Account data</h2>
        <p className={`mb-5 ${subtext}`}>Download a readable PDF summary with your complete account records.</p>
        {exportError && <div className="mb-4"><Alert type="error">{exportError}</Alert></div>}
        <button type="button" disabled={exporting} onClick={downloadData} className={`${btnPrimary} w-full`}>
          {exporting ? 'Preparing download…' : 'Download account data'}
        </button>

        <div className="mt-6 border-t border-red-400/20 pt-6">
          <h3 className="mb-1 text-sm font-semibold text-red-300">Delete account</h3>
          <p className="mb-4 text-sm leading-6 text-red-200/70">
            Permanently delete your account and every budget, expense, goal, and setting it contains.
          </p>
          <button type="button" onClick={openDeleteModal} className={`${btnDanger} w-full`}>
            Delete account
          </button>
        </div>
      </section>

      {deleteOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
          onMouseDown={(event) => event.target === event.currentTarget && closeDeleteModal()}
        >
          <div
            ref={deleteModalRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-account-title"
            aria-describedby="delete-account-description"
            className="w-full max-w-lg rounded-2xl border border-red-400/25 bg-purple-deep p-6 shadow-2xl"
          >
            <h2 id="delete-account-title" className="text-xl font-semibold text-red-300">
              Delete account permanently?
            </h2>
            <p id="delete-account-description" className="mt-2 text-sm leading-6 text-purple-soft">
              This cannot be undone. Download your account data first if you want to keep a copy.
            </p>
            {deleteError && <div className="mt-4"><Alert type="error">{deleteError}</Alert></div>}
            <div className="mt-5 space-y-4">
              <div>
                <label className={label}>Current password</label>
                <input
                  ref={deletePasswordRef}
                  type="password"
                  className={input}
                  value={deletePassword}
                  onChange={(event) => setDeletePassword(event.target.value)}
                  disabled={deleting}
                  autoComplete="current-password"
                  placeholder="••••••••"
                />
              </div>
              <div>
                <label className={label}>
                  Type <span className="font-semibold text-red-300">{requiredConfirmation}</span> to confirm
                </label>
                <input
                  className={input}
                  value={deleteConfirmation}
                  onChange={(event) => setDeleteConfirmation(event.target.value)}
                  onKeyDown={(event) => event.key === 'Enter' && deleteAccount()}
                  disabled={deleting}
                  autoComplete="off"
                  spellCheck="false"
                  placeholder={requiredConfirmation}
                />
              </div>
            </div>
            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={closeDeleteModal}
                disabled={deleting}
                className="rounded-xl border border-purple-border px-5 py-3 text-sm font-medium text-purple-text transition hover:bg-white/5 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={deleteAccount}
                disabled={!deletionReady || deleting}
                className="rounded-xl bg-red-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {deleting ? 'Deleting…' : 'Delete permanently'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
