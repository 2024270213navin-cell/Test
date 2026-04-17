"""
scripts/generate_sample_kb.py — Generates a sample knowledge-base Excel file for testing.

Run:
    python scripts/generate_sample_kb.py
Output:
    data/knowledge_base/sample_kb.xlsx
"""
from pathlib import Path
import pandas as pd

RECORDS = [
    {
        "Category": "VPN",
        "Question": "How do I reset my VPN password?",
        "Response": (
            "To reset your VPN password:\n"
            "1. Navigate to https://vpn-portal.company.com\n"
            "2. Click 'Forgot Password' on the login page\n"
            "3. Enter your corporate email address\n"
            "4. Follow the link in the reset email (valid 15 minutes)\n"
            "5. Set a new password meeting policy requirements (12+ chars, mixed case, number, symbol)\n"
            "6. Reconnect your VPN client with the new credentials."
        ),
        "Reference Information": "KB0001 | VPN Policy v3.2",
    },
    {
        "Category": "VPN",
        "Question": "VPN client cannot connect — error code 619",
        "Response": (
            "Error 619 indicates a firewall or port block. Resolution steps:\n"
            "1. Ensure UDP 500 and 4500 are not blocked by your local firewall\n"
            "2. Disable any third-party security software temporarily\n"
            "3. Restart the VPN client service: Services → Cisco AnyConnect → Restart\n"
            "4. If on hotel/public Wi-Fi, try using a mobile hotspot instead\n"
            "5. Raise an incident if the issue persists on corporate network."
        ),
        "Reference Information": "KB0002 | Network Firewall Guide",
    },
    {
        "Category": "Email",
        "Question": "Outlook is not synchronising emails",
        "Response": (
            "Steps to fix Outlook synchronisation:\n"
            "1. Check your internet connectivity\n"
            "2. In Outlook: File → Account Settings → Repair your Exchange account\n"
            "3. Remove and re-add your account if repair fails\n"
            "4. Clear the Offline Folder cache: File → Account Settings → Data Files → Settings → Compact Now\n"
            "5. If using Cached Exchange Mode, disable it temporarily via File → Account Settings → Change → tick/untick\n"
            "6. Run Outlook in safe mode: Win+R → `outlook /safe`"
        ),
        "Reference Information": "KB0010 | Outlook Troubleshooting",
    },
    {
        "Category": "Email",
        "Question": "How do I set up an out-of-office auto-reply?",
        "Response": (
            "To configure Out of Office in Outlook:\n"
            "1. File → Automatic Replies (Out of Office)\n"
            "2. Select 'Send automatic replies'\n"
            "3. Optionally set a date range\n"
            "4. Type your internal message (for colleagues)\n"
            "5. Click 'Outside My Organisation' tab and type the external message\n"
            "6. Click OK to activate."
        ),
        "Reference Information": "KB0011 | Email Policies",
    },
    {
        "Category": "Hardware",
        "Question": "My laptop keyboard has stopped working",
        "Response": (
            "Keyboard troubleshooting steps:\n"
            "1. Restart the laptop — temporary driver faults are common\n"
            "2. Check Device Manager for keyboard driver errors (yellow triangle)\n"
            "3. Uninstall and reinstall the HID Keyboard Device driver\n"
            "4. Try an external USB keyboard to isolate hardware vs software fault\n"
            "5. If hardware failure is confirmed, submit a Hardware Replacement Request via the Service Portal\n"
            "6. Provide asset tag, department code, and manager approval in the request."
        ),
        "Reference Information": "KB0020 | Hardware Replacement SLA",
    },
    {
        "Category": "Hardware",
        "Question": "How do I request a second monitor?",
        "Response": (
            "To request additional hardware:\n"
            "1. Log in to the Self-Service Portal: https://itsm.company.com\n"
            "2. Browse Catalogue → Hardware → Monitor Request\n"
            "3. Select the approved model (27\" Dell P2723 is standard)\n"
            "4. Enter your cost centre code and manager's email for approval\n"
            "5. Expected delivery: 5–10 business days after approval\n"
            "6. IT will email you once the monitor is at your desk."
        ),
        "Reference Information": "KB0021 | Hardware Catalogue 2024",
    },
    {
        "Category": "Password / Access",
        "Question": "I am locked out of my Active Directory account",
        "Response": (
            "AD account lockout resolution:\n"
            "1. Call the IT Help Desk (ext. 5000) for immediate unlock — no self-service for AD lockout\n"
            "2. Provide your employee ID for identity verification\n"
            "3. The agent will unlock your account and force a password reset\n"
            "4. Common causes: multiple failed logins, cached credentials on a mobile device\n"
            "5. After unlocking, check all mobile devices and disconnect any old sessions using stale passwords."
        ),
        "Reference Information": "KB0030 | Identity & Access Management",
    },
    {
        "Category": "Password / Access",
        "Question": "How do I request access to a shared drive?",
        "Response": (
            "Shared Drive Access Request procedure:\n"
            "1. Navigate to: Service Portal → Access Requests → Shared Drive\n"
            "2. Enter the UNC path of the drive (e.g. \\\\fileserver\\Finance)\n"
            "3. State the business justification\n"
            "4. Request is auto-routed to the drive owner for approval\n"
            "5. Access provisioned within 4 hours of approval\n"
            "6. Quarterly access reviews are conducted — retain justification records."
        ),
        "Reference Information": "KB0031 | Data Access Control Policy",
    },
    {
        "Category": "Software",
        "Question": "How do I install approved software from the software centre?",
        "Response": (
            "To install approved software:\n"
            "1. Open Software Center: Start → Microsoft Endpoint Manager → Software Center\n"
            "2. Browse the Applications tab\n"
            "3. Click the required application → Install\n"
            "4. Installation runs silently in background (5–20 minutes)\n"
            "5. Restart if prompted\n"
            "Note: Software not in the catalogue requires a Software Request via the portal with business justification and manager approval."
        ),
        "Reference Information": "KB0040 | Software Management Policy",
    },
    {
        "Category": "Software",
        "Question": "Microsoft Teams is crashing on startup",
        "Response": (
            "Teams crash fix steps:\n"
            "1. Fully close Teams (System Tray → right-click → Quit)\n"
            "2. Clear cache: %AppData%\\Microsoft\\Teams — delete all folder contents\n"
            "3. Relaunch Teams\n"
            "4. If crashing persists, uninstall via Control Panel then reinstall from Software Center\n"
            "5. For persistent crashes, collect crash dumps from %LocalAppData%\\CrashDumps and raise an incident."
        ),
        "Reference Information": "KB0041 | Microsoft 365 Support",
    },
]


def main():
    output_dir = Path("data/knowledge_base")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "sample_kb.xlsx"

    df = pd.DataFrame(RECORDS)
    df.to_excel(output_path, index=False)
    print(f"✅ Sample knowledge base written to: {output_path}")
    print(f"   Rows: {len(df)}")
    print(f"   Columns: {list(df.columns)}")


if __name__ == "__main__":
    main()
