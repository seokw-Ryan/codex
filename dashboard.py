#!/usr/bin/env python3
"""
Dashboard UI to monitor company progress, teams, workers, and API logs.
"""
import os
# Load environment variables from .env (if python-dotenv is installed)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
import json
import yaml
from flask import Flask, render_template_string, send_from_directory, send_file, abort, url_for, redirect

# Configuration for directories
SPECS_DIR = 'specs'
PROGRESS_DIR = 'progress'
API_LOGS_DIR = os.path.join(PROGRESS_DIR, 'api_logs')

app = Flask(__name__)

def load_spec_headers():
    """Load YAML headers from spec markdown files."""
    headers = []
    if not os.path.isdir(SPECS_DIR):
        return headers
    for filename in sorted(os.listdir(SPECS_DIR)):
        if not filename.endswith('.md'):
            continue
        path = os.path.join(SPECS_DIR, filename)
        try:
            with open(path, 'r') as f:
                content = f.read()
            parts = content.split('---')
            if len(parts) < 3:
                continue
            header = yaml.safe_load(parts[1]) or {}
            header['spec_file'] = filename
            headers.append(header)
        except Exception:
            continue
    return headers

def orchestrate_once():
    """Run manager, workers, and CEO summary for all specs that haven't been processed yet."""
    # Lazy-import agents
    try:
        from agents.manager_agent import ManagerAgent
        from agents.worker_agent import WorkerAgent
        from agents.ceo_agent import CEOAgent
    except ImportError:
        return
    # Load current specs and headers
    headers = load_spec_headers()
    # Ensure queue dir
    queue_file = os.path.join('queue', 'new_specs.txt')
    # Manager: for team specs not yet processed (skip stopped)
    for h in headers:
        team_id = h.get('team_id')
        parent = h.get('parent')
        spec_file = h.get('spec_file')
        # Only top-level team specs (parent is None)
        if parent:
            continue
        # Skip if stopped
        stop_marker = os.path.join(PROGRESS_DIR, f'stopped_{spec_file}')
        if os.path.exists(stop_marker):
            continue
        # Skip if manager progress already exists
        prog = os.path.join(PROGRESS_DIR, f'manager_{team_id}.md')
        if os.path.exists(prog):
            continue
        # Run manager agent
        spec_path = os.path.join(SPECS_DIR, spec_file)
        ManagerAgent(spec_path=spec_path).run()
    # Worker: process new worker specs in queue
    if os.path.isfile(queue_file):
        with open(queue_file) as qf:
            worker_specs = {line.strip() for line in qf if line.strip()}
        # Clear queue
        try:
            os.remove(queue_file)
        except Exception:
            pass
        for ws in sorted(worker_specs):
            WorkerAgent(spec_path=ws).run()
    # CEO: summary for each team spec not yet summarized (skip stopped)
    for h in headers:
        team_id = h.get('team_id')
        parent = h.get('parent')
        spec_file = h.get('spec_file')
        if parent:
            continue
        # Skip if stopped
        stop_marker = os.path.join(PROGRESS_DIR, f'stopped_{spec_file}')
        if os.path.exists(stop_marker):
            continue
        # Skip if CEO summary exists
        summary_file = os.path.join(PROGRESS_DIR, f'ceo_summary_{os.path.splitext(spec_file)[0]}.md')
        if os.path.exists(summary_file):
            continue
        # Run CEO summary
        spec_path = os.path.join(SPECS_DIR, spec_file)
        CEOAgent(spec_path=spec_path).run()

def orchestrate_loop(interval=30):
    """Background loop to periodically orchestrate tasks."""
    import time
    while True:
        orchestrate_once()
        time.sleep(interval)

