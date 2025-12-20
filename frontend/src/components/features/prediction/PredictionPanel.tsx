'use client';

import { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { cn } from '@/lib/utils';
import { CONFIDENCE_COLORS } from '@/lib/constants';
import { createPrediction, getPrediction } from '@/lib/api';
import type { Prediction, PredictionHorse, RecommendedBet } from '@/types/prediction';

interface PredictionPanelProps {
  raceId: string;
  initialPrediction?: Prediction | null;
}

export function PredictionPanel({ raceId, initialPrediction }: PredictionPanelProps) {
  const [prediction, setPrediction] = useState<Prediction | null>(initialPrediction || null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePredict = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await createPrediction(raceId);
      setPrediction(result);
    } catch (err) {
      setError('予測の作成に失敗しました');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  if (!prediction) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>AI予測</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-6">
            <p className="text-gray-500 mb-4">
              AIによる予測を作成できます
            </p>
            <Button onClick={handlePredict} isLoading={isLoading}>
              予測を作成
            </Button>
            {error && (
              <p className="text-red-500 text-sm mt-2">{error}</p>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }

  const { results } = prediction;
  const top5 = results.predictions.slice(0, 5);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>AI予測</CardTitle>
          <Badge variant={results.model_type === 'ml' ? 'success' : 'default'}>
            {results.model_type === 'ml' ? 'MLモデル' : 'ベースライン'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-6">
          {/* Top 5 Predictions */}
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-3">予測順位</h4>
            <div className="space-y-2">
              {top5.map((horse, index) => (
                <PredictionRow key={horse.horse_number} horse={horse} rank={index + 1} />
              ))}
            </div>
          </div>

          {/* Recommended Bets */}
          {results.recommended_bets.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-3">おすすめ馬券</h4>
              <div className="space-y-2">
                {results.recommended_bets.map((bet, index) => (
                  <BetRecommendation key={index} bet={bet} />
                ))}
              </div>
            </div>
          )}

          {/* Re-predict button */}
          <div className="pt-4 border-t">
            <Button
              variant="outline"
              size="sm"
              onClick={handlePredict}
              isLoading={isLoading}
            >
              再予測
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function PredictionRow({ horse, rank }: { horse: PredictionHorse; rank: number }) {
  const rankColors = {
    1: 'bg-yellow-100 text-yellow-800',
    2: 'bg-gray-100 text-gray-800',
    3: 'bg-orange-100 text-orange-800',
  };

  return (
    <div className="flex items-center gap-3 p-2 rounded-lg bg-gray-50">
      <span
        className={cn(
          'w-6 h-6 flex items-center justify-center rounded-full text-sm font-bold',
          rankColors[rank as keyof typeof rankColors] || 'bg-gray-50 text-gray-600'
        )}
      >
        {rank}
      </span>
      <span className="font-medium">
        {horse.horse_number}番 {horse.horse_name || ''}
      </span>
      <span className="text-sm text-gray-500 ml-auto">
        {(horse.probability * 100).toFixed(1)}%
      </span>
    </div>
  );
}

function BetRecommendation({ bet }: { bet: RecommendedBet }) {
  return (
    <div className="flex items-center gap-3 p-2 rounded-lg border">
      <span className="font-medium text-sm">{bet.bet_type}</span>
      <span className="text-gray-600">{bet.detail}</span>
      <Badge
        className={cn('ml-auto', CONFIDENCE_COLORS[bet.confidence])}
      >
        {bet.confidence === 'high' ? '高' : bet.confidence === 'medium' ? '中' : '低'}
      </Badge>
    </div>
  );
}
