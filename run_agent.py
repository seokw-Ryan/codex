#!/usr/bin/env python3
import argparse
import sys
from agents.ceo_agent import CEOAgent
from agents.manager_agent import ManagerAgent
from agents.worker_agent import WorkerAgent

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--role', required=True, choices=['ceo', 'manager', 'worker'])
    parser.add_argument('--prompt', type=str, help='User prompt for CEO')
    parser.add_argument('--spec', type=str, help='Path to spec file')
    args = parser.parse_args()

    if args.role == 'ceo':
        if not args.prompt:
            print('CEO role requires --prompt', file=sys.stderr)
            sys.exit(1)
        agent = CEOAgent(prompt=args.prompt)
    elif args.role == 'manager':
        if not args.spec:
            print('Manager role requires --spec', file=sys.stderr)
            sys.exit(1)
        agent = ManagerAgent(spec_path=args.spec)
    elif args.role == 'worker':
        if not args.spec:
            print('Worker role requires --spec', file=sys.stderr)
            sys.exit(1)
        agent = WorkerAgent(spec_path=args.spec)
    else:
        print('Invalid role', file=sys.stderr)
        sys.exit(1)

    exit_code = agent.run()
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
