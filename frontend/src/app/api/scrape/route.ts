import { NextRequest, NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';

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
    const { startDate, endDate, jraOnly = true, forceOverwrite = false, stream = false } = body;

    if (!startDate || !endDate) {
      return NextResponse.json(
        { error: 'Missing dates', message: '開始日と終了日を指定してください' },
        { status: 400 }
      );
    }

    // スクリプトのパスを取得
    const scriptPath = path.join(process.cwd(), '..', 'scripts', 'scrape_local.py');

    // オプションフラグ
    const args = ['--start', startDate, '--end', endDate, '--progress'];
    if (!jraOnly) args.push('--include-local');
    if (forceOverwrite) args.push('--force');

    console.log('Executing:', `python3 ${scriptPath} ${args.join(' ')}`);

    if (stream) {
      // SSEストリーミングモード
      const encoder = new TextEncoder();
      const cwd = path.join(process.cwd(), '..');
      const readableStream = new ReadableStream({
        start(controller) {
          const childProcess = spawn('python3', [scriptPath, ...args], {
            cwd,
          });

          let buffer = '';

          childProcess.stdout.on('data', (data: Buffer) => {
            buffer += data.toString();
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
              if (line.trim()) {
                // JSON形式の進捗データをパース
                if (line.startsWith('PROGRESS:')) {
                  try {
                    const progressData = JSON.parse(line.substring(9));
                    controller.enqueue(encoder.encode(`data: ${JSON.stringify(progressData)}\n\n`));
                  } catch {
                    // パースエラーは無視
                  }
                }
              }
            }
          });

          childProcess.stderr.on('data', (data: Buffer) => {
            const text = data.toString();
            if (!text.includes('pip') && !text.includes('WARNING')) {
              console.error('Scrape stderr:', text);
            }
          });

          childProcess.on('close', (code) => {
            controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'complete', exitCode: code })}\n\n`));
            controller.close();
          });

          childProcess.on('error', (err) => {
            controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'error', message: err.message })}\n\n`));
            controller.close();
          });
        },
      });

      return new Response(readableStream, {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      });
    } else {
      // 同期モード（従来の動作）
      const { exec } = await import('child_process');
      const { promisify } = await import('util');
      const execAsync = promisify(exec);

      const forceFlag = forceOverwrite ? ' --force' : '';
      const jraFlag = jraOnly ? '' : ' --include-local';
      const command = `python3 "${scriptPath}" --start ${startDate} --end ${endDate}${jraFlag}${forceFlag}`;

      const { stdout, stderr } = await execAsync(command, {
        timeout: 600000,
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
    }
  } catch (error) {
    console.error('Scrape error:', error);

    const message = error instanceof Error ? error.message : '不明なエラー';

    return NextResponse.json(
      { error: 'Scraping failed', message },
      { status: 500 }
    );
  }
}
