import json
import os
import sys
import time

import requests

import postgrest
import psycopg2

from tools import program_tools
from tools.program_tools import Info, load_config

__all__ = (
    'create_table',
    'scrape',
    'scrape_to_json'
)


def create_table():
    if not all([Info.host, Info.user, Info.password]):
        raise RuntimeError("Database configuration not loaded properly!")

    print(f"Attempting connection to: host={Info.host} port={Info.port} user={Info.user}")
    try:
        with psycopg2.connect(
                user=Info.user,
                password=Info.password,
                host=Info.host,
                port=Info.port
        ) as connection:
            print("Connection successful!")
            with connection.cursor() as cursor:
                with open('sql/schemas.sql', 'r') as sql_file:
                    schemas = sql_file.read().strip()
                    schema_sections = schemas.split('-- ###BREAK')
                    table_create = schema_sections[1]

                if not table_create:
                    print("Error: SQL Query is empty!")
                    return False

                cursor.execute(table_create)
                connection.commit()
                print("Table Successfully Created!")
                return True

    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return False


def retry_upsert(entries, section, page):
    s_base = program_tools.get_supabase_client()
    max_retries = 5
    retry_count = 0
    backoff = 2

    while retry_count < max_retries:
        try:
            res = s_base.table("codex").upsert(entries).execute()

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
                    f"\033[0;33mError 57014: POST to database timed out on page {page} of section `{section}`. \033[0m"
                    f"Retrying in {backoff} seconds...")
                time.sleep(backoff)
                retry_count += 1
                backoff *= 2
            elif error_code == "23505":  # Duplicate key error
                print(f"\033[0;33mError 23505: Duplicate GUID detected in `{section}` on page {page}. "
                      f"Skipping entry.\033[0m")
                return False
            elif error_code == "520":  # JSON could not be generated
                print(
                    f"\033[0;33mError 520: JSON object could not be generated for `{section}` on page {page}."
                    f"Object is too large...\033[0m")
                return False
            elif error_code == "21000":  # ON CONFLICT DO UPDATE affecting row twice
                print(f"\033[0;33mError 21000: ON CONFLICT DO UPDATE command cannot affect row a second time. "
                      f"Skipping entry.\033[0m")
                return False
            elif error_code == "23502":  # Missing GUID in entry
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
    config = load_config(program_tools.CONFIG_FILE)

    if not Info.ashes_key or not Info.ashes_auth:
        print("\033[0;33mAshes Key or Auth Token is missing. May be required in the future\033[0m\n")

    # Removed xp-tables. The data is all over the place, and has no structure. Lists, lists of objects, objects of list.
    sections = config["SECTIONS"]

    params = {
        "select": "data",
        "id": "",
        "limit": 1
    }

    headers = {
        "apikey": Info.ashes_key or "no-api-key-needed",
        "Authorization": Info.ashes_auth or "Bearer none",
        "Accept": "application/json",
        "User-Agent": f"CodexScraper/{config['VERSION']}",
        "X-Request-Source": "Discord-Mutim@0001"
    }

    for section in sections:

        page = 1

        print(f"---------- Starting Section `{section}` on page {page}. ----------")

        while True:
            timeouts = 0
            start_time = time.time()
            url = f"https://api.ashescodex.com/{section}?page={page}"
            timeout_time = 30
            if section == "npcs":
                timeout_time = 60

            while timeouts <= 5:
                try:
                    response = requests.get(url, headers=headers, params=params, timeout=timeout_time)

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
            # that should be handled
            if entries:
                for entry in entries:
                    if not entry.get('guid'):
                        print(f"Missing GUID in entry: {entry}")
                success = retry_upsert(entries, section, page)
                if not success:
                    print(f"Failed to handle entries for section `{section}` page {page}.")

            print(f"Inserting page \033[0;32m{page}\033[0m, section `{section}` data in {time.time() - start_time:.2f} seconds.")
            page += 1
            time.sleep(0.25)
    input("\033[0;32mData Grabbing Complete!  --  Press ENTER to return to Main Menu...\033[0m\n")


def scrape_to_json():
    config = load_config(program_tools.CONFIG_FILE)
    output_dir = "data"

    if not Info.ashes_key or not Info.ashes_auth:
        print("\033[0;33mAshes Key or Auth Token is missing. May be required in the future\033[0m\n")

    os.makedirs(output_dir, exist_ok=True)

    sections = config["SECTIONS"]
    params = {
        "select": "data",
        "id": "",
        "limit": 1
    }

    headers = {
        "apikey": Info.ashes_key or "no-api-key-needed",
        "Authorization": Info.ashes_auth or "Bearer none",
        "Accept": "application/json",
        "User-Agent": f"CodexScraper/{config['VERSION']}",
        "X-Request-Source": "Discord-Mutim@0001"
    }

    for section in sections:
        page = 1
        all_section_data = []
        print(f"---------- Starting Section `{section}` on page {page}. ----------")

        while True:
            timeouts = 0
            start_time = time.time()
            url = f"https://api.ashescodex.com/{section}?page={page}"
            timeout_time = 30
            if section == "npcs":
                timeout_time = 60

            while timeouts <= 5:
                try:
                    response = requests.get(url, headers=headers, params=params, timeout=timeout_time)

                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        print(f"Rate-limited. Retrying after {retry_after} seconds...")
                        time.sleep(retry_after)
                        continue
                    break
                except requests.exceptions.Timeout:
                    timeouts += 1
                    print(f"Request timed out on page {page}. Retrying in 5 seconds...")
                    time.sleep(5)
            else:
                print(f"\033[0;31mFailed after 5 timeouts. Skipping section `{section}`...\033[0m")
                break

            if response.status_code != 200:
                print(f"\033[0;31mError fetching section `{section}`: HTTP {response.status_code}\033[0m")
                break

            json_data = response.json()
            new_data = json_data.get("data", [])

            if not new_data:
                print(f"No more data found for `{section}` (page {page})\nWriting data, please wait...")
                break

            for entry in new_data:
                if section in ["mobs", "hunting-creatures"]:
                    guid = entry.get("_slug")
                else:
                    guid = entry.get("guid") or entry.get("_id") or entry.get("displayName")

                processed_entry = {
                    "guid": guid,
                    "section": section,
                    "data": entry
                }
                all_section_data.append(processed_entry)

            print(f"Processed page \033[0;32m{page}\033[0m in {time.time() - start_time:.2f}s")
            page += 1
            time.sleep(0.25)

        if all_section_data:
            fname = f"{output_dir}/{section}.json"
            with open(fname, 'w', encoding='utf-8') as f:
                json.dump(all_section_data, f, indent=2, ensure_ascii=False)
            print(f"\033[0;32mSaved {len(all_section_data)} entries to {fname}\033[0m")
        else:
            print(f"\033[0;33mNo data saved for section `{section}`\033[0m")

    print(f"\n\033[0;32mScraping complete! JSON files saved to {output_dir}/\033[0m")
    input("Press ENTER to return to main menu...")
