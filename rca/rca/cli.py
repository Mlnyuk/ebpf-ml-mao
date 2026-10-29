"""Run inside the agent Pod (kubectl exec); the bearer token never leaves the Pod."""
import argparse
import json

from .common import Settings, request, secret


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['health', 'list', 'show', 'evidence', 'run', 'incident', 'preflight', 'inspect'])
    parser.add_argument('target', nargs='?')
    parser.add_argument('--symptom', default='Manual investigation')
    args = parser.parse_args()
    s = Settings()
    paths = {'health': '/healthz', 'list': '/incidents', 'show': '/incidents/' + str(args.target),
             'evidence': '/incidents/' + str(args.target) + '/evidence',
             'run': '/incidents/' + str(args.target) + '/run', 'incident': '/incidents', 'preflight': '/preflight',
             'inspect': '/incidents/' + str(args.target) + '/preflight'}
    post = args.command in ('run', 'incident', 'preflight', 'inspect')
    body = {'pod': args.target, 'symptom': args.symptom} if args.command in ('incident', 'preflight') else {}
    result = request('http://127.0.0.1:8080' + paths[args.command], 'POST' if post else 'GET',
                     body if post else None, {'Authorization': 'Bearer ' + secret(s.auth_file)}, timeout=90)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
