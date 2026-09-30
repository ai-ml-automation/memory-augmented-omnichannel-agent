import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAuthStore } from '../../store/auth.store';
import { api } from '../../api/axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { Brain, Search, Database, RefreshCw } from 'lucide-react';

interface Fact {
  id: string;
  type: string;
  value: string;
  weight: number;
  channel: string;
  created_at: string;
  expires_at: string | null;
  is_superseded: boolean;
}

const TYPE_COLORS: Record<string, string> = {
  intent: 'bg-primary/15 text-primary',
  preference: 'bg-emerald-100 text-emerald-800',
  complaint: 'bg-destructive/15 text-destructive',
  agreement: 'bg-violet-100 text-violet-800',
  rejection: 'bg-orange-100 text-orange-800',
  personal_info: 'bg-amber-100 text-amber-800',
};

const TYPE_LABELS: Record<string, string> = {
  intent: 'Намерение',
  preference: 'Предпочтение',
  complaint: 'Жалоба',
  agreement: 'Договорённость',
  rejection: 'Отказ',
  personal_info: 'Личная информация',
};

export function MemoryViewPage() {
  const { isAuthenticated } = useAuthStore();
  const navigate = useNavigate();
  const { userId: urlUserId } = useParams<{ userId: string }>();

  const [facts, setFacts] = useState<Fact[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState('');
  const [targetUserId, setTargetUserId] = useState(urlUserId || '');
  const [showGraph, setShowGraph] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const fetchFacts = useCallback(async () => {
    if (!targetUserId) return;
    setLoading(true);
    setError(null);
    setHasSearched(true);
    try {
      const params = new URLSearchParams();
      if (typeFilter) params.append('fact_type', typeFilter);
      const url = `/memory/users/${targetUserId}/facts?${params.toString()}`;
      const response = await api.get(url);
      setFacts(response.data || []);
    } catch {
      setError('Ошибка загрузки фактов памяти');
    } finally {
      setLoading(false);
    }
  }, [targetUserId, typeFilter]);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    if (urlUserId) {
      setTargetUserId(urlUserId);
    }
  }, [urlUserId, isAuthenticated, navigate]);

  useEffect(() => {
    if (urlUserId && urlUserId === targetUserId && isAuthenticated) {
      fetchFacts();
    }
  }, [urlUserId, targetUserId, isAuthenticated, fetchFacts]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchFacts();
  };

  const getTypeColor = (type: string) => {
    return TYPE_COLORS[type] || 'bg-muted text-muted-foreground';
  };

  const getTypeLabel = (type: string) => {
    return TYPE_LABELS[type] || type;
  };

  const renderGraph = () => (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle>Граф связей (заглушка)</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          Визуализация графа фактов будет реализована с использованием
          react-force-graph или vis.js.
        </p>
        <div className="mt-4 p-4 bg-muted/50 rounded-md">
          <pre className="text-xs text-foreground">
            {facts
              .slice(0, 10)
              .map((f) => `${f.type}: ${f.value}`)
              .join('\n')}
          </pre>
        </div>
      </CardContent>
    </Card>
  );

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="border-b bg-card">
        <div className="max-w-7xl mx-auto px-4 py-6 flex justify-between items-center">
          <h1 className="text-3xl font-bold text-foreground flex items-center gap-2">
            <Brain className="size-8" />
            Память клиента
          </h1>
          <Link
            to="/dashboard"
            className="inline-flex items-center justify-center rounded-lg border border-transparent px-2.5 py-1.5 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          >
            &larr; Назад
          </Link>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8 space-y-6">
        {/* Поиск пользователя */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Search className="size-4 text-muted-foreground" />
              Поиск фактов памяти
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={handleSearch}
              className="flex flex-wrap gap-4 items-end"
            >
              <div className="flex-1 min-w-[200px]">
                <label className="block text-sm font-medium text-muted-foreground">
                  ID пользователя
                </label>
                <Input
                  type="text"
                  value={targetUserId}
                  onChange={(e) => setTargetUserId(e.target.value)}
                  placeholder="Введите UUID пользователя"
                  className="mt-1"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-muted-foreground">
                  Тип факта
                </label>
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  className="mt-1 block h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 text-base transition-colors outline-none md:text-sm"
                >
                  <option value="">Все</option>
                  <option value="intent">Намерение</option>
                  <option value="preference">Предпочтение</option>
                  <option value="complaint">Жалоба</option>
                  <option value="agreement">Договорённость</option>
                  <option value="rejection">Отказ</option>
                  <option value="personal_info">Личная информация</option>
                </select>
              </div>
              <Button type="submit" disabled={!targetUserId.trim()}>
                <Database className="size-4" />
                Загрузить факты
              </Button>
            </form>
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
            {hasSearched && facts.length === 0 && !error && (
              <Card>
                <CardContent className="py-8 text-center text-muted-foreground">
                  Факты не найдены для данного пользователя.
                </CardContent>
              </Card>
            )}

            {facts.length > 0 && (
              <Card>
                <CardHeader className="border-b">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-muted-foreground">
                      Найдено фактов:{' '}
                      <strong className="text-foreground">{facts.length}</strong>
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowGraph(!showGraph)}
                    >
                      <RefreshCw className="size-4" />
                      {showGraph ? 'Показать списком' : 'Показать граф'}
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="p-0">
                  {showGraph ? (
                    renderGraph()
                  ) : (
                    <table className="min-w-full divide-y divide-border">
                      <thead className="bg-muted/50">
                        <tr>
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
                            Канал
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                            Дата
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                            Статус
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-card divide-y divide-border">
                        {facts.map((fact) => (
                          <tr key={fact.id}>
                            <td className="px-6 py-4 whitespace-nowrap text-sm">
                              <span
                                className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${getTypeColor(fact.type)}`}
                              >
                                {getTypeLabel(fact.type)}
                              </span>
                            </td>
                            <td
                              className="px-6 py-4 text-sm text-foreground max-w-xs truncate"
                              title={fact.value}
                            >
                              {fact.value}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                              {fact.weight.toFixed(2)}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                              {fact.channel}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                              {new Date(fact.created_at).toLocaleDateString(
                                'ru-RU'
                              )}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm">
                              {fact.is_superseded ? (
                                <span className="text-muted-foreground/70">
                                  Заменён
                                </span>
                              ) : fact.expires_at &&
                                new Date(fact.expires_at) < new Date() ? (
                                <span className="text-destructive">
                                  Истёк
                                </span>
                              ) : (
                                <span className="text-emerald-600">
                                  Активен
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </CardContent>
              </Card>
            )}
          </>
        )}
      </main>
    </div>
  );
}
