import os

__all__ = (
    'clear',
)


def clear():
    # Clear command for Windows
    if os.name == 'nt':
        os.system('cls')
    # Clear command for Linux or macOS
    else:
        os.system('clear')
