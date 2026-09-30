import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/auth.store';
import { api } from '../../api/axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import {
  FileText,
  Search,
  Filter,
  User,
  Calendar,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

interface AuditLogEntry {
  id: string;
  user_id: string;
  action: string;
  fact_id: string | null;
  timestamp: string;
  source: string;
  ip_address: string | null;
}

interface PageInfo {
  page: number;
  size: number;
  total: number;
  pages: number;
}

const ACTION_BADGES: Record<string, string> = {
  READ: 'bg-blue-100 text-blue-800',
  WRITE: 'bg-emerald-100 text-emerald-800',
  DELETE: 'bg-red-100 text-red-800',
};

const ACTION_LABELS: Record<string, string> = {
  READ: 'Чтение',
  WRITE: 'Запись',
  DELETE: 'Удаление',
};

const SOURCE_BADGES: Record<string, string> = {
  AI: 'bg-purple-100 text-purple-800',
  OPERATOR: 'bg-orange-100 text-orange-800',
};

export function AuditLogPage() {
  const { isAuthenticated } = useAuthStore();
  const navigate = useNavigate();

  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const size = 20;
  const [pageInfo, setPageInfo] = useState<PageInfo | null>(null);

  const [userIdFilter, setUserIdFilter] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.append('page', String(page));
      params.append('size', String(size));
      if (userIdFilter) params.append('user_id', userIdFilter);
      if (actionFilter) params.append('action', actionFilter);
      if (sourceFilter) params.append('source', sourceFilter);
      if (dateFrom) params.append('date_from', dateFrom);
      if (dateTo) params.append('date_to', dateTo);

      const response = await api.get(`/audit/logs?${params.toString()}`);
      setLogs(response.data.items || []);
      setPageInfo({
        page: response.data.page || page,
        size: response.data.size || size,
        total: response.data.total || 0,
        pages: response.data.pages || 0,
      });
    } catch {
      setError('Ошибка загрузки журнала аудита');
    } finally {
      setLoading(false);
    }
  }, [page, userIdFilter, actionFilter, sourceFilter, dateFrom, dateTo]);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    fetchLogs();
  }, [fetchLogs, isAuthenticated, navigate]);

  const handlePageChange = (newPage: number) => {
    if (newPage < 1 || (pageInfo && newPage > pageInfo.pages)) return;
    setPage(newPage);
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card">
        <div className="max-w-7xl mx-auto px-4 py-6 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <FileText className="size-6 text-muted-foreground" />
            <h1 className="text-3xl font-bold text-foreground">
              Журнал аудита (152-ФЗ)
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
        {/* Фильтры */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Filter className="size-5 text-muted-foreground" />
              <CardTitle>Фильтры</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              <div>
                <label className="flex items-center gap-1.5 text-sm font-medium text-foreground mb-1">
                  <User className="size-3.5 text-muted-foreground" />
                  User ID
                </label>
                <Input
                  type="text"
                  value={userIdFilter}
                  onChange={(e) => setUserIdFilter(e.target.value)}
                  placeholder="UUID пользователя"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-foreground mb-1 block">
                  Действие
                </label>
                <select
                  value={actionFilter}
                  onChange={(e) => setActionFilter(e.target.value)}
                  className="h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 text-base transition-colors outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 md:text-sm cursor-pointer"
                >
                  <option value="">Все</option>
                  <option value="READ">Чтение</option>
                  <option value="WRITE">Запись</option>
                  <option value="DELETE">Удаление</option>
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-foreground mb-1 block">
                  Источник
                </label>
                <select
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value)}
                  className="h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 text-base transition-colors outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 md:text-sm cursor-pointer"
                >
                  <option value="">Все</option>
                  <option value="AI">AI</option>
                  <option value="OPERATOR">Оператор</option>
                </select>
              </div>
              <div>
                <label className="flex items-center gap-1.5 text-sm font-medium text-foreground mb-1">
                  <Calendar className="size-3.5 text-muted-foreground" />
                  Дата от
                </label>
                <Input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                />
              </div>
              <div>
                <label className="flex items-center gap-1.5 text-sm font-medium text-foreground mb-1">
                  <Calendar className="size-3.5 text-muted-foreground" />
                  Дата до
                </label>
                <Input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                />
              </div>
            </div>
            <div className="mt-4 flex justify-end">
              <Button
                onClick={() => {
                  setPage(1);
                  fetchLogs();
                }}
              >
                <Search className="size-4" />
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
            <Skeleton className="h-8 w-[250px]" />
            <Skeleton className="h-[120px] w-full" />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Skeleton className="h-[200px]" />
              <Skeleton className="h-[200px]" />
            </div>
            <Skeleton className="h-[350px] w-full" />
          </div>
        ) : (
          <>
            <Card>
              <div className="px-6 py-3 bg-muted/50 border-b border-border">
                <span className="text-sm text-muted-foreground">
                  Записей:{' '}
                  <strong className="text-foreground">
                    {pageInfo?.total || 0}
                  </strong>
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-border">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                        Время
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                        Действие
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                        User ID
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                        Источник
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                        Fact ID
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                        IP
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-card divide-y divide-border">
                    {logs.length === 0 ? (
                      <tr>
                        <td
                          colSpan={6}
                          className="px-6 py-4 text-center text-muted-foreground"
                        >
                          Нет записей аудита
                        </td>
                      </tr>
                    ) : (
                      logs.map((log) => (
                        <tr key={log.id}>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                            {new Date(log.timestamp).toLocaleString('ru-RU')}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm">
                            <Badge
                              className={ACTION_BADGES[log.action] ?? ''}
                            >
                              {ACTION_LABELS[log.action] || log.action}
                            </Badge>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground font-mono">
                            {log.user_id.slice(0, 8)}...
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm">
                            <Badge
                              className={SOURCE_BADGES[log.source] ?? ''}
                            >
                              {log.source}
                            </Badge>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground font-mono">
                            {log.fact_id
                              ? log.fact_id.slice(0, 8) + '...'
                              : '—'}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                            {log.ip_address || '—'}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </Card>

            {pageInfo && pageInfo.pages > 1 && (
              <div className="flex justify-between items-center">
                <div className="text-sm text-muted-foreground">
                  Показано {logs.length} из {pageInfo.total} записей
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handlePageChange(page - 1)}
                    disabled={page <= 1}
                  >
                    <ChevronLeft className="size-4" />
                    Назад
                  </Button>
                  <span className="text-sm text-muted-foreground px-2">
                    Страница {page} из {pageInfo.pages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handlePageChange(page + 1)}
                    disabled={page >= pageInfo.pages}
                  >
                    Вперёд
                    <ChevronRight className="size-4" />
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
