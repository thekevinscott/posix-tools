import asyncio


def describe_the_host_shell():
    async def it_runs_a_real_posix_pipeline():
        proc = await asyncio.create_subprocess_exec(
            "sh",
            "-c",
            "printf 'b\\na\\n' | sort",
            stdout=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()

        assert proc.returncode == 0
        assert stdout == b"a\nb\n"

    async def it_reports_a_nonzero_exit_status():
        proc = await asyncio.create_subprocess_exec("sh", "-c", "exit 3")

        assert await proc.wait() == 3
