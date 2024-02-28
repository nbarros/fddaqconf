
def add_thread_pinning_to_boot(system_data, thread_pinning_file, path):
    after = thread_pinning_file['after']
    file  = thread_pinning_file['file']
    from pathlib import Path
    from os.path import expandvars
    resolved_thread_pinning_file = Path(expandvars(file)).expanduser()

    if not resolved_thread_pinning_file.is_absolute():
        resolved_thread_pinning_file = path / resolved_thread_pinning_file

    if not resolved_thread_pinning_file.exists():
        raise RuntimeError(f'Cannot find the file {file} ({resolved_thread_pinning_file})')

    if not system_data['boot'].get('scripts'):
        system_data['boot']['scripts'] = {}
        key = "thread_pinning_0"
    else:
        numbers = [0]
        for script in system_data['boot']['scripts'].keys():
            if not script.startswith('thread_pinning_'):
                continue
            numbers += [int(script.split('_')[-1])]

        numbers.sort()
        number = numbers[-1]+1
        key = f"thread_pinning_{number}"

    for data in system_data['boot']['scripts'].values():
        if data.get('after', '') == after:
            raise RuntimeError(f'Already specified a pinning script for after \'{after}\'')

    system_data['boot']['scripts'][key] = {
        "after": after,
        "cmd": [
            "readout-affinity.py --pinfile ${DUNEDAQ_THREAD_PIN_FILE}"
        ],
        "env": {
            "DUNEDAQ_THREAD_PIN_FILE": resolved_thread_pinning_file.resolve().as_posix(),
            "LD_LIBRARY_PATH": "getenv",
            "PATH": "getenv"
        }
    }
