const fs = require('fs');
const path = require('path');
const glob = require('glob');
const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const chalk = require('chalk');

const ROOT = process.cwd();
const patterns = [
  'pages/**/*.{js,jsx,ts,tsx}',
  'components/**/*.{js,jsx,ts,tsx}',
];

const files = patterns
  .map((p) => glob.sync(p, { cwd: ROOT, absolute: true }))
  .flat();

const problems = [];

function report(file, message, loc) {
  const rel = path.relative(ROOT, file);
  const locStr = loc ? ` (line ${loc.start.line}:${loc.start.column})` : '';
  problems.push({ file: rel, message: message + locStr });
}

function tryParse(content, file) {
  try {
    return parser.parse(content, {
      sourceType: 'module',
      plugins: [
        'jsx',
        'typescript',
        'classProperties',
        'decorators-legacy',
        'dynamicImport',
        'optionalChaining',
        'nullishCoalescingOperator',
      ],
      errorRecovery: true,
    });
  } catch (err) {
    report(file, `Parse error: ${err.message}`);
    return null;
  }
}

files.forEach((file) => {
  let content;
  try {
    content = fs.readFileSync(file, 'utf8');
  } catch (e) {
    report(file, `Cannot read file: ${e.message}`);
    return;
  }
  const ast = tryParse(content, file);
  if (!ast) return;

  traverse(ast, {
    JSXExpressionContainer(path) {
      const expr = path.node.expression;
      if (expr && (expr.type === 'ObjectExpression' || expr.type === 'ArrayExpression')) {
        report(file, `JSX rendering of ${expr.type} (objects/arrays are invalid React children).`, path.node.loc);
      }
      if (expr && expr.type === 'Identifier') {
        const name = expr.name;
        const reObj = new RegExp(`(?:const|let|var)\\s+${name}\\s*=\\s*\\{`);
        const reArr = new RegExp(`(?:const|let|var)\\s+${name}\\s*=\\s*\\[`);
        if (reObj.test(content) || reArr.test(content)) {
          report(file, `JSX may be rendering identifier "${name}" initialized to an object/array in this file. Ensure you're rendering a string/element instead.`, path.node.loc);
        }
      }
    },

    ReturnStatement(path) {
      const arg = path.node.argument;
      if (!arg) return;
      if (arg.type === 'ObjectExpression' || arg.type === 'ArrayExpression') {
        const fn = path.getFunctionParent();
        if (fn) {
          report(file, `Function returns a plain ${arg.type} (not JSX). This may be an accidental object/array return from a component.`, path.node.loc);
        }
      }
    },

    CallExpression(path) {
      const callee = path.node.callee;
      if (callee && callee.type === 'Identifier' && callee.name === 'createClient') {
        const args = path.node.arguments || [];
        if (args[0] && (args[0].type === 'MemberExpression' || args[0].type === 'Identifier')) {
          report(file, `createClient called; ensure environment variables used here are set in Vercel (.env check).`, path.node.loc);
        }
      }
    },
  });
});

const checkoutFlat = [
  path.join(ROOT, 'pages', 'checkout.js'),
  path.join(ROOT, 'pages', 'checkout.jsx'),
  path.join(ROOT, 'pages', 'checkout/index.js'),
  path.join(ROOT, 'pages', 'checkout/index.jsx'),
  path.join(ROOT, 'pages', 'checkout/index.tsx'),
];
const present = checkoutFlat.filter((p) => fs.existsSync(p));
if (present.length > 1) {
  report(ROOT, `Duplicate checkout page files detected: ${present.map((p) => path.relative(ROOT, p)).join(', ')}`);
}

const headerFile = path.join(ROOT, 'components', 'Header.js');
if (fs.existsSync(headerFile)) {
  const headerSrc = fs.readFileSync(headerFile, 'utf8');
  const re = /src=("|')\/images\/([^\s"'<>]+)\1/;
  const m = headerSrc.match(re);
  if (m) {
    const imgPath = path.join(ROOT, 'public', 'images', m[2]);
    if (!fs.existsSync(imgPath)) {
      report(headerFile, `Image referenced (/public/images/${m[2]}) not found. Create file or update src.`);
    }
  }
}

const envPath = path.join(ROOT, '.env');
const envText = fs.existsSync(envPath) ? fs.readFileSync(envPath, 'utf8') : '';
const needsSupabase = files.some((f) => {
  const txt = fs.readFileSync(f, 'utf8');
  return txt.includes('NEXT_PUBLIC_SUPABASE_URL') || txt.includes('NEXT_PUBLIC_SUPABASE_ANON_KEY') || txt.includes('createClient(');
});
if (needsSupabase) {
  const missing = [];
  if (!/NEXT_PUBLIC_SUPABASE_URL=/.test(envText)) missing.push('NEXT_PUBLIC_SUPABASE_URL');
  if (!/NEXT_PUBLIC_SUPABASE_ANON_KEY=/.test(envText)) missing.push('NEXT_PUBLIC_SUPABASE_ANON_KEY');
  if (missing.length) {
    report(ROOT, `Missing .env keys used in project: ${missing.join(', ')}. Add them for local testing (Vercel provides envs in production).`);
  }
}

if (problems.length === 0) {
  console.log(chalk.green('No obvious issues found by static checks.'));
  console.log('Note: this script looks for common SSR/JSX problems (JSX objects/arrays, functions returning objects, duplicate pages, missing image/env).');
  console.log(chalk.cyan('Run a local production build to reproduce the exact React error if it persists:'));
  console.log(chalk.cyan('  npm run build'));
  process.exit(0);
} else {
  console.log(chalk.red(`Found ${problems.length} possible issue(s):`));
  problems.forEach((p, i) => {
    console.log(chalk.yellow(`${i + 1}. ${p.file}: ${p.message}`));
  });
  console.log('');
  console.log(chalk.cyan('Fix the flagged files and re-run the script. If the build still fails, run `npm run build` locally and paste the non-minified error output here.'));
  process.exit(1);
}