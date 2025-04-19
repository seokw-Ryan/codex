#!/usr/bin/env python3
import os
import subprocess
import logging
import sys
from utils.logger import setup_logger

def load_env(env_file='.env'):
    """Load environment variables from a .env file if it exists."""
    if os.path.isfile(env_file):
        with open(env_file) as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, val = line.split('=', 1)
                key = key.strip()
                # Strip optional surrounding quotes
                val = val.strip().strip('"').strip("'")
                os.environ.setdefault(key, val)

def spawn_agent(role, spec=None, prompt=None):
    # Use the same Python interpreter (e.g. venv) that is running the orchestrator
    cmd = [sys.executable, 'run_agent.py', '--role', role]
    if spec:
        cmd.extend(['--spec', spec])
    if prompt:
        cmd.extend(['--prompt', prompt])
    # Log the exact command being executed for debugging
    logging.info(f"Spawning {role} agent with command: {' '.join(cmd)}")
    # Run the agent subprocess (will raise CalledProcessError on failure)
    subprocess.run(cmd, check=True)

def main():
    # Load environment variables from .env (e.g. OPENAI_API_KEY)
    load_env()
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
    # Ensure OpenAI API key is set before invoking agents
    if not os.getenv('OPENAI_API_KEY'):
        logging.error('OPENAI_API_KEY not set. Please set the environment variable and try again.')
        sys.exit(1)
    try:
        spawn_agent('manager', spec=spec_path)
        logging.info('Manager agent completed successfully')
    except subprocess.CalledProcessError as e:
        logging.error(f"Error executing agent for spec '{spec_path}': {e}")
        sys.exit(1)

    # Process newly created worker specs
    queue_file = os.path.join('queue', 'new_specs.txt')
    if os.path.isfile(queue_file):
        with open(queue_file) as qf:
            worker_specs = [line.strip() for line in qf if line.strip()]
        # Log how many worker specs will be processed
        logging.info(f"Found {len(worker_specs)} new worker spec(s) to process")
        for ws in worker_specs:
            try:
                spawn_agent('worker', spec=ws)
                logging.info(f"Worker agent for spec '{ws}' completed successfully")
            except subprocess.CalledProcessError as e:
                logging.error(f"Error executing worker agent for spec '{ws}': {e}")
                sys.exit(1)
    else:
        logging.info('No new worker specs found')
    # Summarize progress via CEO agent
    try:
        logging.info('Generating progress summary...')
        spawn_agent('ceo', spec=spec_path)
        logging.info('CEO progress summary generated successfully')
    except subprocess.CalledProcessError as e:
        logging.error(f"Error generating progress summary: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
