from datetime import datetime, timedelta

from colorama import init, Fore, Style
from halo import Halo

from .misc import group_list

init(autoreset=True)

# Styling functions

dim = lambda s: f"{Style.DIM}{s}{Style.NORMAL}"
bright = lambda s: f"{Style.BRIGHT}{s}{Style.NORMAL}"
red = lambda s: f"{Fore.RED}{s}{Fore.RESET}"
bright_red = lambda s: f"{Fore.RED}{Style.BRIGHT}{s}{Style.NORMAL}{Fore.RESET}"
yellow = lambda s: f"{Fore.YELLOW}{s}{Fore.RESET}"
bright_yellow = lambda s: f"{Fore.YELLOW}{Style.BRIGHT}{s}{Style.NORMAL}{Fore.RESET}"
green = lambda s: f"{Fore.GREEN}{s}{Fore.RESET}"
bright_green = lambda s: f"{Fore.GREEN}{Style.BRIGHT}{s}{Style.NORMAL}{Fore.RESET}"
indent = lambda s, l: " " * l + s
good = lambda s: green(f"✔ {s}")
info = lambda s: f"ℹ {s}"
warn = lambda s: yellow(f"⚠ {s}")
bad = lambda s: red(f"✖ {s}")
join = lambda l, sep, f: sep.join(f(s) for s in l)
blist = lambda l: join(l, ", ", bright)


def human(obj):
    if isinstance(obj, timedelta):
        secs = obj.total_seconds()
        mins = secs / 60.0
        hours = mins / 60.0

        if hours > 1.0:
            r = str(round(hours, 1))
            return f"{r if r[-1] != '0' else r[:-2]}h"

        if mins > 1.0:
            r = str(round(mins, 1))
            return f"{r if r[-1] != '0' else r[:-2]}m"

        elif secs > 1.0:
            r = str(round(secs, 1))
            return f"{r if r[-1] != '0' else r[:-2]}s"

        else:
            msecs = secs * 1000.0
            r = str(round(msecs, 1))
            return f"{r if r[-1] != '0' else r[:-2]}ms"
    elif isinstance(obj, datetime):
        return obj.strftime("%H:%M")
    elif isinstance(obj, str):
        return obj.replace("_", " ").title()
    else:
        return obj


class LogFormatter:
    def unhandled(self, event, context, stage, details):
        ignored = (
            "project_git_commit",
            "sayn_version",
            "project_name",
            "ts",
            "run_id",
            "task",
            "task_order",
            "total_tasks",
        )
        ctx = details["task"] if context == "task" else context
        return (
            f"Unhandled: {ctx}::{stage}::{event}:",
            {k: v for k, v in details.items() if k not in ignored},
        )

    # App context

    def app_start(self, details):
        debug = "(debug)" if details["run_arguments"]["debug"] else ""
        dt_range = (
            f"{details['run_arguments']['start_dt']} to {details['run_arguments']['end_dt']}"
            if not details["run_arguments"]["full_load"]
            else "Full Load"
        )
        out = list()
        out.append(f"Starting sayn {debug}")
        out.append(f"Run ID: {details['run_id']}")
        out.append(f"Project: {details['project_name']}")
        out.append(f"Sayn version: {details['sayn_version']}")
        if details["project_git_commit"] is not None:
            out.append(f"Git commit: {details['project_git_commit']}")
        out.append(f"Period: {dt_range}")
        out.append(
            f"{'Profile: ' + (details['run_arguments'].get('profile') or 'Default')}"
        )

        return out

    def app_finish(self, details):
        errors = details["tasks"].get("failed", list()) + details["tasks"].get(
            "skipped", list()
        )
        msg = f"Execution of SAYN took {human(details['duration'])}"
        return bad(msg) if len(errors) > 0 else good(msg)

    def app_stage_start(self, stage, details):
        if stage == "setup":
            return "Setting up..."
        elif stage in ("run", "compile"):
            return bright(f"Starting {stage} at {details['ts'].strftime('%H:%M')}...")
        else:
            return self.unhandled("start_stage", "app", stage, details)

    def app_stage_finish(self, stage, details):
        tasks = group_list([(v.value, t) for t, v in details["tasks"].items()])
        failed = tasks.get("failed", list())
        succeeded = tasks.get("ready", list()) + tasks.get("succeeded", list())
        skipped = tasks.get("skipped", list())
        duration = human(details["duration"])

        if stage == "setup":
            out = ["Finished setup:"]
            if len(failed) > 0:
                out.append(bad(f"Failed tasks: {blist(failed)}"))
            if len(skipped) > 0:
                out.append(warn(f"Tasks to skip: {blist(skipped)}"))
            if len(succeeded) > 0:
                out.append(green(f"Tasks to run: {blist(succeeded)}"))
            return out

        elif stage in ("run", "compile"):
            if len(failed) > 0 or len(skipped) > 0:
                out = [red(f"There were some errors during {stage} (took {duration})")]
                if len(failed) > 0:
                    out.append(bad(f"Failed tasks: {blist(failed)}"))
                if len(skipped) > 0:
                    out.append(warn(f"Skipped tasks: {blist(skipped)}"))
            else:
                return [
                    good(f"{stage.capitalize()} finished successfully in {duration}"),
                    f"Tasks executed: {blist(succeeded)}",
                ]

        else:
            return self.unhandled("finish_stage", "app", stage, details)

    # Task context

    def task_set_steps(self, details):
        return f"Run Steps: {blist(details['steps'])}"

    def task_stage_start(self, stage, task, task_order, total_tasks, details):
        task_progress = f"[{task_order}/{total_tasks}]"
        ts = human(details["ts"])

        if stage == "setup":
            return f"{task_progress} {bright(task)}"
        elif stage in ("run", "compile"):
            return bright(f"{task_progress} {task} ") + f"(started at {ts})"
        else:
            return self.unhandled("start_stage", "task", stage, details)

    def task_stage_finish(self, stage, task, task_order, total_tasks, details):
        duration = human(details["duration"])

        if details["result"].is_ok:
            return good(f"Finished {stage} for {bright(task)} ({duration})")
        else:
            return self.unhandled("finish_stage", "task", stage, details)

    def task_step_start(self, stage, task, step, step_order, total_steps, details):
        task_progress = f"[{step_order}/{total_steps}]"
        ts = f"[{human(details['ts'])}]"

        if stage in ("run", "compile"):
            return info(f"{task_progress} {ts} Executing {bright(step)} at ...")
        else:
            return self.unhandled("start_step", "task", stage, details)

    def task_step_finish(self, stage, task, step, step_order, total_steps, details):
        task_progress = f"[{step_order}/{total_steps}]"
        ts = f"[{human(details['ts'])}]"
        duration = human(details["duration"])

        if details["result"].is_ok:
            return good(f"{task_progress}" + f" {ts} {bright(step)} ({duration})")
        else:
            return self.unhandled("finish_step", "task", stage, details)


