WELCOME_TEXT = f"""
 ██████╗ ██████╗ ██████╗ ███████╗██╗  ██╗
██╔════╝██╔═══██╗██╔══██╗██╔════╝╚██╗██╔╝
██║     ██║   ██║██║  ██║█████╗   ╚███╔╝ 
██║     ██║   ██║██║  ██║██╔══╝   ██╔██╗ 
╚██████╗╚██████╔╝██████╔╝███████╗██╔╝ ██╗
 ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝

Ashes Codex data grabber. v1.0
\033[0;32m-------------------------------------------------------\033[0m
\033[0;36m[1]\033[0m Scrape                  - Extract data from sources
\033[0;36m[2]\033[0m Initialize Database     - Set up the storage system
\033[0;36m[3]\033[0m Help                    - Get usage instructions
\033[0;36m[4]\033[0m Exit                    - Quit the application
"""

HELP_TEXT = f"""
If you require any assistance or there is an issue with the script, please open an issue on github, or do a PR.
You can also message me directly on discord @Mutim#0001
"""

VERIFY_TEXT = (f"\033[0;33mVerify that all information is correct in your .env file, then press ENTER\n"
               f"If you need to configure your file, please CTRL+C now!\033[0m\n")

ENV_CONTENT = """SUPABASE_URL = 'Replace Me! (Keep quotes to escape special characters)'
SUPABASE_KEY = 'Replace Me! (Keep quotes to escape special characters)'

ASHES_AUTH = 'Make this blank if you are not using it'
ASHES_KEY = ''

USER = 'postgres.{your_database}'
PASSWORD = ''
HOST = ''
PORT = '6543'
DBNAME = 'postgres'
"""
