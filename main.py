"""

CodexScraper  v1.0


Example API call: https://api.ashescodex.com/items?page=1

This program is designed to interact with the Ashes Codex API, fetch data, and insert it into a Supabase database.

Functions:
1. create_table(client): Creates a table in the Supabase database using a schema defined in 'sql/schemas.sql'.
2. scrape(): Scrapes data from various sections of the Ashes Codex API and inserts it into the Supabase database.
    Handles retries and rate limiting.
3. Main execution loop: A CLI interface that allows the user to choose options,
    such as running the scrape process, creating a table, or exiting the program.

Functionality:
- The `create_table` function reads a schema from a file and uses the Supabase client to execute the SQL query.
- The `scrape` function retrieves data from multiple sections of the Ashes Codex API, handles timeouts,
    retries on errors, and performs rate-limiting management. The data is upserted into the 'codex' table in Supabase.
- The user is prompted for input to choose between options: scraping data, creating a table, or exiting.

Error Handling:
- The program handles errors during API requests, including timeouts, rate limiting (HTTP 429),
    and duplicate data entries (HTTP 23505).
- Unexpected API errors will cause the program to exit with an error message.

Notes:
- Ensure your Supabase credentials are correctly configured in your environment for smooth interaction.
- Python >= 3.9 or higher is recommended for optimal compatibility.

Requirements:
- `requests` library for making HTTP requests.
- `dotenv` Used to load and save to your .env file
- `supabase` Will handle the connection to your supabase database. (Min python version Python >= 3.9)
- `postgrest` For interacting with the Supabase RESTful API.

Example Usage:
Run the script, and it will automatically process all the sections and store the data in your supabase database! Ensure
that you have updated your .env file.

"""
import os
import sys

from dotenv import load_dotenv
import colorama

from tools import program_tools, table_tools, terminal_tools
from tools.program_tools import Info
config = program_tools.load_config(program_tools.CONFIG_FILE)

# If no .env file, we create one.
if not os.path.isfile(".env"):
    with open(".env", "w") as f:
        f.write(config["ENV_CONTENT"])
    sys.exit("No valid .env file found! Creating one now... Please modify this to reflect your data.")

load_dotenv(override=True)
Info.refresh()

# Validate info is correctly loaded after loading vars
try:
    Info.validate()
except ValueError as e:
    sys.exit(f"Configuration error while validating system variables: {e}")


def configure_sections():
    configuring = True
    section_list = list(config["TEXTS"]["SECTION_TEXT"].items())  # List of (section, section_name) pairs
    while configuring:
        terminal_tools.clear()
        print(config["TEXTS"]["BANNER"])

        for i, (section, section_name) in enumerate(section_list):
            is_in_sections = '✔' if section in config["SECTIONS"] else ' '
            print(f"\033[0;36m[{i + 1}]\033[0m {section_name}: {' ' * (25 - len(section_name))}[{is_in_sections} ]")

        print(f"\n\033[0;36m[0]\033[0m Return")

        toggle_section = input(f"\nMenu Option: > ")
        if toggle_section == "0":
            configuring = False
        try:
            section_index = int(toggle_section) - 1
            if 0 <= section_index < len(section_list):
                section = section_list[section_index][0]

                if section in config["SECTIONS"]:
                    config["SECTIONS"].remove(section)
                else:
                    config["SECTIONS"].append(section)

                program_tools.update_config(config)
            else:
                if section_index != -1:  # Checking if selection is 0, everything else will fail
                    input(f"\033[0;31mInvalid option. Press ENTER to continue.\033[0m")
        except (ValueError, IndexError):
            print("\033[0;31mInvalid option, please try again.\033[0m")


