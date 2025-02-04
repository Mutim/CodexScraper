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


def generate_numeric_guid(entry):
    entry_str = str(entry)
    hash_object = hashlib.md5(entry_str.encode())
    return int(hash_object.hexdigest(), 16) % (10**18)


def create_table(client):
    with open('sql/schemas.sql', 'r') as sql_file:
        schemas = sql_file.read()
    schema_sections = schemas.split('-- ###BREAK')
    table_create = schema_sections[0]
    response = client.postgrest.rpc("sql", {"query": table_create}).execute()

    if response.status_code == 200:
        print("Table created successfully!")
    else:
        print(f"Error creating table: {response.status_code}")


def scrape():
    sections = ["items", "mobs", "hunting-creatures", "npcs", "pois", "status-effects", "xp-tables"]

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
                    break
                except requests.exceptions.Timeout:
                    timeouts += 1
                    print(f"Request timed out on page {page} of section `{section}`. Retrying in 5 seconds...")
                    time.sleep(5)
                except postgrest.exceptions.APIError as e:
                    if e.code == "57014":  # Statement timeout
                        timeouts += 1
                        print(
                            f"POST to database timed out on page {page} of section `{section}`. Retrying in 5 seconds...")
                        time.sleep(5)
                    else:
                        exit(f"Unexpected API error: {e}")
            else:
                exit(f"Failed after 5 timeouts on page {page} of section `{section}`. Quitting...")

            # Handle error codes
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                print(f"Rate-limited. Retrying after {retry_after} seconds...")
                time.sleep(retry_after)
                continue

            if response.status_code != 200:
                print(f"Error fetching section `{section}`: HTTP {response.status_code}")
                return

            json_data = response.json()
            new_data = json_data.get("levelXpCurve", []) if section == "xp-tables" else json_data.get("data", [])

            if not new_data:
                print(f"No more data found for `{section}`. Moving to next section...")
                break

            entries = []
            for entry in new_data:
                entry['section'] = section
                guid = entry.get("guid") or generate_numeric_guid(entry)
                entry["guid"] = guid

                entries.append({
                    "guid": guid,
                    "section": section,
                    "data": entry
                })

            # Insert data into Supabase. This will handle known error codes. Open a ticket if you find another code
            #   that should be handled
            if entries:
                try:
                    res = supabase.table("codex").upsert(entries).execute()
                    if res.data:
                        print(f"Inserted/Updated {len(res.data)} entries for `{section}` page {page}.")
                    else:
                        print(f"No new data inserted for `{section}` on page {page}. Data may already exist.")
                except postgrest.exceptions.APIError as e:
                    if e.code == "57014":  # Statement timeout
                        print(
                            f"POST to database timed out on page {page} of section `{section}`. Retrying in 5 seconds...")
                        time.sleep(5)
                        res = supabase.table("codex").upsert(entries).execute()
                    if e.code == "23505":  # Duplicate key error
                        print(f"Duplicate GUID detected in `{section}` on page {page}. Skipping entry.")
                    else:
                        print(f"Unexpected API error while up-upsert section `{section}` on page {page}:\n{e}")

            print(f"Inserting page {page}, section `{section}` data in {time.time() - start_time:.2f} seconds.")
            page += 1
            time.sleep(0.25)
    print("Data Grabbing Complete!  --  Exiting program...")


if __name__ == "__main__":
    running = True
    print(config.WELCOME_TEXT)
    while running:
        option = input("Menu Option: > ")
        match option:
            case "1":
                input(config.VERIFY_TEXT)
                print("Running scrape...")
                scrape()
                running = False
            case "2":
                input(config.VERIFY_TEXT)
                create_table(Client)
                print("Running create table")
            case "3":
                print(config.HELP_TEXT)
            case "4":
                print("Exiting program...")
                running = False
                quit()
            case _:
                print("Invalid option, please try again.")
