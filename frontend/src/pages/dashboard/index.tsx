import { useState, useEffect } from 'react';
import { useAuthStore } from '@/store/auth.store';
import { api } from '@/api/axios';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
  CardAction,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import {
  ShieldCheck,
  ShieldX,
  Globe,
  Brain,
  Info,
  Loader2,
} from 'lucide-react';

interface ConsentStatus {
  has_active_consent: boolean;
  granted_at: string | null;
  revoked_at: string | null;
}

export function DashboardPage() {
  const { user } = useAuthStore();
  const [consentStatus, setConsentStatus] = useState<ConsentStatus | null>(null);
  const [isLoadingConsent, setIsLoadingConsent] = useState(false);

  const fullName = user?.full_name ?? user?.phone_hash ?? 'User';
  const isActive = consentStatus?.has_active_consent ?? false;

  async function fetchConsentStatus() {
    setIsLoadingConsent(true);
    try {
      const { data } = await api.get('/consents/status');
      setConsentStatus(data);
    } catch (err) {
      console.error('Failed to load consent status', err);
    } finally {
      setIsLoadingConsent(false);
    }
  }

  async function handleGrantConsent() {
    setIsLoadingConsent(true);
    try {
      await api.post('/consents/grant', { channel: 'WEB' });
      await fetchConsentStatus();
    } catch (err) {
      console.error('Failed to grant consent', err);
    } finally {
      setIsLoadingConsent(false);
    }
  }

  async function handleRevokeConsent() {
    setIsLoadingConsent(true);
    try {
      await api.post('/consents/revoke');
      await fetchConsentStatus();
    } catch (err) {
      console.error('Failed to revoke consent', err);
    } finally {
      setIsLoadingConsent(false);
    }
  }

  useEffect(() => {
    fetchConsentStatus();
  }, []);

  return (
    <div className="space-y-6">
      {isLoadingConsent && !consentStatus ? (
        <div className="space-y-6">
          <Skeleton className="h-8 w-[200px]" />
          <Skeleton className="h-[120px] w-full" />
          <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
            <Skeleton className="h-[250px] md:col-span-2" />
            <Skeleton className="h-[250px]" />
          </div>
        </div>
      ) : (
        <>
          <h1>Панель управления</h1>
          <p>Добро пожаловать, {fullName}</p>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>Согласие (152-ФЗ)</CardTitle>
            <CardDescription>Управление согласием на обработку персональных данных</CardDescription>
            <CardAction>
              <Badge variant={isActive ? 'default' : 'destructive'}>
                {isActive ? <ShieldCheck className="mr-1 size-3" /> : <ShieldX className="mr-1 size-3" />}
                {isActive ? 'Предоставлено' : 'Не предоставлено'}
              </Badge>
            </CardAction>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-foreground">Статус</p>
                <p className="text-sm text-muted-foreground">
                  {isActive ? 'Согласие активно' : 'Согласие не предоставлено'}
                </p>
              </div>
              <Button
                variant={isActive ? 'destructive' : 'default'}
                disabled={isLoadingConsent}
                onClick={isActive ? handleRevokeConsent : handleGrantConsent}
              >
                {isLoadingConsent && <Loader2 className="mr-2 size-4 animate-spin" />}
                {isActive ? 'Отозвать согласие' : 'Предоставить согласие'}
              </Button>
            </div>
            {consentStatus?.granted_at && (
              <p className="text-xs text-muted-foreground">Предоставлено: {new Date(consentStatus.granted_at).toLocaleDateString()}</p>
            )}
            {consentStatus?.revoked_at && (
              <p className="text-xs text-muted-foreground">Отозвано: {new Date(consentStatus.revoked_at).toLocaleDateString()}</p>
            )}
            <Alert>
              <Info className="size-4" />
              <AlertDescription>Для персонализированных сервисов необходимо согласие в соответствии с 152-ФЗ.</AlertDescription>
            </Alert>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="space-y-4">
            <h3 className="text-sm font-medium text-foreground">О системе</h3>
            <div className="space-y-2">
              <div className="flex items-start gap-2">
                <Globe className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Омниканальность</p>
                  <p className="text-xs text-muted-foreground">Единое взаимодействие через все каналы</p>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <Brain className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Долгосрочная память</p>
                  <p className="text-xs text-muted-foreground">Постоянный контекст между сессиями</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
        </>
      )}
    </div>
  );
}
