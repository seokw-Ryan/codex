class AgentBase:
    def __init__(self, spec_path=None, prompt=None):
        self.spec_path = spec_path
        self.prompt = prompt

    def run(self):
        raise NotImplementedError
