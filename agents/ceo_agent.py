import os
import yaml
from agents.agent_base import AgentBase

class CEOAgent(AgentBase):
    def run(self):
        """
        Split the high-level mission into multiple team specs using OpenAI.
        """
        import os, sys, yaml, json
        # Load configuration
        from pathlib import Path
        CONFIG_PATH = 'config.yaml'
        if not Path(CONFIG_PATH).exists():
            print(f'Missing config file: {CONFIG_PATH}', file=sys.stderr)
            return 1
        with open(CONFIG_PATH) as cf:
            cfg = yaml.safe_load(cf)
        # Set OpenAI API key
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print('OPENAI_API_KEY not set', file=sys.stderr)
            return 1
        # Initialize OpenAI client
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        # Prepare prompt
        system_msg = (
            'You are a CEO-level AI agent. Split the following mission into logical, agile team-level tasks. '
            'Decide how many teams are needed. Output strictly a JSON array of objects with keys: '
            '`team_id` (unique slug), `mission` (description of team scope).'
        )
        messages = [
            {'role': 'system', 'content': system_msg},
            {'role': 'user', 'content': f'Mission: {self.prompt}'}
        ]
        # Call OpenAI
        # Call OpenAI chat completion via new API
        resp = client.chat.completions.create(
            model=cfg.get('model'),
            messages=messages,
            max_tokens=cfg.get('max_tokens', 1500)
        )
        text = resp.choices[0].message.content.strip()
        try:
            tasks = json.loads(text)
        except json.JSONDecodeError:
            print('Failed to parse JSON from OpenAI response:', text, file=sys.stderr)
            return 1
        # Write specs and enqueue
        specs_dir = 'specs'
        os.makedirs(specs_dir, exist_ok=True)
        queue_file = os.path.join('queue', 'new_specs.txt')
        os.makedirs(os.path.dirname(queue_file), exist_ok=True)
        for task in tasks:
            team_id = task.get('team_id')
            mission = task.get('mission', '')
            spec_header = {
                'team_id': team_id,
                'version': 1,
                'parent': None,
                'status': 'draft',
                'inputs': task.get('inputs', []),
                'outputs': task.get('outputs', [])
            }
            spec_path = os.path.join(specs_dir, f'{team_id}.md')
            with open(spec_path, 'w') as f:
                f.write('---\n')
                yaml.dump(spec_header, f)
                f.write('---\n')
                f.write(f'## Mission\n{mission}\n')
            with open(queue_file, 'a') as qf:
                qf.write(spec_path + '\n')
        return 0
