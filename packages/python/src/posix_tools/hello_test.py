from posix_tools.hello import hello


def describe_hello() -> None:
    def it_greets() -> None:
        assert hello() == "hello, world"
