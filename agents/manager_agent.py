from agents.agent_base import AgentBase

class ManagerAgent(AgentBase):
    def run(self):
        """
        Read a team spec, split into worker tasks via OpenAI, write worker specs, and enqueue them.
        """
        import os, yaml, json, sys
        # Load OpenAI client
        from openai import OpenAI
        from pathlib import Path
        # Load config
        CONFIG_PATH = 'config.yaml'
        if not Path(CONFIG_PATH).exists():
            print(f'Missing config file: {CONFIG_PATH}', file=sys.stderr)
            return 1
        with open(CONFIG_PATH) as cf:
            cfg = yaml.safe_load(cf)
        # Set API key
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print('OPENAI_API_KEY not set', file=sys.stderr)
            return 1
        # Initialize OpenAI client with API key
        client = OpenAI(api_key=api_key)
        # Parse existing spec
        if not os.path.exists(self.spec_path):
            print(f'Spec file not found: {self.spec_path}', file=sys.stderr)
            return 1
        with open(self.spec_path) as sf:
            content = sf.read()
        parts = content.split('---')
        if len(parts) < 3:
            print(f'Invalid spec format: {self.spec_path}', file=sys.stderr)
            return 1
        header_str = parts[1]
        body = parts[2]
        spec_header = yaml.safe_load(header_str)
        team_id = spec_header.get('team_id')
        # Prepare prompt
        system_msg = (
            'You are a Manager-level AI agent. Split the following team spec into logical, agile worker-level tasks. '
            'Decide how many workers are needed. Output strictly a JSON array of objects with keys: '
            '`worker_id` (unique slug), `mission` (detailed task description), '
            '`inputs` (list of required asset paths), `outputs` (list of files to produce).'
        )
        messages = [
            {'role': 'system', 'content': system_msg},
            {'role': 'user', 'content': f'Spec header YAML:\n{header_str}\nMission markdown:{body}'}
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
        # Write worker specs
        specs_dir = 'specs'
        os.makedirs(specs_dir, exist_ok=True)
        queue_file = os.path.join('queue', 'new_specs.txt')
        os.makedirs(os.path.dirname(queue_file), exist_ok=True)
        for task in tasks:
            worker_id = task.get('worker_id')
            mission = task.get('mission', '')
            inputs = task.get('inputs', [])
            outputs = task.get('outputs', [])
            spec_header2 = {
                'team_id': worker_id,
                'version': 1,
                'parent': team_id,
                'status': 'draft',
                'inputs': inputs,
                'outputs': outputs
            }
            spec_path = os.path.join(specs_dir, f'{worker_id}.md')
            with open(spec_path, 'w') as wf:
                wf.write('---\n')
                yaml.dump(spec_header2, wf)
                wf.write('---\n')
                wf.write(f'## Mission\n{mission}\n')
            with open(queue_file, 'a') as qf:
                qf.write(spec_path + '\n')
        return 0
