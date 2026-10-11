"""Deploy only the signed delivery endpoint to the authorized existing project.

Does not alter aliases, project protection, Neon settings, or production.
After deployment, verify the source/routes before creating its narrow protection
exception and configuring Neon. Never make the normal app preview public.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from run import load_env_file


SOURCE_FILES = (
    'app/__init__.py', 'app/auth_config.py', 'app/webhook.py',
    'app/api/__init__.py', 'app/api/auth_webhook.py',
    'app/db/__init__.py', 'app/db/base.py', 'app/db/database.py',
    'app/services/__init__.py', 'app/services/auth_storage.py',
    'app/services/auth_webhooks.py', 'app/services/neon_auth.py',
)


def deploy():
    load_env_file(ROOT / '.env.private-access')
    values = {key: os.environ[key] for key in (
        'APP_BASE_URL', 'NEON_AUTH_BASE_URL', 'ALLOWED_EMAILS', 'DATABASE_URL',
        'SESSION_SECRET', 'SMTP_HOST', 'SMTP_PORT', 'SMTP_USERNAME',
        'SMTP_PASSWORD', 'SMTP_FROM', 'SMTP_SECURITY',
    )}
    values.update(AUTH_MODE='neon', APP_ENV='preview', COOKIE_SECURE='true', SQLALCHEMY_ECHO='false')
    with tempfile.TemporaryDirectory(prefix='guardias-webhook-') as folder:
        root = Path(folder)
        sources = [ROOT / name for name in SOURCE_FILES] + list((ROOT / 'app/models').glob('*.py'))
        for source in sources:
            if not source.exists():
                continue
            target = root / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        for name in ('requirements.txt', 'uv.lock', '.python-version'):
            if (ROOT / name).exists(): shutil.copyfile(ROOT / name, root / name)
        (root / 'pyproject.toml').write_text((ROOT / 'pyproject.toml').read_text().replace('app.main:app', 'app.webhook:app'))
        (root / 'vercel.json').write_text(json.dumps({'framework':'fastapi','functions':{'app/webhook.py':{'excludeFiles':'{tests/**,docs/**,.env*,.venv/**,scripts/**}'}}}))
        args = ['vercel','deploy',str(root),'--project','gestion-guardias','--scope','7h146os-projects','--target','preview','--no-wait','--json','--yes']
        for key, value in values.items(): args.extend(['--env',key+'='+value])
        result = subprocess.run(args, text=True, capture_output=True)
        if result.returncode:
            diagnostic = result.stderr
            for value in values.values():
                diagnostic = diagnostic.replace(value, '[redacted]')
            errors = [line for line in diagnostic.splitlines() if 'Error:' in line]
            raise RuntimeError('Webhook-only deployment failed: ' + (' '.join(errors)[:1200] or 'response withheld.'))
        payload = json.loads(result.stdout)
        item = payload.get('deployment', payload)
        identifier, url = item.get('id'), item.get('url')
        if not identifier or not url:
            raise RuntimeError('Missing deployment identifier; response withheld.')
        private = ROOT / '.env.private-access'
        lines = private.read_text().splitlines()
        for key, value in {'WEBHOOK_DEPLOYMENT_ID':identifier,'WEBHOOK_DEPLOYMENT_URL':url if url.startswith('https://') else 'https://'+url}.items():
            lines = [line for line in lines if not line.startswith(key+'=')]
            lines.append(key+'='+value)
        private.write_text('\n'.join(lines)+'\n')
        private.chmod(0o600)
        print('Webhook-only preview:', identifier, url)


if __name__ == '__main__':
    deploy()
