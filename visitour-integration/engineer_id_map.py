"""
VISITOUR fmExtId ↔ Engineer Name Mapping
Reference data for Advance Group Dev Lead.

Engineers without an fmExtId (marked None) cannot currently be pushed
to VISITOUR — they need a FieldManager record created in VISITOUR first.
"""

# (Name, fmExtId)
ENGINEER_IDS = [
    ("Tony Reid",               "487"),
    ("Aristotelis Goudelis",    "858"),
    ("Carl Mills",              "689"),
    ("Charles Tidey",           "802"),
    ("Chris Amor",              "240"),
    ("Franc Genovese",          "348"),
    ("Gareth Terrell",          "926"),
    ("Gary Cant",               "501"),
    ("Hossein Soltani-Tehrani", "776"),
    ("Ian Scott",               "773"),
    ("Jack Eagle",              "690"),
    ("Lee Reynolds",            "233"),
    ("Louis Holman",            "800"),
    ("Mark Wilson",             "952"),
    ("Michael Mutirwara",       "711"),
    ("Mustafa Raza",            "855"),
    ("Nick Green",              "820"),
    ("Nigel Lomax",             "405"),
    ("Paul Holman",             "808"),
    ("Rhys Standing",           "982"),
    ("Ricky Parrett",           "239"),
    ("Rob Carlisle",            "799"),
    ("Scott Morgan",            "681"),
    ("Sean Craig",              "308"),
    ("Shane Sheppard",          "676"),
    ("Stephen Martin",          "844"),
    ("Terry Jones",             "884"),
    ("Trymore Mavhangira",      "696"),
    ("Tyler Speight",           "461"),
    ("Umit Salah",              "731"),
    ("Vincent Magombe",         "761"),
    ("Wes Mwashaireni",         "694"),
    # No fmExtId — not yet in VISITOUR as FieldManagers:
    ("Mark Holmes",             None),
    ("Roy Aris",                None),
    ("Callum Milnes",           None),
    ("Ryan Mongiovi",           None),
    ("Andre Simao",             None),
    ("Arron Kearns",            None),
]

FM_TO_NAME = {fmid: name for name, fmid in ENGINEER_IDS if fmid}
NAME_TO_FM = {name: fmid for name, fmid in ENGINEER_IDS if fmid}

if __name__ == "__main__":
    print(f"{'Engineer':<30} {'fmExtId':>8}")
    print("-" * 40)
    for name, fmid in ENGINEER_IDS:
        print(f"{name:<30} {fmid or 'NO ID':>8}")
