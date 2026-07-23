import { spawn } from 'node:child_process';
import process from 'node:process';
import { createServer } from 'vite';

const server = await createServer({
  appType: 'spa',
  logLevel: 'warn',
  server: {
    host: '127.0.0.1',
    port: 4173,
    strictPort: true,
  },
});

let exitCode = 1;

try {
  await server.listen();
  exitCode = await new Promise((resolve, reject) => {
    const child = spawn(
      process.execPath,
      ['./node_modules/playwright/cli.js', 'test', ...process.argv.slice(2)],
      {
        cwd: process.cwd(),
        env: process.env,
        stdio: 'inherit',
      },
    );
    child.once('error', reject);
    child.once('exit', (code) => resolve(code ?? 1));
  });
} finally {
  await server.close();
}

process.exitCode = exitCode;
