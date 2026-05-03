"""Helper script to get WhatsApp group IDs from your account.

Run this locally (not in GitHub Actions) to find your group IDs:

    export GREEN_API_INSTANCE_ID="your_instance_id"
    export GREEN_API_TOKEN="your_api_token"
    python scripts/get_groups.py

The output will show all groups with their IDs. Use these IDs
in the WA_RECIPIENTS secret.
"""

import os
import sys

from whatsapp_api_client_python import API


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

    client = API.GreenAPI(instance_id, api_token)

    print("Fetching groups...\n")

    try:
        response = client.groups.getGroups()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    if response.code != 200:
        print(f"ERROR: API returned status {response.code}")
        print(response.data)
        sys.exit(1)

    groups = response.data
    if not groups:
        print("No groups found on this WhatsApp account.")
        return

    print(f"Found {len(groups)} groups:\n")
    print(f"{'Group ID':<45} {'Group Name'}")
    print("-" * 80)

    for group in groups:
        group_id = group.get("id", "N/A")
        group_name = group.get("name", group.get("subject", "N/A"))
        print(f"{group_id:<45} {group_name}")

    print()
    print("Copy the Group ID(s) you want and add them to WA_RECIPIENTS.")
    print("Format: one ID per line, e.g.:")
    print()
    print("  6281234567890@c.us")
    print("  120363194020948049@g.us")


if __name__ == "__main__":
    main()
