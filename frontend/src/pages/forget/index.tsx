import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/auth.store';
import { api } from '../../api/axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Input } from '@/components/ui/input';
import { Trash2, AlertTriangle, Shield, Loader2 } from 'lucide-react';

type PageStep = 'confirm' | 'verifying' | 'success' | 'error';

export function ForgetPage() {
  const { isAuthenticated, logout } = useAuthStore();
  const navigate = useNavigate();

  const [step, setStep] = useState<PageStep>('confirm');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [confirmationText, setConfirmationText] = useState('');

  if (!isAuthenticated) {
    navigate('/login');
    return null;
  }

  const CONFIRM_WORD = 'УДАЛИТЬ';

  const handleDeleteRequest = async () => {
    if (confirmationText !== CONFIRM_WORD) {
      setErrorMessage('Введите слово ' + CONFIRM_WORD);
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);
    setStep('verifying');

    try {
      await api.post('/consents/data-deletion');
      setStep('success');
      setTimeout(() => {
        logout();
        navigate('/login');
      }, 3000);
    } catch (err: unknown) {
      setStep('error');
      const message = err instanceof Error ? err.message : 'Error deleting data';
      setErrorMessage(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    navigate('/dashboard');
  };

  const willBeDeleted = [
    'Все факты и записи в памяти агента',
    'История сессий и обращений',
    'Согласие на обработку данных',
    'Привязки к каналам (Telegram, VK, MAX, голос)',
    'Все аудиофайлы',
    'Ваш профиль пользователя',
  ];

  return (
    <div className="min-h-screen bg-muted/30 flex items-center justify-center px-4">
      <div className="max-w-2xl w-full mx-4">
        <Card className="shadow-lg overflow-hidden">
          <CardHeader className="bg-destructive/10">
            <CardTitle className="text-2xl font-bold flex items-center gap-2">
              <Trash2 className="size-6 text-destructive" />
              {'Право на забвение (152-ФЗ)'}
            </CardTitle>
            <CardDescription>
              {'Безопасное удаление всех персональных данных'}
            </CardDescription>
          </CardHeader>

          <CardContent>
            {step === 'confirm' && (
              <>
                <Alert variant="destructive" className="mb-6">
                  <AlertTriangle className="size-4 text-destructive" />
                  <AlertDescription>
                    <strong>{'Внимание!'}</strong>{' '}
                    {'Это действие необратимо. Все данные будут удалены.'}
                  </AlertDescription>
                </Alert>

                <p className="text-muted-foreground mb-4">
                  {'В соответствии с 152-ФЗ вы имеете право на удаление всех персональных данных.'}
                </p>

                <div className="rounded-lg bg-muted/50 p-4 mb-4">
                  <p className="text-sm text-muted-foreground">
                    <strong>{'Будут удалены:'}</strong>
                  </p>
                  <ul className="list-disc list-inside text-sm text-muted-foreground mt-2 space-y-1">
                    {willBeDeleted.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>

                <div className="space-y-2 mb-4">
                  <label className="text-sm font-medium leading-none">
                    {'Введите слово '}{' '}
                    <strong className="text-destructive">{CONFIRM_WORD}</strong>
                  </label>
                  <div className="relative">
                    <Shield className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                    <Input
                      type="text"
                      value={confirmationText}
                      onChange={(e) => setConfirmationText(e.target.value)}
                      placeholder={CONFIRM_WORD}
                      className="pl-9"
                      aria-invalid={!!errorMessage}
                    />
                  </div>
                  {errorMessage && (
                    <p className="text-sm text-destructive">{errorMessage}</p>
                  )}
                </div>

                <div className="flex gap-4">
                  <Button variant="outline" onClick={handleCancel} className="flex-1">
                    {'Отмена'}
                  </Button>
                  <Button variant="destructive" onClick={handleDeleteRequest} disabled={isLoading} className="flex-1">
                    {isLoading ? (
                      <>
                        <Loader2 className="mr-2 size-4 animate-spin" />
                        {'Обработка...'}
                      </>
                    ) : (
                      <>
                        <Trash2 className="mr-2 size-4" />
                        {'Удалить мои данные'}
                      </>
                    )}
                  </Button>
                </div>
              </>
            )}

            {step === 'verifying' && (
              <div className="text-center py-8">
                <Loader2 className="size-12 text-destructive animate-spin mx-auto mb-4" />
                <p className="text-muted-foreground">{'Удаление данных...'}</p>
                <p className="text-sm text-muted-foreground mt-2">
                  {'Пожалуйста, не закрывайте страницу'}
                </p>
              </div>
            )}

            {step === 'success' && (
              <div className="text-center py-8">
                <div className="mx-auto flex items-center justify-center size-12 rounded-full bg-primary/10 mb-4">
                  <Shield className="size-6 text-primary" />
                </div>
                <h2 className="text-xl font-semibold mb-2">
                  {'Данные успешно удалены'}
                </h2>
                <p className="text-muted-foreground">
                  {'Все персональные данные удалены по 152-ФЗ.'}
                </p>
                <p className="text-sm text-muted-foreground mt-2">
                  {'Перенаправление через несколько секунд...'}
                </p>
              </div>
            )}

            {step === 'error' && (
              <div className="text-center py-8">
                <div className="mx-auto flex items-center justify-center size-12 rounded-full bg-destructive/10 mb-4">
                  <AlertTriangle className="size-6 text-destructive" />
                </div>
                <h2 className="text-xl font-semibold mb-2">{'Ошибка'}</h2>
                <p className="text-muted-foreground">{errorMessage}</p>
                <Button onClick={() => setStep('confirm')} className="mt-4">
                  {'Попытать снова'}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="mt-4 text-center text-sm text-muted-foreground">
          <Link to="/dashboard" className="text-primary underline-offset-4 hover:underline font-medium">
            {'← Вернуться на панель'}
          </Link>
        </div>
      </div>
    </div>
  );
}