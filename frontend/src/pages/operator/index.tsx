/**
 * Operator Dashboard
 * Admin panel for user and channel management
 */

import React from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { BarChart3, Users, MessageSquare, Activity } from 'lucide-react';

const OperatorDashboard: React.FC = () => {
  return (
    <div className="min-h-screen bg-muted/30">
      {/* Header */}
      <header className="bg-card shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold">
            Панель оператора
          </h1>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Navigation cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* Users card */}
          <Link to="/operator/users" className="block">
            <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
              <CardContent className="flex items-center gap-4">
                <div className="p-3 rounded-full bg-primary/10 text-primary">
                  <Users className="size-8" />
                </div>
                <div>
                  <CardTitle className="text-lg">
                    Пользователи
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">
                    Управление пользователями системы
                  </p>
                </div>
              </CardContent>
            </Card>
          </Link>

          {/* Channels card */}
          <Link to="/operator/channels" className="block">
            <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
              <CardContent className="flex items-center gap-4">
                <div className="p-3 rounded-full bg-primary/10 text-primary">
                  <MessageSquare className="size-8" />
                </div>
                <div>
                  <CardTitle className="text-lg">
                    Каналы
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">
                    Управление привязками каналов
                  </p>
                </div>
              </CardContent>
            </Card>
          </Link>

          {/* Sessions card */}
          <Link to="/operator/sessions" className="block">
            <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
              <CardContent className="flex items-center gap-4">
                <div className="p-3 rounded-full bg-primary/10 text-primary">
                  <Activity className="size-8" />
                </div>
                <div>
                  <CardTitle className="text-lg">
                    Сессии
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">
                    Просмотр активных сессий
                  </p>
                </div>
              </CardContent>
            </Card>
          </Link>

          {/* Audit card */}
          <Link to="/operator/audit" className="block">
            <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
              <CardContent className="flex items-center gap-4">
                <div className="p-3 rounded-full bg-primary/10 text-primary">
                  <BarChart3 className="size-8" />
                </div>
                <div>
                  <CardTitle className="text-lg">
                    Аудит
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">
                    Журнал действий (152-ФЗ)
                  </p>
                </div>
              </CardContent>
            </Card>
          </Link>
        </div>

        {/* Quick stats */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-2xl font-bold text-primary">0</div>
                  <div className="text-sm text-muted-foreground">Пользователей</div>
                </div>
                <Badge variant="secondary">
                  <Users className="mr-1 size-3" />
                  Статистика
                </Badge>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-2xl font-bold text-primary">0</div>
                  <div className="text-sm text-muted-foreground">Активных каналов</div>
                </div>
                <Badge variant="secondary">
                  <MessageSquare className="mr-1 size-3" />
                  Статистика
                </Badge>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-2xl font-bold text-primary">0</div>
                  <div className="text-sm text-muted-foreground">Активных сессий</div>
                </div>
                <Badge variant="secondary">
                  <Activity className="mr-1 size-3" />
                  Статистика
                </Badge>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-2xl font-bold text-primary">0</div>
                  <div className="text-sm text-muted-foreground">Записей аудита</div>
                </div>
                <Badge variant="secondary">
                  <BarChart3 className="mr-1 size-3" />
                  Статистика
                </Badge>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
};

export default OperatorDashboard;
