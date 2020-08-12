from . import Task


class DummyTask(Task):
    def setup(self):
        self.logger.debug("Setting up Dummy Task")
        return self.ready()

    def compile(self):
        self.logger.debug("DummyTask compiling")
        return self.success()

    def run(self):
        self.logger.debug("DummyTask running.")
        return self.success()
