/**
 * Analytics Dashboard
 * Displays analytics and reporting data with interactive Recharts visualizations
 */

import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  AreaChart,
  Area,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { BarChart3, TrendingUp, Clock, Users, Loader2 } from 'lucide-react';

interface DashboardStats {
  users: number;
  active_sessions: number;
  total_facts: number;
  active_consents: number;
  audit_today: number;
}

interface TimelineEntry {
  date: string;
  count: number;
}

interface HourlyEntry {
  hour: number;
  count: number;
}

const CHANNEL_DATA = [
  { channel: 'MAX', messages: 1240 },
  { channel: 'Telegram', messages: 980 },
  { channel: 'VK', messages: 650 },
  { channel: 'Voice', messages: 320 },
];

function readChartColor(): string {
  if (typeof document === 'undefined') return 'hsl(217, 91%, 60%)';
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue('--primary')
    .trim();
  if (!raw) return 'hsl(217, 91%, 60%)';
  if (raw.startsWith('hsl')) return raw;
  return `hsl(${raw})`;
}

const AnalyticsDashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [peakHours, setPeakHours] = useState<HourlyEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [barFill, setBarFill] = useState('hsl(217, 91%, 60%)');

  useEffect(() => {
    fetchAnalytics();
  }, []);

  useEffect(() => {
    setBarFill(readChartColor());
  }, []);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      const [statsRes, timelineRes, hoursRes] = await Promise.all([
        axios.get('/analytics/dashboard'),
        axios.get('/analytics/audit/timeline?days=7'),
        axios.get('/analytics/audit/peak-hours'),
      ]);

      setStats(statsRes.data);
      setTimeline(timelineRes.data);
      setPeakHours(hoursRes.data);
      setError(null);
    } catch (err) {
      setError('Ошибка загрузки аналитики');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-muted/30 flex items-center justify-center">
        <Loader2 className="size-8 text-primary animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-muted/30">
      {/* Header */}
      <header className="bg-card shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-6 flex justify-between items-center">
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <BarChart3 className="size-8" />
            Аналитика
          </h1>
          <Link
            to="/operator"
            className="text-primary underline-offset-4 hover:underline font-medium text-sm"
          >
            &larr; Назад
          </Link>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Stats cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-2xl font-bold text-primary">
                      {stats.users}
                    </div>
                    <div className="text-sm text-muted-foreground">Пользователей</div>
                  </div>
                  <Badge variant="secondary">
                    <Users className="mr-1 size-3" />
                  </Badge>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-2xl font-bold text-primary">
                      {stats.active_sessions}
                    </div>
                    <div className="text-sm text-muted-foreground">Активных сессий</div>
                  </div>
                  <Badge variant="secondary">
                    <TrendingUp className="mr-1 size-3" />
                  </Badge>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-2xl font-bold text-primary">
                      {stats.total_facts}
                    </div>
                    <div className="text-sm text-muted-foreground">Фактов в памяти</div>
                  </div>
                  <Badge variant="secondary">
                    <BarChart3 className="mr-1 size-3" />
                  </Badge>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-2xl font-bold text-primary">
                      {stats.active_consents}
                    </div>
                    <div className="text-sm text-muted-foreground">Согласий</div>
                  </div>
                  <Badge variant="secondary">
                    <Clock className="mr-1 size-3" />
                  </Badge>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-2xl font-bold text-primary">
                      {stats.audit_today}
                    </div>
                    <div className="text-sm text-muted-foreground">Аудит сегодня</div>
                  </div>
                  <Badge variant="secondary">
                    <BarChart3 className="mr-1 size-3" />
                  </Badge>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Messages by Channel — Recharts BarChart */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="size-5" />
                Сообщения по каналам
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={CHANNEL_DATA}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="channel" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar
                    dataKey="messages"
                    name="Сообщений"
                    fill={barFill}
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Timeline chart — Recharts AreaChart */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="size-5" />
                Активность за 7 дней
              </CardTitle>
            </CardHeader>
            <CardContent>
              {timeline.length === 0 ? (
                <div className="flex items-center justify-center h-[250px] text-muted-foreground">
                  Нет данных
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={250}>
                  <AreaChart
                    data={timeline.map((e) => ({
                      ...e,
                      date: new Date(e.date).toLocaleDateString('ru-RU', {
                        day: '2-digit',
                        month: '2-digit',
                      }),
                    }))}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Area
                      type="monotone"
                      dataKey="count"
                      name="Событий"
                      stroke={barFill}
                      fill={barFill}
                      fillOpacity={0.2}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          {/* Peak hours — Recharts BarChart */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="size-5" />
                Часы пиковой активности
              </CardTitle>
            </CardHeader>
            <CardContent>
              {peakHours.length === 0 ? (
                <div className="flex items-center justify-center h-[250px] text-muted-foreground">
                  Нет данных
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart
                    data={Array.from({ length: 24 }, (_, i) => {
                      const entry = peakHours.find((h) => h.hour === i);
                      return { hour: `${i}:00`, count: entry?.count ?? 0 };
                    })}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="hour" tick={{ fontSize: 11 }} interval={3} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Bar
                      dataKey="count"
                      name="Запросов"
                      fill={barFill}
                      radius={[3, 3, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          {/* Summary card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="size-5" />
                Сводка
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Всего каналов</span>
                  <span className="font-semibold">{CHANNEL_DATA.length}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Сообщений (все каналы)</span>
                  <span className="font-semibold">
                    {CHANNEL_DATA.reduce((sum, c) => sum + c.messages, 0).toLocaleString('ru-RU')}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Пиковый час</span>
                  <span className="font-semibold">
                    {peakHours.length > 0
                      ? `${peakHours.reduce((max, e) => (e.count > max.count ? e : max), peakHours[0]).hour}:00`
                      : '—'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Средняя активность / день</span>
                  <span className="font-semibold">
                    {timeline.length > 0
                      ? Math.round(timeline.reduce((s, e) => s + e.count, 0) / timeline.length)
                      : '—'}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
};

export default AnalyticsDashboard;
