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
            'Decide how many workers are needed. The optimal development team size is from 3 to 9 workers/developers. Output strictly a JSON array of objects with keys: '
            '`worker_id` (unique slug), `mission` (detailed task description), '
            '`inputs` (list of required asset paths), `outputs` (list of files to produce).'
        )
        messages = [
            {'role': 'system', 'content': system_msg},
            {'role': 'user', 'content': f'Spec header YAML:\n{header_str}\nMission markdown:{body}'}
        ]
        # Call OpenAI chat completion via new API
        try:
            resp = client.chat.completions.create(
                model=cfg.get('model'),
                messages=messages,
                max_tokens=cfg.get('max_tokens', 1500)
            )
        except Exception as e:
            print(f'OpenAI API call failed: {e}', file=sys.stderr)
            return 1
        # Get the raw response content
        text = resp.choices[0].message.content.strip()
        # Log API prompt and response for UI
        try:
            api_log_dir = os.path.join('progress', 'api_logs')
            os.makedirs(api_log_dir, exist_ok=True)
            log_path = os.path.join(api_log_dir, f'manager_{team_id}.json')
            with open(log_path, 'w') as lf:
                json.dump({'messages': messages, 'response_text': text}, lf, indent=2)
        except Exception:
            pass
        # Attempt to clean JSON by stripping code fences if present
        clean_text = text
        if clean_text.startswith("```") and clean_text.endswith("```"):
            # Remove opening fence and optional language label
            first_nl = clean_text.find('\n')
            if first_nl != -1:
                # Content between first newline after fence and closing fence
                clean_text = clean_text[first_nl+1:-3].strip()
            else:
                clean_text = clean_text.strip('`').strip()
        # Parse the JSON into tasks
        try:
            tasks = json.loads(clean_text)
        except json.JSONDecodeError:
            print('Failed to parse JSON from OpenAI response:', clean_text, file=sys.stderr)
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
        # Write manager progress summary
        try:
            progress_dir = os.path.join('progress')
            os.makedirs(progress_dir, exist_ok=True)
            progress_file = os.path.join(progress_dir, f'manager_{team_id}.md')
            with open(progress_file, 'w') as pf:
                pf.write(f'# Manager Progress for team {team_id}\n\n')
                pf.write('Generated worker specs:\n')
                for task in tasks:
                    wid = task.get('worker_id')
                    pf.write(f'- {wid}: specs/{wid}.md\n')
        except Exception:
            pass
        return 0
