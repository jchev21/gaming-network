# Operator-local interface.
# The external worker receives signed files, not database access.
import argparse
import json
import os
import sys

from .repair import RepairQueue
from .repair_pr import PRVerifier


def configured_queue():
    if os.getenv(
        'GN_FEEDBACK_REPAIR_ENABLED', 'false'
    ) != 'true':
        raise ValueError('Repair feature disabled')

    return RepairQueue(
        os.getenv(
            'GN_FEEDBACK_REPAIR_DB_PATH',
            '/data/gn-repair.sqlite3',
        ),
        {
            int(x)
            for x in os.environ[
                'GN_FEEDBACK_OWNER_IDS'
            ].split(',')
        },
        int(os.environ['GN_FEEDBACK_GUILD_ID']),
        int(os.environ['GN_FEEDBACK_OWNER_CHANNEL_ID']),
        os.environ['GN_FEEDBACK_WORKER_KEY'].encode(),
        os.environ['GN_FEEDBACK_BASE_SHA'],
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'action', choices=['export', 'import']
    )
    parser.add_argument('file')
    args = parser.parse_args()

    q = configured_queue()
    try:
        if args.action == 'export':
            # Reserve exclusive output before consuming a lease.
            fd = os.open(
                args.file,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(fd, 'w') as f:
                value = q.claim()
                if value is None:
                    raise ValueError('No queued job')
                json.dump(value, f)
        else:
            with open(args.file, 'rb') as f:
                raw = f.read(16385)
            if len(raw) > 16384:
                raise ValueError('Result file bound')

            verifier = PRVerifier(
                os.environ['GN_FEEDBACK_GITHUB_TOKEN'],
                os.environ[
                    'GN_FEEDBACK_REQUIRED_CHECKS'
                ].split(','),
                {
                    int(x)
                    for x in os.environ[
                        'GN_FEEDBACK_CI_APP_IDS'
                    ].split(',')
                },
            )
            q.submit(json.loads(raw), verifier)

        print(
            'Local handoff operation complete; '
            'no merge/deploy authorized.'
        )
    finally:
        q.close()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print(
            'Handoff refused or failed; inspect safe local '
            'job state. No secrets logged.',
            file=sys.stderr,
        )
        sys.exit(1)
