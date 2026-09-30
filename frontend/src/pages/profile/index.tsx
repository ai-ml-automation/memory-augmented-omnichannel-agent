import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/auth.store';
import { api } from '../../api/axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { User, Lock, Shield, Loader2, Save } from 'lucide-react';

interface ConsentStatus {
  has_active_consent: boolean;
  granted_at: string | null;
  revoked_at: string | null;
}

export function ProfilePage() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState(user?.full_name || '');
  const [consentStatus, setConsentStatus] = useState<ConsentStatus | null>(null);
  const [isLoadingConsent, setIsLoadingConsent] = useState(false);
  const [isLoadingUpdate, setIsLoadingUpdate] = useState(false);
  const [updateMessage, setUpdateMessage] = useState<string | null>(null);

  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordMessage, setPasswordMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchConsentStatus();
  }, []);

  const fetchConsentStatus = async () => {
    try {
      const { data } = await api.get('/consents/status');
      setConsentStatus(data);
    } catch (error) {
      console.error('Failed to fetch consent status:', error);
    }
  };

  const handleGrantConsent = async () => {
    setIsLoadingConsent(true);
    try {
      await api.post('/consents/grant', { channel: 'WEB' });
      await fetchConsentStatus();
    } catch (error) {
      console.error('Failed to grant consent:', error);
    } finally {
      setIsLoadingConsent(false);
    }
  };

  const handleRevokeConsent = async () => {
    if (!confirm('Вы уверены, что хотите отозвать согласие? Все данные будут удалены.')) {
      return;
    }
    setIsLoadingConsent(true);
    try {
      await api.post('/consents/revoke');
      await fetchConsentStatus();
    } catch (error) {
      console.error('Failed to revoke consent:', error);
    } finally {
      setIsLoadingConsent(false);
    }
  };

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoadingUpdate(true);
    setUpdateMessage(null);
    try {
      // Заглушка: бэкенд пока не поддерживает обновление /users/me
      setUpdateMessage('Обновление профиля пока не реализовано на бэкенде.');
    } catch {
      setUpdateMessage('Ошибка обновления профиля');
    } finally {
      setIsLoadingUpdate(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setPasswordMessage('Пароли не совпадают');
      return;
    }
    if (newPassword.length < 8) {
      setPasswordMessage('Пароль должен быть не менее 8 символов');
      return;
    }
    setPasswordMessage(null);
    // Заглушка: смена пароля не реализована на бэкенде
    setPasswordMessage('Смена пароля пока не реализована на бэкенде.');
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  if (!user) {
    navigate('/login');
    return null;
  }

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="border-b bg-card">
        <div className="max-w-4xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
            <User className="size-5" />
            Профиль пользователя
          </h1>
          <Button variant="destructive" size="sm" onClick={handleLogout}>
            Выйти
          </Button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto py-6 px-4 space-y-6">
        {/* Информация о пользователе */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="size-4 text-muted-foreground" />
              Личные данные
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-muted-foreground">
                  ID пользователя
                </label>
                <p className="mt-1 text-sm text-foreground">{user.id}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-muted-foreground">
                  Телефон (хеш)
                </label>
                <p className="mt-1 text-sm text-foreground">{user.phone_hash}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-muted-foreground">
                  Дата регистрации
                </label>
                <p className="mt-1 text-sm text-foreground">
                  {user.created_at
                    ? new Date(user.created_at).toLocaleString('ru-RU')
                    : '—'}
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-muted-foreground">
                  Роль
                </label>
                <p className="mt-1 text-sm text-foreground">
                  {user.role || 'operator'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Редактирование профиля */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Save className="size-4 text-muted-foreground" />
              Редактировать профиль
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleUpdateProfile} className="space-y-4">
              <div>
                <label
                  htmlFor="fullName"
                  className="block text-sm font-medium text-muted-foreground"
                >
                  Полное имя
                </label>
                <Input
                  id="fullName"
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="mt-1"
                />
              </div>
              {updateMessage && (
                <Alert
                  variant={
                    updateMessage.includes('Ошибка') ? 'destructive' : 'default'
                  }
                >
                  <AlertDescription>{updateMessage}</AlertDescription>
                </Alert>
              )}
              <Button type="submit" disabled={isLoadingUpdate}>
                {isLoadingUpdate && (
                  <Loader2 className="size-4 animate-spin" />
                )}
                {isLoadingUpdate ? 'Сохранение...' : 'Сохранить изменения'}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Смена пароля */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lock className="size-4 text-muted-foreground" />
              Смена пароля
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleChangePassword} className="space-y-4">
              <div>
                <label
                  htmlFor="oldPassword"
                  className="block text-sm font-medium text-muted-foreground"
                >
                  Текущий пароль
                </label>
                <Input
                  id="oldPassword"
                  type="password"
                  value={oldPassword}
                  onChange={(e) => setOldPassword(e.target.value)}
                  className="mt-1"
                  required
                />
              </div>
              <div>
                <label
                  htmlFor="newPassword"
                  className="block text-sm font-medium text-muted-foreground"
                >
                  Новый пароль
                </label>
                <Input
                  id="newPassword"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="mt-1"
                  required
                  minLength={8}
                />
              </div>
              <div>
                <label
                  htmlFor="confirmPassword"
                  className="block text-sm font-medium text-muted-foreground"
                >
                  Подтвердите новый пароль
                </label>
                <Input
                  id="confirmPassword"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="mt-1"
                  required
                  minLength={8}
                />
              </div>
              {passwordMessage && (
                <Alert
                  variant={
                    passwordMessage.includes('Ошибка') ||
                    passwordMessage.includes('не совпадают')
                      ? 'destructive'
                      : 'default'
                  }
                >
                  <AlertDescription>{passwordMessage}</AlertDescription>
                </Alert>
              )}
              <Button type="submit">
                <Lock className="size-4" />
                Сменить пароль
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Управление согласием */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="size-4 text-muted-foreground" />
              Согласие на обработку персональных данных (152-ФЗ)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  Статус согласия:
                </p>
                <p
                  className={`text-sm ${
                    consentStatus?.has_active_consent
                      ? 'text-emerald-600'
                      : 'text-destructive'
                  }`}
                >
                  {consentStatus?.has_active_consent
                    ? 'Выдано'
                    : 'Не выдано / Отозвано'}
                </p>
              </div>
              <div>
                {consentStatus?.has_active_consent ? (
                  <Button
                    variant="destructive"
                    disabled={isLoadingConsent}
                    onClick={handleRevokeConsent}
                  >
                    {isLoadingConsent && (
                      <Loader2 className="size-4 animate-spin" />
                    )}
                    {isLoadingConsent ? 'Обработка...' : 'Отозвать согласие'}
                  </Button>
                ) : (
                  <Button
                    disabled={isLoadingConsent}
                    onClick={handleGrantConsent}
                  >
                    {isLoadingConsent && (
                      <Loader2 className="size-4 animate-spin" />
                    )}
                    {isLoadingConsent ? 'Обработка...' : 'Выдать согласие'}
                  </Button>
                )}
              </div>
            </div>
            {consentStatus?.granted_at && (
              <div className="text-sm text-muted-foreground">
                <p>
                  Выдано:{' '}
                  {new Date(consentStatus.granted_at).toLocaleString('ru-RU')}
                </p>
                {consentStatus.revoked_at && (
                  <p>
                    Отозвано:{' '}
                    {new Date(consentStatus.revoked_at).toLocaleString('ru-RU')}
                  </p>
                )}
              </div>
            )}
            <Alert>
              <AlertDescription>
                <strong>Важно:</strong> Без вашего согласия система не может
                сохранять и использовать вашу историю обращений для
                персонализации ответов. Вы можете отозвать согласие в любой
                момент, и все ваши данные будут удалены в течение 24 часов.
              </AlertDescription>
            </Alert>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
