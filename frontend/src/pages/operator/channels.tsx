/**
 * Channels Management Page
 * Admin interface for managing channel bindings
 */

import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Radio, Globe, MessageCircle, Phone, Loader2 } from 'lucide-react';

interface ChannelBinding {
  id: string;
  user_id: string;
  channel_type: string;
  external_id: string;
  is_active: boolean;
}

const ChannelsPage: React.FC = () => {
  const [bindings, setBindings] = useState<ChannelBinding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchBindings();
  }, []);

  const fetchBindings = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/admin/channels/');
      setBindings(response.data);
      setError(null);
    } catch (err) {
      setError('Ошибка загрузки каналов');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleUnbind = async (bindingId: string) => {
    if (!window.confirm('Отвязать канал?')) {
      return;
    }

    try {
      await axios.delete(`/admin/channels/${bindingId}`);
      setBindings(bindings.filter((b) => b.id !== bindingId));
    } catch (err) {
      alert('Ошибка отвязки');
    }
  };

  const getChannelIcon = (type: string) => {
    switch (type) {
      case 'MAX':
        return <MessageCircle className="size-4" />;
      case 'TG':
        return <Globe className="size-4" />;
      case 'VK':
        return <Globe className="size-4" />;
      case 'VOICE':
        return <Phone className="size-4" />;
      default:
        return <Radio className="size-4" />;
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
            <Radio className="size-8" />
            Каналы
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

        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Канал
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      User ID
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      External ID
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Статус
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      Действия
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-card divide-y divide-border">
                  {bindings.length === 0 ? (
                    <tr>
                      <td
                        colSpan={5}
                        className="px-6 py-4 text-center text-muted-foreground"
                      >
                        Нет привязок каналов
                      </td>
                    </tr>
                  ) : (
                    bindings.map((binding) => (
                      <tr key={binding.id}>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <span className="flex items-center gap-2">
                            {getChannelIcon(binding.channel_type)}
                            {binding.channel_type}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                          {binding.user_id.slice(0, 8)}...
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          {binding.external_id}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <Badge variant={binding.is_active ? 'secondary' : 'outline'}>
                            {binding.is_active ? 'Активен' : 'Неактивен'}
                          </Badge>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => handleUnbind(binding.id)}
                          >
                            Отвязать
                          </Button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default ChannelsPage;
