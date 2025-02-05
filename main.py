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


import hashlib
import time
import os
import sys

import requests
from dotenv import load_dotenv
from supabase import create_client, Client
import postgrest
import psycopg2

import config


if not os.path.isfile(".env"):
    with open(".env", "w") as f:
        f.write(config.ENV_CONTENT)
    sys.exit("No valid .env file found! Creating one now... Please modify this to reflect your data.")
# Load the .env
load_dotenv()

# Supabase credentials -
# Found at https://supabase.com/dashboard/project/{your-database-url}/settings/api
SUPABASE_URL = os.getenv("SUPABASE_URL")  # URL For you supabase database
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Supabase API key
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Ashes information -
# This info is not needed, and can safely be left blank in your .env file.
# However, it is apparently needed when pulling user specific information from the site, such as custom markers.
ASHES_AUTH = os.getenv("ASHES_AUTH")  # 'Bearer token'
ASHES_KEY = os.getenv("ASHES_KEY")  # The API key that you send when you send a request to codex

# Database Information -
# Found at https://supabase.com/dashboard/project/{your-database-url}/editor?showConnect=true
USER = os.getenv("USER")
PASSWORD = os.getenv("PASSWORD")
HOST = os.getenv("HOST")
PORT = os.getenv("PORT")
DBNAME = os.getenv("DBNAME")


def create_table():
    print("Attempting connection...")
    try:
        with psycopg2.connect(
            user=USER,
            password=PASSWORD,
            host=HOST,
            port=PORT,
            dbname=DBNAME
        ) as connection:
            print("Connection successful!")
            with connection.cursor() as cursor:
                with open('sql/schemas.sql', 'r') as sql_file:
                    schemas = sql_file.read().strip()
                    schema_sections = schemas.split('-- ###BREAK')
                    table_create = schema_sections[1]

                if not table_create:
                    print("Error: SQL Query is empty!")
                    return

                cursor.execute(table_create)
                connection.commit()
                print("Table Successfully Created!")

    except psycopg2.Error as e:
        print(f"Database error: {e}")


def retry_upsert(entries, section, page):
    max_retries = 5
    retry_count = 0
    backoff = 2

    while retry_count < max_retries:
        try:
            res = supabase.table("codex").upsert(entries).execute()

            if res.data:

                print(f"Created or Updated | {len(res.data)} "
                      f"total entries for \033[0;32m`{section}`\033[0m page {page}.")
            else:
                print(f"No new data inserted for `{section}` on page {page}. Data may already exist.")

            return True

        except postgrest.exceptions.APIError as e:
            error_code = str(getattr(e, "code", "N/A"))
            if error_code == "57014":  # Statement timeout
                print(
                    f"\033[0;33mError 57014: POST to database timed out on page {page} of section `{section}`.\033[0m"
                    f"Retrying in {backoff} seconds...")
                time.sleep(backoff)
                retry_count += 1
                backoff *= 2
            elif error_code == "23505":  # Duplicate key error
                print(f"\033[0;33mError 23505: Duplicate GUID detected in `{section}` on page {page}. Skipping entry.\033[0m")
                return False
            elif error_code == "520":  # JSON could not be generated
                print(
                    f"\033[0;33mError 520: JSON object could not be generated for `{section}` on page {page}.\033[0m"
                    f"Object is too large...")
                return False
            elif error_code == "21000":  # ON CONFLICT DO UPDATE affecting row twice
                print(f"\033[0;33mError 21000: ON CONFLICT DO UPDATE command cannot affect row a second time. Skipping entry.")
                return False
            elif error_code == "23502":  # ON CONFLICT DO UPDATE affecting row twice
                print(f"\033[0;33mError 23502: Missing GUID in entry. Skipping entry.\033[0m")
                return False
            else:
                print(f"\033[0;33mUnexpected API error while upsert section `{section}` on page {page}:\033[0m\n{e}")
                cont = input(f"\nPlease report: {e.code} as message: {e.hint}. "
                             f"Type 'exit' to quit, or press ENTER to continue.\n > ")
                if not cont.lower() == "exit":
                    return False
                sys.exit(f"\033[0;33mDB has been force closed with errors.\033[0m")
        if retry_count >= max_retries:
            print(f"Max retries reached for page {page} of section `{section}`. Skipping.")
            return False

    return False


def scrape():
    # Removed xp-tables. The data is all over the place, and has no structure. Lists, lists of objects, objects of list.
    sections = ["items", "mobs", "abilities", "hunting-creatures", "npcs", "pois", "status-effects"]

    params = {
        "select": "data",
        "id": "",
        "limit": 1
    }

    headers = {
        "apikey": ASHES_KEY,
        "Authorization": ASHES_AUTH,
        "Accept": "application/json",
    }

    for section in sections:

        page = 1

        print(f"---------- Starting Section `{section}` on page {page}. ----------")

        while True:
            timeouts = 0
            start_time = time.time()
            url = f"https://api.ashescodex.com/{section}?page={page}"

            while timeouts <= 5:
                try:
                    response = requests.get(url, headers=headers, params=params, timeout=30)

                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        print(f"Rate-limited. Retrying after {retry_after} seconds...")
                        time.sleep(retry_after)
                        continue
                    break
                except requests.exceptions.Timeout:
                    timeouts += 1
                    print(f"Request timed out on page {page} of section `{section}`. Retrying in 5 seconds...")
                    time.sleep(5)
            else:
                print(f"Failed after 5 timeouts on page {page} of section `{section}`. Skipping...")
                continue

            if response.status_code != 200:
                print(f"Error fetching section `{section}`: HTTP {response.status_code}")
                return

            json_data = response.json()
            new_data = json_data.get("data", [])

            if not new_data:
                print(f"No more data found for `{section}`. Moving to next section...")
                break

            entries = []
            _slug_entries = ["mobs", "hunting-creatures"]
            for entry in new_data:
                if section in _slug_entries:
                    guid = entry.get("_slug")
                else:
                    #  This is an ugly workaround. Will have to fix it when everything has a guid or _id
                    guid = entry.get("guid") or entry.get("_id") or entry.get("displayName")

                entry['guid'] = guid
                entry['section'] = section

                entries.append({
                    "guid": guid,
                    "section": section,
                    "data": entry
                })

            # Insert data into Supabase. This will handle known error codes. Open a ticket if you find another code
            #   that should be handled
            if entries:
                for entry in entries:
                    if not entry.get('guid'):
                        print(f"Missing GUID in entry: {entry}")
                success = retry_upsert(entries, section, page)
                if not success:
                    print(f"Failed to handle entries for section `{section}` page {page}.")

            print(f"Inserting page {page}, section `{section}` data in {time.time() - start_time:.2f} seconds.")
            page += 1
            time.sleep(0.25)
    print("Data Grabbing Complete!  --  Exiting program...")


if __name__ == "__main__":
    running = True
    print(config.WELCOME_TEXT)
    while running:
        option = input("\nMenu Option: > ")
        match option:
            case "1":
                input(config.VERIFY_TEXT)
                scrape()
                running = False
            case "2":
                input(config.VERIFY_TEXT)
                create_table()
            case "3":
                print(config.HELP_TEXT)
            case "4":
                print("Exiting program...")
                running = False
                quit()
            case _:
                print("Invalid option, please try again.")
