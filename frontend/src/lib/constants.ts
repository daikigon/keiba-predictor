export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const COURSE_COLORS: Record<string, string> = {
  '東京': 'bg-blue-100 text-blue-800',
  '中山': 'bg-green-100 text-green-800',
  '阪神': 'bg-red-100 text-red-800',
  '京都': 'bg-purple-100 text-purple-800',
  '中京': 'bg-orange-100 text-orange-800',
  '小倉': 'bg-pink-100 text-pink-800',
  '新潟': 'bg-cyan-100 text-cyan-800',
  '福島': 'bg-teal-100 text-teal-800',
  '札幌': 'bg-indigo-100 text-indigo-800',
  '函館': 'bg-sky-100 text-sky-800',
};

export const GRADE_COLORS: Record<string, string> = {
  'G1': 'bg-yellow-400 text-yellow-900 font-bold',
  'G2': 'bg-pink-400 text-pink-900 font-bold',
  'G3': 'bg-green-400 text-green-900 font-bold',
  'L': 'bg-purple-200 text-purple-800',
  'オープン': 'bg-gray-200 text-gray-800',
  '3勝': 'bg-gray-100 text-gray-700',
  '2勝': 'bg-gray-100 text-gray-700',
  '1勝': 'bg-gray-100 text-gray-700',
  '新馬': 'bg-blue-200 text-blue-800',
  '未勝利': 'bg-gray-50 text-gray-600',
};

export const TRACK_TYPE_LABELS: Record<string, string> = {
  '芝': '芝',
  'ダート': 'ダ',
};

export const CONFIDENCE_COLORS: Record<string, string> = {
  'high': 'bg-green-100 text-green-800',
  'medium': 'bg-yellow-100 text-yellow-800',
  'low': 'bg-gray-100 text-gray-600',
};
