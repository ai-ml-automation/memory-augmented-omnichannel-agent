import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/auth.store';
import { api } from '@/api/axios';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import {
  MessageSquare,
  Search,
  Filter,
  Calendar,
  ChevronRight,
} from 'lucide-react';

interface Session {
  id: string;
  user_id: string;
  channel_type: string;
  status: string;
  started_at: string;
  ended_at: string | null;
}

interface PageInfo {
  page: number;
  size: number;
  total: number;
  pages: number;
}

const CHANNEL_ICONS: Record<string, string> = {
  MAX: '💬',
  TG: '✈️',
  VK: '👤',
  VOICE: '🎤',
};

const STATUS_VARIANT: Record<string, 'secondary' | 'default' | 'destructive' | 'outline'> = {
  pending: 'secondary',
  in_progress: 'outline',
  completed: 'default',
  aborted: 'destructive',
};

const STATUS_LABELS: Record<string, string> = {
  pending: 'Ожидание',
  in_progress: 'В процессе',
  completed: 'Завершена',
  aborted: 'Прервана',
};

export function SessionsListPage() {
  const { isAuthenticated } = useAuthStore();
  const navigate = useNavigate();

  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const size = 20;
  const [pageInfo, setPageInfo] = useState<PageInfo | null>(null);

  const [channelFilter, setChannelFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.append('page', String(page));
      params.append('size', String(size));
      if (channelFilter) params.append('channel', channelFilter);
      if (statusFilter) params.append('status', statusFilter);
      if (dateFrom) params.append('date_from', dateFrom);
      if (dateTo) params.append('date_to', dateTo);

      const response = await api.get(`/sessions?${params.toString()}`);
      setSessions(response.data.items || []);
      setPageInfo({
        page: response.data.page || page,
        size: response.data.size || size,
        total: response.data.total || 0,
        pages: response.data.pages || 0,
      });
    } catch {
      setError('Ошибка загрузки сессий');
    } finally {
      setLoading(false);
    }
  }, [page, channelFilter, statusFilter, dateFrom, dateTo]);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    fetchSessions();
  }, [fetchSessions, isAuthenticated, navigate]);

  const handlePageChange = (newPage: number) => {
    if (newPage < 1 || (pageInfo && newPage > pageInfo.pages)) return;
    setPage(newPage);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-foreground">Сессии</h1>
        <Button variant="ghost" render={<Link to="/dashboard" />}>
          ← Назад
        </Button>
      </div>

      {/* Фильтры */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="size-4 text-muted-foreground" />
            Фильтры
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-muted-foreground mb-1">Канал</label>
              <select
                value={channelFilter}
                onChange={(e) => setChannelFilter(e.target.value)}
                className="flex h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-base md:text-sm focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 outline-none"
              >
                <option value="">Все</option>
                <option value="MAX">MAX</option>
                <option value="TG">Telegram</option>
                <option value="VK">VK</option>
                <option value="VOICE">Голос</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-muted-foreground mb-1">Статус</label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="flex h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-base md:text-sm focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 outline-none"
              >
                <option value="">Все</option>
                <option value="pending">Ожидание</option>
                <option value="in_progress">В процессе</option>
                <option value="completed">Завершена</option>
                <option value="aborted">Прервана</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-muted-foreground mb-1">Дата от</label>
              <div className="relative">
                <Calendar className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                <Input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="pl-8"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-muted-foreground mb-1">Дата до</label>
              <div className="relative">
                <Calendar className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                <Input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  className="pl-8"
                />
              </div>
            </div>
          </div>
          <div className="mt-4 flex justify-end">
            <Button
              onClick={() => {
                setPage(1);
                fetchSessions();
              }}
            >
              <Search className="mr-2 size-4" />
              Применить фильтры
            </Button>
          </div>
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <div className="space-y-6">
          <Skeleton className="h-8 w-[200px]" />
          <Skeleton className="h-[120px] w-full" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Skeleton className="h-[200px]" />
            <Skeleton className="h-[200px]" />
          </div>
          <Skeleton className="h-[300px] w-full" />
        </div>
      ) : (
        <>
          <Card>
            <CardContent className="p-0">
              <table className="min-w-full">
                <thead>
                  <tr className="border-b">
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Канал
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      ID
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Начало
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Статус
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Действия
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-4 text-center text-muted-foreground">
                        Нет сессий
                      </td>
                    </tr>
                  ) : (
                    sessions.map((session) => (
                      <tr key={session.id} className="border-b last:border-0">
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                          <span className="mr-2">{CHANNEL_ICONS[session.channel_type] || '📱'}</span>
                          {session.channel_type}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground font-mono">
                          {session.id.slice(0, 8)}...
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                          {new Date(session.started_at).toLocaleString('ru-RU')}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <Badge variant={STATUS_VARIANT[session.status] || 'secondary'}>
                            <MessageSquare className="size-3" />
                            {STATUS_LABELS[session.status] || session.status}
                          </Badge>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <Button
                            variant="ghost"
                            size="sm"
                            render={<Link to={`/operator/sessions/${session.id}`} />}
                          >
                            <ChevronRight className="size-4" />
                            Просмотр
                          </Button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </CardContent>
          </Card>

          {pageInfo && pageInfo.pages > 1 && (
            <div className="flex justify-between items-center">
              <p className="text-sm text-muted-foreground">
                Показано {sessions.length} из {pageInfo.total} записей
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(page - 1)}
                  disabled={page <= 1}
                >
                  Назад
                </Button>
                <span className="text-sm text-muted-foreground">
                  Стр. {page} из {pageInfo.pages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePageChange(page + 1)}
                  disabled={page >= pageInfo.pages}
                >
                  Вперёд
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
