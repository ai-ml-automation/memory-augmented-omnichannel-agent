import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/auth.store';
import { api } from '../../api/axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { Settings, ToggleLeft, ToggleRight, Server, Activity, Loader2 } from 'lucide-react';

interface HealthStatus {
  status: string;
  services: Record<string, string>;
}

interface VoiceHealth {
  asr_enabled: boolean;
  tts_enabled: boolean;
  voice_enabled: boolean;
}

interface LLMHealth {
  provider: string;
  enabled: boolean;
  initialized: boolean;
}

interface FeatureFlags {
  enable_llm: boolean;
  enable_voice: boolean;
  enable_asr: boolean;
  enable_tts: boolean;
  enable_memory: boolean;
}

const FLAG_LABELS: Record<string, string> = {
  enable_llm: 'LLM (языковая модель)',
  enable_voice: 'Голосовой пайплайн',
  enable_asr: 'ASR (распознавание речи)',
  enable_tts: 'TTS (синтез речи)',
  enable_memory: 'Память (векторный store)',
};

export function AdminSettingsPage() {
  const { isAuthenticated, user } = useAuthStore();
  const navigate = useNavigate();

  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [voiceHealth, setVoiceHealth] = useState<VoiceHealth | null>(null);
  const [llmHealth, setLlmHealth] = useState<LLMHealth | null>(null);
  const [flags, setFlags] = useState<FeatureFlags | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [decayRunning, setDecayRunning] = useState(false);
  const [decayResult, setDecayResult] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    if (user?.role !== 'admin') {
      navigate('/dashboard');
      return;
    }
    fetchAllStatuses();
  }, [isAuthenticated, user, navigate]);

  const fetchAllStatuses = async () => {
    setLoading(true);
    setError(null);
    try {
      const [healthRes, voiceRes, llmRes] = await Promise.allSettled([
        api.get('/health'),
        api.get('/voice/health'),
        api.get('/chat/health'),
      ]);

      if (healthRes.status === 'fulfilled') setHealth(healthRes.value.data);
      if (voiceRes.status === 'fulfilled') setVoiceHealth(voiceRes.value.data);
      if (llmRes.status === 'fulfilled') setLlmHealth(llmRes.value.data);

      const voiceData = voiceRes.status === 'fulfilled' ? voiceRes.value.data : {};
      const llmData = llmRes.status === 'fulfilled' ? llmRes.value.data : {};

      setFlags({
        enable_llm: llmData.enabled || false,
        enable_voice: voiceData.voice_enabled || false,
        enable_asr: voiceData.asr_enabled || false,
        enable_tts: voiceData.tts_enabled || false,
        enable_memory: false,
      });

      if (healthRes.status === 'rejected' && voiceRes.status === 'rejected') {
        setError('Не удалось загрузить статусы сервисов');
      }
    } catch {
      setError('Ошибка загрузки статусов');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleFlag = (_flag: keyof FeatureFlags) => {
    // Заглушка: бэкенд не поддерживает изменение флагов на лету
    alert('Изменение Feature Flags требует перезапуска сервисов с новыми значениями в .env');
  };

  const handleRunDecay = async () => {
    setDecayRunning(true);
    setDecayResult(null);
    try {
      // Заглушка: DecayAgent запускается через Celery Beat
      await new Promise((resolve) => setTimeout(resolve, 1500));
      setDecayResult('DecayAgent будет выполнен по расписанию (Celery Beat)');
    } catch {
      setDecayResult('Ошибка запуска DecayAgent');
    } finally {
      setDecayRunning(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <header className="border-b bg-card">
          <div className="max-w-7xl mx-auto px-4 py-6 flex justify-between items-center">
            <div className="flex items-center gap-2">
              <Skeleton className="size-6 rounded" />
              <Skeleton className="h-8 w-[350px]" />
            </div>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-4 py-8 space-y-6">
          <Skeleton className="h-[120px] w-full" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Skeleton className="h-[200px]" />
            <Skeleton className="h-[200px]" />
          </div>
          <Skeleton className="h-[250px] w-full" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Skeleton className="h-[150px]" />
            <Skeleton className="h-[150px]" />
            <Skeleton className="h-[150px]" />
          </div>
          <Skeleton className="h-[100px] w-full" />
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card">
        <div className="max-w-7xl mx-auto px-4 py-6 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Settings className="size-6 text-muted-foreground" />
            <h1 className="text-3xl font-bold text-foreground">
              Административные настройки
            </h1>
          </div>
          <Link
            to="/dashboard"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            &larr; Назад
          </Link>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8 space-y-6">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Feature Flags */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <ToggleLeft className="size-5 text-muted-foreground" />
              <CardTitle>Feature Flags (ENABLE_*)</CardTitle>
            </div>
            <CardDescription>
              Изменение флагов требует перезапуска сервисов. Значения задаются в
              файле .env.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {flags &&
                Object.entries(flags).map(([key, value]) => (
                  <div
                    key={key}
                    className="flex items-center justify-between p-3 bg-muted/50 rounded-lg"
                  >
                    <span className="text-sm font-medium text-foreground">
                      {FLAG_LABELS[key] || key}
                    </span>
                    <div className="flex items-center gap-3">
                      <Badge variant={value ? 'default' : 'destructive'}>
                        {value ? 'Вкл' : 'Выкл'}
                      </Badge>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          handleToggleFlag(key as keyof FeatureFlags)
                        }
                      >
                        {value ? (
                          <ToggleRight className="size-4" />
                        ) : (
                          <ToggleLeft className="size-4" />
                        )}
                        {value ? 'Отключить' : 'Включить'}
                      </Button>
                    </div>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>

        {/* Health Checks */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Server className="size-5 text-muted-foreground" />
              <CardTitle>Статус сервисов (Health Checks)</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="border border-border rounded-lg p-4">
                <h3 className="font-medium text-foreground">Система</h3>
                <p
                  className={`text-sm ${
                    health?.status === 'healthy'
                      ? 'text-emerald-600'
                      : 'text-destructive'
                  }`}
                >
                  {health?.status || 'Недоступен'}
                </p>
                {health?.services && (
                  <div className="mt-2 text-xs text-muted-foreground space-y-1">
                    {Object.entries(health.services).map(([name, status]) => (
                      <div key={name}>
                        {name}:{' '}
                        <span
                          className={
                            status === 'healthy'
                              ? 'text-emerald-600'
                              : 'text-destructive'
                          }
                        >
                          {status}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="border border-border rounded-lg p-4">
                <h3 className="font-medium text-foreground">
                  Голосовой пайплайн
                </h3>
                <div className="mt-2 space-y-1 text-sm">
                  <p>
                    ASR:{' '}
                    <span
                      className={
                        voiceHealth?.asr_enabled
                          ? 'text-emerald-600'
                          : 'text-destructive'
                      }
                    >
                      {voiceHealth?.asr_enabled ? 'Включён' : 'Отключён'}
                    </span>
                  </p>
                  <p>
                    TTS:{' '}
                    <span
                      className={
                        voiceHealth?.tts_enabled
                          ? 'text-emerald-600'
                          : 'text-destructive'
                      }
                    >
                      {voiceHealth?.tts_enabled ? 'Включён' : 'Отключён'}
                    </span>
                  </p>
                  <p>
                    Voice:{' '}
                    <span
                      className={
                        voiceHealth?.voice_enabled
                          ? 'text-emerald-600'
                          : 'text-destructive'
                      }
                    >
                      {voiceHealth?.voice_enabled ? 'Включён' : 'Отключён'}
                    </span>
                  </p>
                </div>
              </div>

              <div className="border border-border rounded-lg p-4">
                <h3 className="font-medium text-foreground">LLM</h3>
                <div className="mt-2 space-y-1 text-sm">
                  <p>Провайдер: {llmHealth?.provider || '—'}</p>
                  <p>
                    Статус:{' '}
                    <span
                      className={
                        llmHealth?.enabled && llmHealth?.initialized
                          ? 'text-emerald-600'
                          : 'text-destructive'
                      }
                    >
                      {llmHealth?.enabled
                        ? llmHealth?.initialized
                          ? 'Работает'
                          : 'Инициализация'
                        : 'Отключён'}
                    </span>
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* DecayAgent */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Activity className="size-5 text-muted-foreground" />
              <CardTitle>Фоновые задачи</CardTitle>
            </div>
            <CardDescription>
              Запускает фоновый агент устаревания фактов (Memory Decay).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <Button onClick={handleRunDecay} disabled={decayRunning}>
                {decayRunning && <Loader2 className="size-4 animate-spin" />}
                {decayRunning ? 'Запуск...' : 'Запустить DecayAgent'}
              </Button>
              {decayResult && (
                <Badge
                  variant={
                    decayResult.includes('Ошибка') ? 'destructive' : 'default'
                  }
                >
                  {decayResult}
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
