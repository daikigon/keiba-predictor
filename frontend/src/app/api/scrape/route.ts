import { NextRequest, NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execAsync = promisify(exec);

// 環境チェック
function isLocalEnvironment(): boolean {
  return !process.env.VERCEL && !process.env.NEXT_PUBLIC_VERCEL_ENV;
}

export async function POST(request: NextRequest) {
  // クラウド環境では実行不可
  if (!isLocalEnvironment()) {
    return NextResponse.json(
      { error: 'Scraping is only available in local environment', message: 'クラウド環境ではスクレイピングを実行できません' },
      { status: 403 }
    );
  }

  try {
    const body = await request.json();
    const { startDate, endDate } = body;

    if (!startDate || !endDate) {
      return NextResponse.json(
        { error: 'Missing dates', message: '開始日と終了日を指定してください' },
        { status: 400 }
      );
    }

    // スクリプトのパスを取得
    const scriptPath = path.join(process.cwd(), '..', 'scripts', 'scrape_local.py');

    // Python スクリプトを実行
    const command = `python3 "${scriptPath}" --start ${startDate} --end ${endDate}`;

    console.log('Executing:', command);

    const { stdout, stderr } = await execAsync(command, {
      timeout: 600000, // 10分タイムアウト
      cwd: path.join(process.cwd(), '..'),
    });

    if (stderr && !stderr.includes('pip') && !stderr.includes('WARNING')) {
      console.error('Scrape stderr:', stderr);
    }

    // 結果をパース
    const successMatch = stdout.match(/完了: (\d+)\/(\d+)件/);
    const success = successMatch ? parseInt(successMatch[1]) : 0;
    const total = successMatch ? parseInt(successMatch[2]) : 0;

    return NextResponse.json({
      status: 'success',
      success,
      total,
      output: stdout,
    });
  } catch (error) {
    console.error('Scrape error:', error);

    const message = error instanceof Error ? error.message : '不明なエラー';

    return NextResponse.json(
      { error: 'Scraping failed', message },
      { status: 500 }
    );
  }
}