@app.route('/')
def index():
    headers = load_spec_headers()
    teams = [h for h in headers if not h.get('parent')]
    workers = [h for h in headers if h.get('parent')]
    # API logs stats
    api_logs = sorted(os.listdir(API_LOGS_DIR)) if os.path.isdir(API_LOGS_DIR) else []
    counts = {'manager': 0, 'worker': 0, 'ceo': 0}
    for fn in api_logs:
        if fn.startswith('manager_'):
            counts['manager'] += 1
        elif fn.startswith('worker_'):
            counts['worker'] += 1
        elif fn.startswith('ceo'):
            counts['ceo'] += 1
    return render_template_string(
        '''<!doctype html>
<title>Company Dashboard</title>
<h1>Company Dashboard</h1>
<ul>
  <li>Total Teams: {{ teams|length }}</li>
  <li>Total Workers: {{ workers|length }}</li>
  <li>API Calls:
    <ul>
      <li>Manager: {{ counts.manager }}</li>
      <li>Worker: {{ counts.worker }}</li>
      <li>CEO: {{ counts.ceo }}</li>
    </ul>
  </li>
</ul>
<p><a href="{{ url_for('teams') }}">View Teams &amp; Workers</a></p>
<p><a href="{{ url_for('specs_list') }}">View All Specs</a></p>
<p><a href="{{ url_for('api_logs') }}">View API Logs</a></p>
<p><a href="{{ url_for('progress') }}">View Progress Documents</a></p>
<p><a href="{{ url_for('network') }}">View Team-Worker Graph</a></p>
        ''', teams=teams, workers=workers, counts=counts)

@app.route('/teams')
def teams():
    headers = load_spec_headers()
    # Determine stopped specs
    stopped = set()
    if os.path.isdir(PROGRESS_DIR):
        for fn in os.listdir(PROGRESS_DIR):
            if fn.startswith('stopped_'):
                stopped.add(fn[len('stopped_'):])
    # Map children by parent team_id
    children_map = {}
    for h in headers:
        parent = h.get('parent')
        if parent:
            children_map.setdefault(parent, []).append(h)
    teams_list = [h for h in headers if not h.get('parent')]
    return render_template_string(
        '''<!doctype html>
<title>Teams & Workers</title>
<h1>Teams & Workers</h1>
<ul>
{% for team in teams %}
  <li>
    <b>{{ team.team_id }}</b> - spec: <a href="{{ url_for('get_spec', filename=team.spec_file) }}">{{ team.spec_file }}</a>
    [
    {% if team.spec_file in stopped %}
      <a href="{{ url_for('start_spec', spec_file=team.spec_file) }}">Start</a>
    {% else %}
      <a href="{{ url_for('stop_spec', spec_file=team.spec_file) }}">Stop</a>
    {% endif %}
    ]
    <br>
    Progress:
    <ul>
      <li>Manager: {% set m = 'manager_' + team.team_id + '.md' %}{% if m in files_progress %}<a href="{{ url_for('view_progress', filename=m) }}">{{ m }}</a>{% else %}None{% endif %}</li>
      <li>CEO: {% set c = 'ceo_summary_' + team.team_id + '.md' %}{% if c in files_progress %}<a href="{{ url_for('view_progress', filename=c) }}">{{ c }}</a>{% else %}None{% endif %}</li>
    </ul>
    {% if children_map.get(team.team_id) %}
    Workers:
    <ul>
      {% for child in children_map.get(team.team_id, []) %}
      <li>
        {{ child.team_id }} - spec: <a href="{{ url_for('get_spec', filename=child.spec_file) }}">{{ child.spec_file }}</a>
        <br>
        Progress: {% set w = 'worker_' + child.team_id + '.md' %}{% if w in files_progress %}<a href="{{ url_for('view_progress', filename=w) }}">{{ w }}</a>{% else %}None{% endif %}
      </li>
      {% endfor %}
    </ul>
    {% endif %}
  </li>
{% endfor %}
</ul>
<p><a href="{{ url_for('index') }}">Back to Dashboard</a></p>
''', teams=teams_list, children_map=children_map, stopped=stopped, files_progress=[f for f in os.listdir(PROGRESS_DIR) if f.endswith('.md')] )

@app.route('/specs/<path:filename>')
def get_spec(filename):
    if not os.path.exists(os.path.join(SPECS_DIR, filename)):
        abort(404)
    return send_from_directory(SPECS_DIR, filename)

@app.route('/api_logs')
def api_logs():
    if not os.path.isdir(API_LOGS_DIR):
        return 'No API logs found', 404
    files = sorted(os.listdir(API_LOGS_DIR))
    return render_template_string(
        '''<!doctype html>
<title>API Logs</title>
<h1>API Logs</h1>
<ul>
{% for fn in files %}
  <li><a href="{{ url_for('view_api_log', filename=fn) }}">{{ fn }}</a></li>
{% endfor %}
</ul>
<p><a href="{{ url_for('index') }}">Back to Dashboard</a></p>
''', files=files)