class Logger:
    def report_event(self, **event):
        raise NotImplementedError()


class ConsoleDebugLogger(Logger):
    fmt = LogFormatter()
    current_indent = 0

    def unhandled(self, event, context, stage, details):
        print(self.fmt.unhandled(event, context, stage, details))

    # App context

    def app_start(self, details):
        self.print(self.fmt.app_start(details))
        print()

    def app_finish(self, details):
        self.print(self.fmt.app_finish(details))

    def app_stage_start(self, stage, details):
        self.print(self.fmt.app_stage_start(stage, details))
        self.current_indent += 1

    def app_stage_finish(self, stage, details):
        self.current_indent -= 1
        self.print(self.fmt.app_stage_finish(stage, details))
        print()

    # Task context

    def task_stage_start(self, stage, task, task_order, total_tasks, details):
        self.print(
            self.fmt.task_stage_start(stage, task, task_order, total_tasks, details)
        )
        self.current_indent += 1

    def task_stage_finish(self, stage, task, task_order, total_tasks, details):
        self.current_indent -= 1
        self.print(
            self.fmt.task_stage_finish(stage, task, task_order, total_tasks, details)
        )

    def task_set_steps(self, details):
        self.print(self.fmt.task_set_steps(details))

    def task_step_start(self, stage, task, step, step_order, total_steps, details):
        self.print(
            self.fmt.task_step_start(
                stage, task, step, step_order, total_steps, details
            )
        )
        self.current_indent += 1

    def task_step_finish(self, stage, task, step, step_order, total_steps, details):
        self.current_indent -= 1
        self.print(
            self.fmt.task_step_finish(
                stage, task, step, step_order, total_steps, details
            )
        )

    def report_event(self, context, event, stage, **details):
        if context == "app":
            if event == "start_app":
                self.app_start(details)

            elif event == "finish_app":
                self.app_finish(details)

            elif event == "start_stage":
                self.app_stage_start(stage, details)

            elif event == "finish_stage":
                self.app_stage_finish(stage, details)

            else:
                self.unhandled(event, context, stage, details)

        elif context == "task":
            task = details["task"]
            task_order = details["task_order"]
            total_tasks = details["total_tasks"]

            if event == "set_run_steps":
                self.task_set_steps(details)

            elif event == "start_stage":
                self.task_stage_start(stage, task, task_order, total_tasks, details)

            elif event == "finish_stage":
                self.task_stage_finish(stage, task, task_order, total_tasks, details)

            elif event == "start_step":
                self.task_step_start(
                    stage,
                    task,
                    details["step"],
                    details["step_order"],
                    details["total_steps"],
                    details,
                )

            elif event == "finish_step":
                self.task_step_finish(
                    stage,
                    task,
                    details["step"],
                    details["step_order"],
                    details["total_steps"],
                    details,
                )

            else:
                self.unhandled(event, context, stage, details)

        else:
            self.unhandled(event, context, stage, details)

    def print(self, s):
        if isinstance(s, str):
            print("  " * self.current_indent + s)
        elif isinstance(s, list):
            print("  " * self.current_indent + s[0])
            for l in s[1:]:
                print("  " * self.current_indent + f"  {l}")
        else:
            raise ValueError("error in logging print")


