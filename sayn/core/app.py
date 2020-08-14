from datetime import datetime, date, timedelta
from uuid import UUID, uuid4

from ..tasks import TaskStatus
from ..tasks.task_wrapper import TaskWrapper
from ..utils.dag import query as dag_query, topological_sort
from .config import get_connections
from .errors import CommandError, ConfigError
from .logger import AppLogger

run_id = uuid4()


class App:
    run_id: UUID = run_id
    start_ts = datetime.now()
    logger = AppLogger(run_id)

    run_arguments = {
        "folders": {
            "python": "python",
            "sql": "sql",
            "compile": "compile",
            "logs": "logs",
        },
        "full_load": False,
        "start_dt": date.today() - timedelta(days=1),
        "end_dt": date.today() - timedelta(days=1),
        "debug": False,
        "profile": None,
    }

    project_parameters = dict()
    credentials = dict()
    default_db = None

    tasks = dict()
    dag = dict()

    task_query = list()

    connections = dict()

    def set_run_arguments(self, **kwargs):
        self.run_arguments.update(kwargs)

    def set_project(self, project):
        self.project_parameters.update(project.parameters or dict())
        self.credentials = {k: None for k in project.required_credentials}
        self.default_db = project.default_db

    def set_settings(self, settings):
        parameters = dict()
        credentials = dict()
        profile_name = self.run_arguments["profile"]

        # Get parameters and credentials from yaml
        if settings.yaml is not None:
            if profile_name is not None and profile_name not in settings.yaml.profiles:
                raise CommandError(
                    f'Profile "{profile_name}" not defined in settings.yaml.'
                )

            profile_name = profile_name or settings.yaml.default_profile

            parameters = settings.yaml.profiles[profile_name].parameters or dict()

            credentials = {
                project_name: settings.yaml.credentials[yaml_name]
                for project_name, yaml_name in settings.yaml.profiles[
                    profile_name
                ].credentials.items()
            }
            self.run_arguments["profile"] = profile_name

        # Update parameters and credentials with environment
        if settings.environment is not None:
            parameters.update(settings.environment.parameters or dict())
            credentials.update(settings.environment.credentials or dict())

        # Validate the given parameters
        error_items = set(parameters.keys()) - set(self.project_parameters.keys())
        if error_items:
            raise ConfigError(
                f"Some parameters are not accepted by this project: {', '.join(error_items)}"
            )

        self.project_parameters.update(parameters)

        # Validate credentials
        error_items = set(credentials.keys()) - set(self.credentials.keys())
        if error_items:
            raise ConfigError(
                f"Some credentials are not accepted by this project: {', '.join(error_items)}"
            )

        error_items = set(self.credentials.keys()) - set(credentials.keys())
        if error_items:
            raise ConfigError(f"Some credentials are missing: {', '.join(error_items)}")

        error_items = [n for n, v in credentials.items() if "type" not in v]
        if error_items:
            raise ConfigError(
                f"Some credentials are missing a type: {', '.join(error_items)}"
            )

        self.credentials.update(credentials)

        # Create connections
        self.connections = get_connections(self.credentials)

    def set_tasks(self, tasks, task_query):
        self.task_query = task_query

        self.dag = {
            task["name"]: [p for p in task.get("parents", list())]
            for task in tasks.values()
        }

        self._tasks_dict = {
            task_name: tasks[task_name] for task_name in topological_sort(self.dag)
        }

        tasks_in_query = dag_query(self.dag, self.task_query)

        for task_name, task in self._tasks_dict.items():
            self.logger.set_current_task(task_name)
            self.tasks[task_name] = TaskWrapper(
                task,
                [self.tasks[p] for p in task.get("parents", list())],
                task_name in tasks_in_query,
                self.logger.get_task_logger(task_name),
                self.connections,
                self.default_db,
                self.project_parameters,
                self.run_arguments,
            )

        self.logger.set_tasks(tasks_in_query)

    # Commands

    def run(self):
        self._execute_dag("run")

    def compile(self):
        self._execute_dag("compile")

    def _execute_dag(self, command):
        self.logger.set_stage(command)
        tasks_to_run = {
            name: task for name, task in self.tasks.items() if task.should_run()
        }
        self.logger.set_tasks(list(tasks_to_run.keys()))
        for task_name, task in tasks_to_run.items():
            if command == "run":
                task.run()
            else:
                task.compile()

        self.logger.set_stage("summary")
        succeeded = [
            name
            for name, task in tasks_to_run.items()
            if task.status == TaskStatus.SUCCESS
        ]
        skipped = [
            name
            for name, task in tasks_to_run.items()
            if task.status == TaskStatus.SKIPPED
        ]
        failed = [
            name
            for name, task in tasks_to_run.items()
            if task.status == TaskStatus.FAILED
        ]
        self.logger.report_event(
            {
                "event": "execution_finished",
                "command": command,
                "context": "app",
                "duration": datetime.now() - self.start_ts,
                "level": "failed"
                if len(failed) > 0
                else "warning"
                if len(skipped) > 0
                else "success",
                "succeeded": succeeded,
                "skipped": skipped,
                "failed": failed,
            }
        )
