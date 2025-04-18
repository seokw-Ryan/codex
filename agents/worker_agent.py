from agents.agent_base import AgentBase

class WorkerAgent(AgentBase):
    def run(self):
        """
        Parse a worker spec and produce placeholder outputs for review.
        """
        import os, yaml, json, sys
        from pathlib import Path
        # Read spec
        if not Path(self.spec_path).exists():
            print(f'Spec file not found: {self.spec_path}', file=sys.stderr)
            return 1
        with open(self.spec_path) as sf:
            text = sf.read()
        parts = text.split('---')
        if len(parts) < 3:
            print(f'Invalid spec format: {self.spec_path}', file=sys.stderr)
            return 1
        header_str = parts[1]
        body = parts[2]
        spec_header = yaml.safe_load(header_str)
        team_id = spec_header.get('team_id')
        version = spec_header.get('version', 1)
        # Prepare output directory
        base_out = os.path.join('outputs', team_id, str(version))
        os.makedirs(base_out, exist_ok=True)
        # Save mission for reference
        mission_file = os.path.join(base_out, 'MISSION.md')
        with open(mission_file, 'w') as mf:
            mf.write(body)
        # Save metadata
        meta_file = os.path.join(base_out, 'meta.json')
        with open(meta_file, 'w') as mf:
            json.dump(spec_header, mf, indent=2)
        # Invoke the Codex CLI to generate actual outputs in this directory
        import subprocess
        mission_text = body.strip()
        # Ensure codex is available
        try:
            # Pass the mission text as a single argument to codex
            cmd = ['codex', mission_text]
            print(f'Invoking codex CLI: {cmd}', file=sys.stderr)
            result = subprocess.run(cmd, cwd=base_out)
            return result.returncode
        except FileNotFoundError:
            print('Error: codex CLI not found. Please install codex and ensure it is in PATH.', file=sys.stderr)
            return 1
