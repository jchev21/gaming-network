# Read-only independent PR/CI verification.
# Never follows returned URLs.
import json
import re
import urllib.request


class RejectRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('GitHub redirect refused')


class PRVerifier:
    def __init__(self, token, required_checks, allowed_app_ids):
        if not token or not required_checks or not allowed_app_ids:
            raise ValueError('PR verification configuration required')
        self.token = token
        self.checks = set(required_checks)
        self.apps = set(allowed_app_ids)
        self.opener = urllib.request.build_opener(
            RejectRedirect()
        )

    def read(self, path):
        if not re.fullmatch(
            r'/pulls/[1-9][0-9]*|'
            r'/commits/[a-f0-9]{40}/check-runs'
            r'\?per_page=100&page=[12]',
            path,
        ):
            raise ValueError('Unsafe GitHub path')

        req = urllib.request.Request(
            'https://api.github.com/repos/jchev21/gaming-network'
            + path,
            headers={
                'Authorization': 'Bearer ' + self.token,
                'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2026-03-10',
                'User-Agent': 'GN-Feedback-Review/1',
            },
        )

        try:
            with self.opener.open(req, timeout=10) as r:
                data = r.read(524289)
                if len(data) > 524288:
                    raise ValueError('PR response bound')
                return json.loads(data)
        except Exception:
            raise ValueError(
                'PR verification unavailable; '
                'no raw response exposed'
            ) from None

    def __call__(self, job, result, base_sha):
        pr = self.read('/pulls/' + str(result['pr']))
        branch = f"ai-feedback/{job['id']}/a{job['attempt']}"

        if (
            pr.get('state') != 'open'
            or pr.get('draft') is not True
            or pr.get('merged') is not False
            or pr.get('head', {}).get('sha') != result['sha']
            or pr.get('head', {}).get('ref') != branch
            or pr.get('head', {}).get('repo', {}).get(
                'full_name'
            ) != 'jchev21/gaming-network'
            or pr.get('base', {}).get('repo', {}).get(
                'full_name'
            ) != 'jchev21/gaming-network'
            or pr.get('base', {}).get('sha') != base_sha
            or pr.get('head', {}).get('repo', {}).get(
                'private'
            ) is not True
            or pr.get('base', {}).get('repo', {}).get(
                'private'
            ) is not True
        ):
            raise ValueError('PR origin/branch/draft/base mismatch')

        runs = []
        for page in (1, 2):
            response = self.read(
                f"/commits/{result['sha']}/check-runs"
                f"?per_page=100&page={page}"
            )
            part = response.get('check_runs')
            if (
                not isinstance(part, list)
                or response.get('total_count', 201) > 200
            ):
                raise ValueError(
                    'CI response incomplete or over limit'
                )
            runs.extend(part)
            if len(runs) >= response['total_count']:
                break

        names = {}
        for run in runs:
            if (
                run.get('name') in self.checks
                and run.get('app', {}).get('id') in self.apps
                and run.get('head_sha') == result['sha']
            ):
                # Do not accept an old successful run over an ambiguous rerun.
                if run['name'] in names:
                    return 'NOT RUN'
                names[run['name']] = run

        if set(names) != self.checks:
            return 'NOT RUN'
        if any(
            r.get('status') != 'completed'
            for r in names.values()
        ):
            return 'NOT RUN'

        return (
            'PASS'
            if all(
                r.get('conclusion') == 'success'
                for r in names.values()
            )
            else 'FAIL'
        )