class ConsoleLogger(Logger):
    # TODO refactor log formatter so that it's more useful here
    # formatter = LogFormatter("info", False)
    spinner = None
    text = None

    def report_event(self, level, event, stage, **kwargs):
        if event == "start_stage" and stage != "summary":
            self.spinner = Halo(spinner="dots")
            self.spinner.start(stage)

        elif event == "finish_stage" and stage == "setup":
            if level == "error":
                self.spinner.fail(
                    "\n    ".join(
                        (
                            f"{Fore.RED}{stage.capitalize()} ({human(kwargs['duration'])}):",
                            f"{Fore.RED}Some tasks failed during setup: {', '.join(kwargs['task_statuses']['failed'])}",
                            "",
                        )
                    )
                )
            elif level == "warning":
                self.spinner.warn(
                    "\n    ".join(
                        (
                            f"{Fore.YELLOW}{stage.capitalize()} ({human(kwargs['duration'])}):",
                            f"{Fore.RED}Some tasks failed during setup: {', '.join(kwargs['task_statuses']['failed'])}",
                            f"{Fore.YELLOW}Some tasks will be skipped: {', '.join(kwargs['task_statuses']['skipped'])}",
                            "",
                        )
                    )
                )
            else:
                self.spinner.succeed(
                    f"{stage.capitalize()} ({human(kwargs['duration'])})"
                )

        elif event == "start_task":
            self.spinner.text = f"{stage.capitalize()}: {kwargs['task']}"

        elif event == "finish_task":
            if level == "error":
                self.spinner.fail(
                    f"{stage.capitalize()}: {kwargs['task']} ({human(kwargs['duration'])})"
                )
            elif level == "warning":
                self.spinner.warn(
                    f"{stage.capitalize()}: {kwargs['task']} ({human(kwargs['duration'])})"
                )
            else:
                self.spinner.succeed(
                    f"{stage.capitalize()}: {kwargs['task']} ({human(kwargs['duration'])})"
                )

        elif event == "execution_finished":
            out = [
                ". ".join(
                    (
                        "" f"Process finished ({human(kwargs['duration'])})",
                        f"Total tasks: {len(kwargs['succeeded']+kwargs['skipped']+kwargs['failed'])}",
                        f"Success: {len(kwargs['succeeded'])}",
                        f"Failed {len(kwargs['failed'])}",
                        f"Skipped {len(kwargs['skipped'])}.",
                    )
                )
            ]

            for status in ("succeeded", "failed", "skipped"):
                if len(kwargs[status]) > 0:
                    out.append(
                        (
                            f"  The following tasks "
                            f"{'were ' if status == 'skipped' else ''}{status}: "
                            f"{', '.join(kwargs[status])}"
                        )
                    )

            colour = (
                Fore.GREEN
                if level == "success"
                else Fore.YELLOW
                if level == "warning"
                else Fore.RED
            )
            print()
            for line in out:
                print(f"{colour}{line}")


class FileLogger(Logger):
    # formatter = LogFormatter("debug", True)
    # logger = None

    def __init__(self, folder):
        pass

    #     from pathlib import Path
    #     import logging
    #     formatter = logging.Formatter("%(message)s")

    #     log_file = Path(folder, "sayn.log")
    #     if not log_file.parent.exists():
    #         log_file.parent.mkdir(parents=True)

    #     handler = logging.FileHandler(log_file)
    #     handler.setLevel(logging.DEBUG)
    #     handler.setFormatter(formatter)

    #     logger = logging.getLogger(__name__)
    #     logger.addHandler(handler)
    #     logger.setLevel(logging.DEBUG)

    #     self.logger = logger

    def report_event(self, **event):
        # TODO
        return
        for line in self.formatter.get_lines(**event):
            self.logger.debug(line)
