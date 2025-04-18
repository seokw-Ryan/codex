#!/usr/bin/env python3
import os
import subprocess
import logging
import sys
from utils.logger import setup_logger

def spawn_agent(role, spec=None, prompt=None):
    # Use the same Python interpreter (e.g. venv) that is running the orchestrator
    cmd = [sys.executable, 'run_agent.py', '--role', role]
    if spec:
        cmd.extend(['--spec', spec])
    if prompt:
        cmd.extend(['--prompt', prompt])
    subprocess.run(cmd, check=True)

def main():
    setup_logger()
    logging.info('Orchestrator started')
    spec_dir = 'specs'
    if not os.path.isdir(spec_dir):
        logging.error(f"Specs directory '{spec_dir}' not found")
        sys.exit(1)
    md_files = sorted([
        f for f in os.listdir(spec_dir)
        if f.endswith('.md') and os.path.isfile(os.path.join(spec_dir, f))
    ])
    if not md_files:
        logging.error(f"No spec files (*.md) found in '{spec_dir}'")
        sys.exit(1)
    if len(md_files) == 1:
        selected = md_files[0]
        logging.info(f"Only one spec file found, selecting '{selected}'")
    else:
        print('Multiple spec files found:')
        for i, f in enumerate(md_files, 1):
            print(f'  {i}. {f}')
        while True:
            choice = input(f'Enter the number of the spec to process [1-{len(md_files)}]: ')
            if not choice.isdigit():
                print('Please enter a valid number.')
                continue
            idx = int(choice)
            if 1 <= idx <= len(md_files):
                selected = md_files[idx - 1]
                break
            print('Number out of range.')
        logging.info(f"User selected spec '{selected}'")
    spec_path = os.path.join(spec_dir, selected)
    logging.info(f"Processing spec: {spec_path}")
    try:
        spawn_agent('manager', spec=spec_path)
        logging.info('Manager agent completed successfully')
    except subprocess.CalledProcessError as e:
        logging.error(f"Error executing agent for spec '{spec_path}': {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
