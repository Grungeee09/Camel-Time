from utils.file_operations import get_data, change_data
from gui.input_dialog import get_name
from gui.confirmation_dialog import ask_yes_or_no
from tkinter.messagebox import showerror, askyesno, showinfo
import psutil
import re
import threading
import time
import datetime
import globals


def add_tracked_process(process: str, name: str) -> bool:
    data: dict = get_data()

    if not re.match(r".*\..*", process):
        showerror("Error", "You have entered an invalid process")
        return False
    elif process in data["tracked"]:
        showerror("Error", "This process is already tracking")
        return False
    elif name in [other["display_name"] for other in data["tracked"].values()]:
        showerror("Error", "This display name is already taken")
        return False
    else:
        if process not in data["runned"]:
            def add_to_runned(data: dict) -> dict:
                data["runned"].append(process)
                return data
            change_data(add_to_runned)
        add_new_tracked_process(process, name)
        threading.Thread(target=check_all_tracked_programs).start()
        showinfo("Info", "This process has started to track")
        return True


def delete_tracked_process(string: str) -> bool:
    data: dict = get_data()
    redacted_string = string.replace(" ", "").lower()

    for process, other in data["tracked"].items():
        redacted_process: str = process.replace(" ", "").lower()
        redacted_display_name: str = other["display_name"].replace(" ", "").lower()

        if redacted_string == redacted_process or redacted_string == redacted_display_name:
            if askyesno("Confirmation",
                        "All process data including time will be permanently deleted. Are you sure?"):
                def delete(data: dict) -> dict:
                    del data["tracked"][process]
                    return data

                change_data(delete)
                return True

    showerror("Error", "This process is not tracked yet")
    return False


def handle_processes_queue() -> None:
    while not globals.requested_to_quit:
        if globals.new_processes_queue:
            for process, pid in set(globals.new_processes_queue.items()):
                on_new_process(pid, process)
                globals.new_processes_queue.pop(process)
        time.sleep(0.85)


def check_all_tracked_programs() -> None:
    data: dict = get_data()

    existing_processes: dict = {}
    for pid in psutil.pids():
        try:
            existing_processes[psutil.Process(pid).name()] = pid
        except psutil.NoSuchProcess:
            pass

    existing_processes_names: set = set(existing_processes.keys())

    for process, other in data["tracked"].items():
        pid: int | None = other["pid"]
        if pid is not None and psutil.pid_exists(pid):
            on_tracked_app_run(pid, process, restart_thread=True)
        elif pid is None and process in existing_processes_names:
            on_tracked_app_run(existing_processes[process], process)
        elif pid is not None and not psutil.pid_exists(pid):
            def reset_pid(data: dict) -> dict:
                data["tracked"][process]["pid"] = None
                return data

            change_data(reset_pid)


def add_time(pid: int, process: str) -> None:
    last_time = datetime.datetime.now()
    while psutil.pid_exists(pid) and not globals.requested_to_quit and process in get_data()["tracked"]:
        current_time = datetime.datetime.now()
        time_difference = current_time - last_time
        last_time = current_time

        def add_time(data: dict) -> dict:
            data["tracked"][process]["time"] = (
                round(time_difference.total_seconds() + data["tracked"][process]["time"], 3))
            data["tracked"][process]["last_run_time"] += int(time_difference.total_seconds())
            return data

        change_data(add_time)

        time.sleep(1)

    if not psutil.pid_exists(pid):
        def reset_pid(data: dict) -> dict:
            data["tracked"][process]["pid"] = None
            return data
        change_data(reset_pid)


def on_tracked_app_run(pid: int, process: str, restart_thread: bool = False) -> None:
    if get_data()["tracked"][process]["pid"] is None or restart_thread:
        def assign_pid(data: dict) -> dict:
            if not restart_thread:
                data["tracked"][process]["pid"] = pid
            data["tracked"][process]["last_run_time"] = int(time.time())
            return data

        change_data(assign_pid)
        threading.Thread(target=lambda: add_time(pid, process)).start()


def add_new_tracked_process(process: str, display_name: str) -> None:
    def add(data: dict):
        data["tracked"][process] = {"time": 0, "pid": None, "display_name": display_name, "last_run_time": 0}
        return data
    change_data(add)


def on_new_process(pid: int, process: str) -> None:
    answer = ask_yes_or_no("New process", f"Does this process need to be monitored:\n{process}?",
                           destroy_after=10, font_size=13)

    if answer:
        display_name = get_name(process, "Enter display name:", "Input name")
        if display_name:
            add_new_tracked_process(process, display_name)
            on_tracked_app_run(pid, process)


def check_new_processes() -> None:
    existing_processes = set(psutil.pids())

    while not globals.requested_to_quit:
        new_processes = set(psutil.pids()) - existing_processes
        for pid in new_processes:
            try:
                process = psutil.Process(pid)
                process_name = process.name()
                if process.username() != "SYSTEM":
                    data: dict = get_data()
                    if process_name in data["tracked"]:
                        threading.Thread(target=on_tracked_app_run, args=(pid, process_name)).start()
                    if process_name not in data["runned"]:
                        def append_to_runned(data: dict) -> dict:
                            data["runned"].append(process_name)
                            return data
                        change_data(append_to_runned)
                        globals.new_processes_queue[process_name] = pid
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            except Exception as e:
                showerror(str(e))

        existing_processes = set(psutil.pids())
        time.sleep(0.85)