def configure_database():
    configuring = True
    env_vars = {
        "HOST": "Database Host",
        "PORT": "Database Port (default: 5432)",
        "USER": "Database Username",
        "PASSWORD": "Database Password",
        "SUPABASE_URL": "Supabase Project URL",
        "SUPABASE_KEY": "Supabase API Key"
    }

    initial_values = {var: os.getenv(var, "") for var in env_vars.keys()}
    current_values = initial_values.copy()
    has_changes = False

    while configuring:
        terminal_tools.clear()
        print(config["TEXTS"]["BANNER"])

        for i, (var, desc) in enumerate(env_vars.items(), 1):
            value = current_values[var]
            display_value = ("*" * 12) if var == "PASSWORD" and value else f"{value[:15]}..." if len(value) > 18 else value
            print(f"\033[0;36m[{i}]\033[0m {desc:40} \033[0;33m{display_value or '<not set>'}\033[0m")

        color_code = program_tools.COLOR_CODES["GREEN"] if has_changes else program_tools.COLOR_CODES["RESET"]
        print(f"\n\033[0;36m[s]\033[0m {color_code}Save configuration\033[0m")
        print(f"\033[0;36m[0]\033[0m Return without saving")

        choice = input(f"\nMenu Option: > ")
        if choice == "0":
            if has_changes:
                confirm = input("\033[0;33mDiscard changes? (y/n): \033[0m")
                if confirm.lower() != 'y':
                    continue
            return False
        elif choice == "s":
            if not has_changes:
                input("\033[0;36mNo changes to save. Press ENTER to continue.\033[0m")
                continue
            with open(".env", "w") as f:
                for var, value in current_values.items():
                    if value:
                        f.write(f"{var}='{value}'\n")
            print("\033[0;32mConfiguration saved to .env file!\033[0m")
            input("Press ENTER to continue...")
            return True
        elif choice.isdigit() and 1 <= int(choice) <= len(env_vars):
            selected_var = list(env_vars.keys())[int(choice) - 1]
            new_val = input(f"\nEnter new value for {env_vars[selected_var]}: ").strip()

            if new_val:
                current_values[selected_var] = new_val
                has_changes = current_values != initial_values
            if new_val.lower() == "none":
                return True
            current_values[selected_var] = new_val
        else:
            input(f"\033[0;31mInvalid option. Press ENTER to continue.\033[0m")


def configure_method():
    configuring = True
    options = ["DB", "JSON"]
    while configuring:
        terminal_tools.clear()
        print(config["TEXTS"]["BANNER"])

        for i, option in enumerate(options):
            is_in_sections = '✔' if option in config["SCRAPE_METHOD"] else ' '
            print(f"\033[0;36m[{i + 1}]\033[0m {option}: {' ' * (25 - len(option))}[{is_in_sections} ]")

        print(f"\n\033[0;36m[0]\033[0m Return")

        choice = input(f"\nMenu Option: > ")
        if choice == "0":
            configuring = False
        elif choice in ("1", "2"):
            selected_method = options[int(choice) - 1]
            if config["SCRAPE_METHOD"] != selected_method:
                config["SCRAPE_METHOD"] = selected_method
                program_tools.update_config(config)
        else:
            input(f"\033[0;31mInvalid option. Press ENTER to continue.\033[0m")


def configure():
    configuring = True
    while configuring:
        terminal_tools.clear()
        print(config["TEXTS"]["BANNER"])
        print(config["TEXTS"]["CONFIGURATION_TEXT"])
        opt = input("\nMenu Option: > ")
        match opt:
            case "1":  # Sections
                configure_sections()
            case "2":  # Configure Database
                configure_database()
            case "3":  # Scrape Method
                configure_method()
            case "0":  # Exit
                configuring = False
            case _:
                print("Invalid Option")


# TODO: Set this to run in it's own thread so we can listen for keystrokes and stop the program cleanly.
if __name__ == "__main__":
    # Colorama will set up systems to accept colorful terminals
    colorama.init()
    running = True
    while running:
        terminal_tools.clear()
        print(config["TEXTS"]["BANNER"])
        print(config["TEXTS"]["WELCOME_TEXT"])
        option = input("\nMenu Option: > ")
        scrape_meth = config["SCRAPE_METHOD"]
        match option:
            case "1":  # Scrape
                input(config["TEXTS"]["VERIFY_TEXT"])
                if config["SCRAPE_METHOD"] == "DB":
                    table_tools.scrape()
                elif config["SCRAPE_METHOD"] == "JSON":
                    table_tools.scrape_to_json()
                else:
                    input(f"\033[0;31mInvalid Configuration Option. Expected DB or JSON, "
                          f"received {scrape_meth} Press ENTER to configure.\033[0m")
                    configure()
            case "2":  # Initialize Database
                input(config["TEXTS"]["VERIFY_TEXT"])
                configured = table_tools.create_table()
                input(f"Database was {'not ' if not configured else ''}properly configured!")
            case "3":  # Config
                configure()
            case "4":  # Help
                input(config["TEXTS"]["HELP_TEXT"])
            case "0":  # Exit
                print("Exiting program...")
                running = False
            case _:
                print("Invalid option, please try again.")