@app.route('/api_logs/<path:filename>')
def view_api_log(filename):
    path = os.path.join(API_LOGS_DIR, filename)
    if not os.path.exists(path):
        abort(404)
    try:
        with open(path, 'r') as f:
            data = json.load(f)
    except Exception:
        return 'Failed to load log', 500
    return render_template_string(
        '''<!doctype html>
<title>{{ filename }}</title>
<h1>{{ filename }}</h1>
<pre>{{ data | tojson(indent=2) }}</pre>
<p><a href="{{ url_for('api_logs') }}">Back to API Logs</a></p>
''', filename=filename, data=data)

@app.route('/progress')
def progress():
    """List progress markdown documents."""
    if not os.path.isdir(PROGRESS_DIR):
        return 'No progress directory found', 404
    files = [f for f in sorted(os.listdir(PROGRESS_DIR)) if f.endswith('.md')]
    return render_template_string(
        '''<!doctype html>
<title>Progress Documents</title>
<h1>Progress Documents</h1>
<ul>
{% for fn in files %}
  <li><a href="{{ url_for('view_progress', filename=fn) }}">{{ fn }}</a></li>
{% endfor %}
</ul>
<p><a href="{{ url_for('index') }}">Back to Dashboard</a></p>
''', files=files)

@app.route('/progress/<path:filename>')
def view_progress(filename):
    """Display a progress markdown document."""
    path = os.path.join(PROGRESS_DIR, filename)
    if not os.path.exists(path):
        abort(404)
    try:
        with open(path, 'r') as f:
            content = f.read()
    except Exception:
        return 'Failed to load progress document', 500
    return render_template_string(
        '''<!doctype html>
<title>{{ filename }}</title>
<h1>{{ filename }}</h1>
<pre>{{ content }}</pre>
<p><a href="{{ url_for('progress') }}">Back to Progress</a></p>
''', filename=filename, content=content)

@app.route('/stop/<path:spec_file>')
def stop_spec(spec_file):
    """Mark a team spec as stopped to pause orchestration."""
    marker = os.path.join(PROGRESS_DIR, f'stopped_{spec_file}')
    try:
        # create empty stop marker
        os.makedirs(PROGRESS_DIR, exist_ok=True)
        with open(marker, 'w'):
            pass
    except Exception:
        pass
    # Redirect back to teams view
    return redirect(url_for('teams'))

@app.route('/start/<path:spec_file>')
def start_spec(spec_file):
    """Remove stop marker and enqueue missing worker specs for a team."""
    # remove stop marker
    marker = os.path.join(PROGRESS_DIR, f'stopped_{spec_file}')
    try:
        if os.path.exists(marker):
            os.remove(marker)
    except Exception:
        pass
    # enqueue missing worker specs
    headers = load_spec_headers()
    # find team header
    team_header = next((h for h in headers if h.get('spec_file') == spec_file), None)
    if team_header:
        team_id = team_header.get('team_id')
        # map children
        children = [h for h in headers if h.get('parent') == team_id]
        queue_file = os.path.join('queue', 'new_specs.txt')
        os.makedirs(os.path.dirname(queue_file), exist_ok=True)
        for child in children:
            pid = child.get('team_id')
            progress_file = os.path.join(PROGRESS_DIR, f'worker_{pid}.md')
            if not os.path.exists(progress_file):
                # enqueue spec path
                spec_path = os.path.join(SPECS_DIR, child.get('spec_file'))
                try:
                    with open(queue_file, 'a') as qf:
                        qf.write(spec_path + '\n')
                except Exception:
                    pass
    # Redirect back to teams view
    return redirect(url_for('teams'))

