WELCOME_TEXT = f"""
 ██████╗ ██████╗ ██████╗ ███████╗██╗  ██╗
██╔════╝██╔═══██╗██╔══██╗██╔════╝╚██╗██╔╝
██║     ██║   ██║██║  ██║█████╗   ╚███╔╝ 
██║     ██║   ██║██║  ██║██╔══╝   ██╔██╗ 
╚██████╗╚██████╔╝██████╔╝███████╗██╔╝ ██╗
 ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝

Ashes Codex data grabber.

[1] Initialize Database     - Set up the storage system
[2] Scrape                  - Extract data from sources
[3] Help                    - Get usage instructions
[4] Exit                    - Quit the application

"""

HELP_TEXT = f"""
If you require any assistance or there is an issue with the script, please open an issue on github, or do a PR.
You can also message me directly on discord @Mutim#0001
"""

VERIFY_TEXT = (f"Verify that all information is correct in your .env file, then press ENTER\n"
               f"If you need to configure your file, please CTRL+C now!")

ENV_CONTENT = """SUPABASE_URL = 'Replace Me! (Keep quotes to escape special characters)'
SUPABASE_KEY = 'Replace Me! (Keep quotes to escape special characters)'

ASHES_AUTH = 'This can safely be left blank like the key below'
ASHES_KEY = ''
"""
