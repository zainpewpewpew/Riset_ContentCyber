"""Helper script to get WhatsApp group IDs from your account.

Run this locally (not in GitHub Actions) to find your group IDs:

    $env:GREEN_API_INSTANCE_ID = "your_instance_id"
    $env:GREEN_API_TOKEN = "your_api_token"
    python scripts/get_groups.py
"""

import os
import sys

import requests


def main():
    instance_id = os.environ.get("GREEN_API_INSTANCE_ID", "")
    api_token = os.environ.get("GREEN_API_TOKEN", "")

    if not instance_id or not api_token:
        print("ERROR: Set GREEN_API_INSTANCE_ID and GREEN_API_TOKEN environment variables")
        print()
        print("  Windows (PowerShell):")
        print('    $env:GREEN_API_INSTANCE_ID = "your_instance_id"')
        print('    $env:GREEN_API_TOKEN = "your_api_token"')
        print()
        print("  Linux/Mac:")
        print('    export GREEN_API_INSTANCE_ID="your_instance_id"')
        print('    export GREEN_API_TOKEN="your_api_token"')
        sys.exit(1)

    print("Fetching groups...\n")

    url = f"https://api.green-api.com/waInstance{instance_id}/getChats/{api_token}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        chats = response.json()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    groups = [c for c in chats if c.get("id", "").endswith("@g.us")]

    if not groups:
        print("No groups found on this WhatsApp account.")
        return

    print(f"Found {len(groups)} groups:\n")
    print(f"{'Group ID':<45} {'Group Name'}")
    print("-" * 80)

    for group in groups:
        group_id = group.get("id", "N/A")
        group_name = group.get("name", "N/A")
        clean_name = "".join(c for c in group_name if c.isprintable())
        print(f"{group_id:<45} {clean_name}")

    print()
    print("Copy the Group ID(s) you want and add them to WA_RECIPIENTS.")
    print("Format: one ID per line, e.g.:")
    print()
    print("  6281234567890@c.us")
    print("  120363194020948049@g.us")


if __name__ == "__main__":
    main()
