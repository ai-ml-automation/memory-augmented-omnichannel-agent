import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '../../store/auth.store';
import { api } from '../../api/axios';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Mic, MicOff, Volume2, Loader2, Play, Square } from 'lucide-react';

type TestStatus = 'idle' | 'recording' | 'sending' | 'done' | 'error';

const STATUS_LABELS: Record<TestStatus, string> = {
  idle: 'Готов к записи',
  recording: 'Запись...',
  sending: 'Обработка...',
  done: 'Завершено',
  error: 'Ошибка',
};

export function VoiceTestPage() {
  const { user } = useAuthStore();

  const [status, setStatus] = useState<TestStatus>('idle');
  const [asrResult, setAsrResult] = useState<string | null>(null);
  const [llmReply, setLlmReply] = useState<string | null>(null);
  const [ttsAudioUrl, setTtsAudioUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // MediaRecorder
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [audioChunks, setAudioChunks] = useState<Blob[]>([]);

  const handleStartRecord = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) setAudioChunks((prev) => [...prev, e.data]);
      };

      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
      };

      recorder.start();
      setMediaRecorder(recorder);
      setAudioChunks([]);
      setStatus('recording');
      setAsrResult(null);
      setLlmReply(null);
      setTtsAudioUrl(null);
      setError(null);
    } catch {
      setError('Не удалось получить доступ к микрофону');
      setStatus('error');
    }
  };

  const handleStopRecord = () => {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop();
      setStatus('sending');
    }
  };

  const handleProcess = async () => {
    if (audioChunks.length === 0) {
      setError('Сначала запишите аудио');
      setStatus('error');
      return;
    }

    setStatus('sending');
    setError(null);

    try {
      // 1. ASR
      const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
      const formData = new FormData();
      formData.append('audio', audioBlob, 'test.webm');

      const asrRes = await api.post('/voice/recognize', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const text = asrRes.data?.text || asrRes.data?.transcript;
      setAsrResult(text);

      if (!text) {
        setError('ASR не распознал текст');
        setStatus('error');
        return;
      }

      // 2. LLM reply
      const chatRes = await api.post('/chat/message', {
        text,
        channel: 'web',
        user_id: user?.id || 'test-user',
      });
      const reply = chatRes.data?.reply || chatRes.data?.text;
      setLlmReply(reply);

      // 3. TTS
      const ttsRes = await api.post(
        '/voice/speak',
        { text: reply },
        { responseType: 'blob' },
      );
      const url = URL.createObjectURL(ttsRes.data);
      setTtsAudioUrl(url);

      setStatus('done');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Ошибка обработки';
      setError(message);
      setStatus('error');
    }
  };

  const statusBadgeVariant = (): 'default' | 'destructive' | 'secondary' | 'outline' => {
    switch (status) {
      case 'error':
        return 'destructive';
      case 'done':
        return 'default';
      case 'sending':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card">
        <div className="max-w-4xl mx-auto px-4 py-6 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Mic className="size-6 text-muted-foreground" />
            <h1 className="text-3xl font-bold text-foreground">
              Тестирование голоса
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

      <main className="max-w-4xl mx-auto px-4 py-8 space-y-6">
        {/* Record Controls */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              {status === 'recording' ? (
                <Mic className="size-5 text-destructive animate-pulse" />
              ) : (
                <MicOff className="size-5 text-muted-foreground" />
              )}
              <CardTitle>Запись аудио</CardTitle>
            </div>
            <CardDescription>
              Запишите голосовое сообщение и обработайте через пайплайн ASR →
              LLM → TTS.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3 flex-wrap">
              <Button
                variant="destructive"
                onClick={handleStartRecord}
                disabled={status === 'recording' || status === 'sending'}
              >
                {status === 'recording' && (
                  <span className="size-2 rounded-full bg-current animate-pulse" />
                )}
                <Mic className="size-4" />
                {status === 'recording' ? 'Запись...' : 'Записать'}
              </Button>

              <Button
                variant="secondary"
                onClick={handleStopRecord}
                disabled={status !== 'recording'}
              >
                <Square className="size-4" />
                Стоп
              </Button>

              <Button
                onClick={handleProcess}
                disabled={status !== 'sending' || audioChunks.length === 0}
              >
                {status === 'sending' ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Play className="size-4" />
                )}
                Обработать (ASR → LLM → TTS)
              </Button>

              <Badge variant={statusBadgeVariant()}>
                {STATUS_LABELS[status]}
              </Badge>
            </div>
          </CardContent>
        </Card>

        {/* Results */}
        {(asrResult || llmReply || ttsAudioUrl || error) && (
          <Card>
            <CardHeader>
              <CardTitle>Результаты</CardTitle>
            </CardHeader>
            <CardContent>
              {error && (
                <Alert variant="destructive" className="mb-4">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <div className="space-y-4">
                {/* ASR Result */}
                <div className="border border-border rounded-lg p-4">
                  <h3 className="text-sm font-medium text-foreground mb-1">
                    ASR (распознанный текст)
                  </h3>
                  <p className="text-foreground">
                    {asrResult || (
                      <span className="text-muted-foreground italic">
                        Ожидание...
                      </span>
                    )}
                  </p>
                </div>

                {/* LLM Reply */}
                <div className="border border-border rounded-lg p-4">
                  <h3 className="text-sm font-medium text-foreground mb-1">
                    Ответ LLM
                  </h3>
                  <p className="text-foreground">
                    {llmReply || (
                      <span className="text-muted-foreground italic">
                        Ожидание...
                      </span>
                    )}
                  </p>
                </div>

                {/* TTS Audio */}
                {ttsAudioUrl && (
                  <div className="border border-border rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Volume2 className="size-4 text-muted-foreground" />
                      <h3 className="text-sm font-medium text-foreground">
                        TTS (озвучка)
                      </h3>
                    </div>
                    <audio controls src={ttsAudioUrl} className="w-full" />
                  </div>
                )}
              </div>

              {status === 'done' && (
                <div className="mt-4 text-center text-sm text-emerald-600">
                  Пайплайн завершён успешно: ASR → LLM → TTS
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
