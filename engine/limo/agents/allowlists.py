WRITE_AGENT = ("read_file", "list_files", "grep", "read_ref", "write_file", "run_command")

ALLOWLISTS: dict[str, tuple[str, ...]] = {
    "architecture": WRITE_AGENT,
    "spec": WRITE_AGENT,
    "plan": WRITE_AGENT,
    "close": WRITE_AGENT,
    "build": ("read_file", "read_ref", "write_file", "run_command"),
    "verify": ("read_file", "list_files", "grep", "read_ref", "run_command"),
    "resolver": ("read_file", "list_files", "grep", "host_query"),
}
