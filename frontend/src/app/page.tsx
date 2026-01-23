'use client';

import Link from 'next/link';
import { MapPin, Mountain, Snowflake } from 'lucide-react';

const raceTypes = [
  {
    id: 'central',
    name: '中央競馬',
    description: 'JRA主催の中央競馬予想',
    icon: MapPin,
    href: '/central',
    color: 'bg-blue-500 hover:bg-blue-600',
    iconBg: 'bg-blue-100',
    iconColor: 'text-blue-600',
  },
  {
    id: 'local',
    name: '地方競馬',
    description: 'NAR主催の地方競馬予想',
    icon: Mountain,
    href: '/local',
    color: 'bg-green-500 hover:bg-green-600',
    iconBg: 'bg-green-100',
    iconColor: 'text-green-600',
    disabled: false,
  },
  {
    id: 'banei',
    name: 'ばんえい競馬',
    description: '帯広のばんえい競馬予想',
    icon: Snowflake,
    href: '/banei',
    color: 'bg-purple-500 hover:bg-purple-600',
    iconBg: 'bg-purple-100',
    iconColor: 'text-purple-600',
    disabled: false,
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex flex-col items-center justify-center p-4">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">競馬予想AI</h1>
        <p className="text-lg text-gray-600">
          機械学習を活用した競馬予想アプリケーション
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-3 w-full max-w-4xl">
        {raceTypes.map((type) => (
          <Link
            key={type.id}
            href={type.disabled ? '#' : type.href}
            className={`relative block p-6 bg-white rounded-xl shadow-lg transition-all duration-200 ${
              type.disabled
                ? 'opacity-50 cursor-not-allowed'
                : 'hover:shadow-xl hover:-translate-y-1'
            }`}
            onClick={(e) => type.disabled && e.preventDefault()}
          >
            {type.disabled && (
              <span className="absolute top-3 right-3 px-2 py-1 text-xs font-medium bg-gray-200 text-gray-600 rounded">
                準備中
              </span>
            )}
            <div className={`w-14 h-14 ${type.iconBg} rounded-xl flex items-center justify-center mb-4`}>
              <type.icon className={`w-7 h-7 ${type.iconColor}`} />
            </div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              {type.name}
            </h2>
            <p className="text-sm text-gray-500">{type.description}</p>
          </Link>
        ))}
      </div>

      <p className="mt-12 text-sm text-gray-400">
        予想は参考情報です。馬券購入は自己責任でお願いします。
      </p>
    </div>
  );
}
