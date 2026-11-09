import fs from 'node:fs';
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {selectComposition, renderMedia} from '@remotion/renderer';

const root = path.resolve(import.meta.dirname, '..');
const index = process.argv.indexOf('--output');
if (index >= 0 && !process.argv[index + 1]) throw new Error('--output requires a path');
const output = path.resolve(index >= 0 ? process.argv[index + 1] : path.join(root, '../output/final.mp4'));
fs.mkdirSync(path.dirname(output), {recursive: true});
const serveUrl = await bundle({entryPoint: path.join(root, 'src/index.tsx'), publicDir: path.join(root, 'public')});
const browserExecutable = process.env.CHROME_PATH || undefined;
const composition = await selectComposition({serveUrl, id: 'Film', browserExecutable});
await renderMedia({serveUrl, composition, browserExecutable, outputLocation: output, codec: 'h264', audioCodec: 'aac', pixelFormat: 'yuv420p', crf: 18, concurrency: 2});
