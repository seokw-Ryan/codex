import os
import yaml
from agents.agent_base import AgentBase

class CEOAgent(AgentBase):
    def run(self):
        """
        Split the high-level mission into multiple team specs using OpenAI.
        """
        import os, sys, yaml, json
        # Summary mode: if spec_path provided without prompt, summarize project progress
        if self.spec_path and not self.prompt:
            from pathlib import Path
            # Load configuration for summarization
            CONFIG_PATH = 'config.yaml'
            if not Path(CONFIG_PATH).exists():
                print(f"Missing config file: {CONFIG_PATH}", file=sys.stderr)
                return 1
            with open(CONFIG_PATH) as cf:
                cfg = yaml.safe_load(cf)
            # Load spec content
            try:
                with open(self.spec_path, 'r') as sf:
                    spec_content = sf.read()
            except Exception as e:
                print(f'Failed to read spec file: {e}', file=sys.stderr)
                return 1
            # Collect progress documents
            progress_contents = ''
            prog_dir = 'progress'
            if os.path.isdir(prog_dir):
                for fname in sorted(os.listdir(prog_dir)):
                    if fname.endswith('.md'):
                        try:
                            with open(os.path.join(prog_dir, fname), 'r') as pf:
                                progress_contents += f'# {fname}\n' + pf.read() + '\n\n'
                        except:
                            continue
            # Prepare summarization prompt
            system_msg = (
                'You are a CEO-level AI agent. Summarize the current progress of the project based on the spec and progress documents. '
                'Provide a summary of completed tasks and remaining work in a structured format.'
            )
            user_msg = (f'Spec ({self.spec_path}):\n```\n{spec_content}\n```\n'
                        f'Progress docs:\n```\n{progress_contents}\n```')
            # Initialize client
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            # Call OpenAI for summarization
            try:
                resp = client.chat.completions.create(
                    model=cfg.get('model'),
                    messages=[{'role': 'system', 'content': system_msg}, {'role': 'user', 'content': user_msg}],
                    max_tokens=cfg.get('max_tokens', 1500)
                )
            except Exception as e:
                print(f'OpenAI API call failed: {e}', file=sys.stderr)
                return 1
            summary = resp.choices[0].message.content.strip()
            # Log API prompt and summary response for UI
            try:
                api_log_dir = os.path.join('progress', 'api_logs')
                os.makedirs(api_log_dir, exist_ok=True)
                # Use spec stem for filename
                log_path = os.path.join(api_log_dir, f'ceo_summary_{Path(self.spec_path).stem}.json')
                messages = [
                    {'role': 'system', 'content': system_msg},
                    {'role': 'user', 'content': user_msg}
                ]
                with open(log_path, 'w') as lf:
                    json.dump({'messages': messages, 'response_text': summary}, lf, indent=2)
            except Exception:
                pass
            # Write summary to progress
            try:
                os.makedirs(prog_dir, exist_ok=True)
                summary_file = os.path.join(prog_dir, f'ceo_summary_{Path(self.spec_path).stem}.md')
                with open(summary_file, 'w') as sf:
                    sf.write(summary)
            except:
                pass
            # Print summary
            print(summary)
            return 0
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
        # Log API prompt and response for UI (CEO split)
        try:
            api_log_dir = os.path.join('progress', 'api_logs')
            os.makedirs(api_log_dir, exist_ok=True)
            log_path = os.path.join(api_log_dir, 'ceo_split.json')
            with open(log_path, 'w') as lf:
                json.dump({'messages': messages, 'response_text': text}, lf, indent=2)
        except Exception:
            pass
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