@app.route('/network.png')
def network():
    """Generate and return a PNG network graph of CEO->teams->workers."""
    # Build graph from specs
    try:
        import networkx as nx
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import io
    except ImportError:
        return 'Network graph requires networkx and matplotlib', 500
    headers = load_spec_headers()
    G = nx.DiGraph()
    # Add CEO node
    G.add_node('CEO')
    for h in headers:
        team_id = h.get('team_id')
        parent = h.get('parent')
        G.add_node(team_id)
        if parent:
            G.add_edge(parent, team_id)
        else:
            G.add_edge('CEO', team_id)
    # Draw graph
    fig = plt.figure(figsize=(8, 8))
    pos = nx.spring_layout(G)
    nx.draw(G, pos, with_labels=True, arrows=True, node_size=1500, node_color='lightblue')
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return send_file(buf, mimetype='image/png')
@app.route('/specs')
def specs_list():
    """List all spec markdown files with status, progress, and API logs."""
    headers = load_spec_headers()
    # Determine stopped specs
    stopped = set()
    if os.path.isdir(PROGRESS_DIR):
        for fn in os.listdir(PROGRESS_DIR):
            if fn.startswith('stopped_'):
                stopped.add(fn[len('stopped_'):])
    # Gather progress and API log files
    progress_files = set()
    if os.path.isdir(PROGRESS_DIR):
        for fn in os.listdir(PROGRESS_DIR):
            if fn.endswith('.md'):
                progress_files.add(fn)
    api_log_files = set()
    if os.path.isdir(API_LOGS_DIR):
        for fn in os.listdir(API_LOGS_DIR):
            api_log_files.add(fn)
    # Render specs list
    return render_template_string(
        '''<!doctype html>
<title>Specs List</title>
<h1>All Specifications</h1>
<ul>
{% for h in headers %}
  <li>
    <b>{{ h.team_id }}</b>
    (spec: <a href="{{ url_for('get_spec', filename=h.spec_file) }}">{{ h.spec_file }}</a>)
    {% if not h.parent %}
      [ {% if h.spec_file in stopped %}
          <a href="{{ url_for('start_spec', spec_file=h.spec_file) }}">Start</a>
        {% else %}
          <a href="{{ url_for('stop_spec', spec_file=h.spec_file) }}">Stop</a>
        {% endif %} ]
    {% endif %}
    <br>
    Version: {{ h.get('version') }}, Status: {{ h.get('status') }}<br>
    {% if h.parent %}Parent Team: {{ h.parent }}{% endif %}
    <br>Progress:
    <ul>
      {% if not h.parent %}
        {% set mfile = 'manager_' + h.team_id + '.md' %}
        <li>Manager: {% if mfile in progress_files %}<a href="{{ url_for('view_progress', filename=mfile) }}">{{ mfile }}</a>{% else %}None{% endif %}</li>
        {% set cfile = 'ceo_summary_' + h.team_id + '.md' %}
        <li>CEO Summary: {% if cfile in progress_files %}<a href="{{ url_for('view_progress', filename=cfile) }}">{{ cfile }}</a>{% else %}None{% endif %}</li>
      {% else %}
        {% set wfile = 'worker_' + h.team_id + '.md' %}
        <li>Worker: {% if wfile in progress_files %}<a href="{{ url_for('view_progress', filename=wfile) }}">{{ wfile }}</a>{% else %}None{% endif %}</li>
      {% endif %}
    </ul>
    API Logs:
    <ul>
      {% if not h.parent %}
        {% set mlog = 'manager_' + h.team_id + '.json' %}
        <li>Manager Log: {% if mlog in api_log_files %}<a href="{{ url_for('view_api_log', filename=mlog) }}">{{ mlog }}</a>{% else %}None{% endif %}</li>
        {% set clog = 'ceo_summary_' + h.team_id + '.json' %}
        <li>CEO Summary Log: {% if clog in api_log_files %}<a href="{{ url_for('view_api_log', filename=clog) }}">{{ clog }}</a>{% else %}None{% endif %}</li>
      {% else %}
        {% set wlog = 'worker_' + h.team_id + '.json' %}
        <li>Worker Log: {% if wlog in api_log_files %}<a href="{{ url_for('view_api_log', filename=wlog) }}">{{ wlog }}</a>{% else %}None{% endif %}</li>
      {% endif %}
    </ul>
  </li>
{% endfor %}
</ul>
<p><a href="{{ url_for('index') }}">Back to Dashboard</a></p>
''', headers=headers, stopped=stopped, progress_files=progress_files, api_log_files=api_log_files)

if __name__ == '__main__':
    # Start orchestration loop in background
    import threading
    t = threading.Thread(target=orchestrate_loop, daemon=True)
    t.start()
    # Run Flask UI on localhost:5000
    app.run(host='0.0.0.0', port=5000, debug=True)