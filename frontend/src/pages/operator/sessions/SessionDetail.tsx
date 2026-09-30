import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '@/api/axios';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  ArrowLeft,
  MessageSquare,
  Clock,
  User,
  Loader2,
} from 'lucide-react';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
}

interface Fact {
  id: string;
  type: string;
  value: string;
  weight: number;
  channel: string;
  created_at: string;
}

interface SessionDetail {
  id: string;
  user_id: string;
  channel_type: string;
  started_at: string;
  ended_at: string | null;
  status: 'pending' | 'in_progress' | 'completed' | 'aborted';
  transcript: Message[];
  facts?: Fact[];
  context_json?: Record<string, unknown>;
}

const STATUS_VARIANT: Record<string, 'secondary' | 'default' | 'destructive' | 'outline'> = {
  pending: 'secondary',
  in_progress: 'outline',
  completed: 'default',
  aborted: 'destructive',
};

const STATUS_LABELS: Record<string, string> = {
  pending: 'Ожидает',
  in_progress: 'В процессе',
  completed: 'Завершена',
  aborted: 'Прервана',
};

export default function SessionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    fetchSessionDetail();
  }, [id]);

  const fetchSessionDetail = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/sessions/${id}`);
      setSession(response.data);
      setError(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Ошибка загрузки сессии';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="mr-2 size-5 animate-spin text-muted-foreground" />
        <span className="text-lg text-muted-foreground">Загрузка...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center space-y-4">
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
          <Button variant="ghost" render={<Link to="/sessions" />}>
            Вернуться к списку
          </Button>
        </div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <span className="text-lg text-muted-foreground">Сессия не найдена</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">Детали сессии</h1>
        <Button variant="ghost" render={<Link to="/sessions" />}>
          <ArrowLeft className="mr-2 size-4" />
          Назад к списку
        </Button>
      </div>

      {/* Информация о сессии */}
      <Card>
        <CardHeader>
          <CardTitle>Информация</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-muted-foreground">ID сессии</label>
              <p className="mt-1 text-sm text-foreground font-mono">{session.id}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-muted-foreground">Пользователь</label>
              <p className="mt-1 text-sm text-foreground flex items-center gap-2">
                <User className="size-4 text-muted-foreground" />
                {session.user_id}
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-muted-foreground">Канал</label>
              <p className="mt-1 text-sm text-foreground flex items-center gap-2">
                <MessageSquare className="size-4 text-muted-foreground" />
                {session.channel_type}
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-muted-foreground">Статус</label>
              <div className="mt-1">
                <Badge variant={STATUS_VARIANT[session.status] || 'secondary'}>
                  {STATUS_LABELS[session.status] || session.status}
                </Badge>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-muted-foreground">Дата начала</label>
              <p className="mt-1 text-sm text-foreground flex items-center gap-2">
                <Clock className="size-4 text-muted-foreground" />
                {new Date(session.started_at).toLocaleString('ru-RU')}
              </p>
            </div>
            {session.ended_at && (
              <div>
                <label className="block text-sm font-medium text-muted-foreground">Дата окончания</label>
                <p className="mt-1 text-sm text-foreground flex items-center gap-2">
                  <Clock className="size-4 text-muted-foreground" />
                  {new Date(session.ended_at).toLocaleString('ru-RU')}
                </p>
              </div>
            )}
            {session.context_json && (
              <div className="col-span-2">
                <label className="block text-sm font-medium text-muted-foreground">Контекст</label>
                <pre className="mt-1 text-sm text-foreground bg-muted p-2 rounded-lg overflow-auto max-h-40 font-mono">
                  {JSON.stringify(session.context_json, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Транскрипт сообщений */}
      <Card>
        <CardHeader>
          <CardTitle>История сообщений</CardTitle>
        </CardHeader>
        <CardContent>
          {session.transcript && session.transcript.length > 0 ? (
            <div className="space-y-4 max-h-96 overflow-y-auto">
              {session.transcript.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-3/4 rounded-lg px-4 py-2 ${
                      msg.role === 'user'
                        ? 'bg-primary/10 text-primary'
                        : msg.role === 'assistant'
                          ? 'bg-muted text-foreground'
                          : 'bg-muted/60 text-muted-foreground'
                    }`}
                  >
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    {msg.timestamp && (
                      <p className="text-xs text-muted-foreground mt-1">
                        {new Date(msg.timestamp).toLocaleString('ru-RU')}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Сообщений нет</p>
          )}
        </CardContent>
      </Card>

      {/* Факты */}
      {session.facts && session.facts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Извлечённые факты</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead>
                  <tr className="border-b">
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Тип
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Значение
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Вес
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Дата
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {session.facts.map((fact) => (
                    <tr key={fact.id} className="border-b last:border-0">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                        {fact.type}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                        {fact.value}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                        {fact.weight}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                        {new Date(fact.created_at).toLocaleString('ru-RU')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
