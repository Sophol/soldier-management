"""Load a realistic demo dataset: unit tree, soldiers with service history, approved and
draft decisions, incoming/outgoing documents, training, awards, discipline, retirement,
separation and demo users.

Usage:  python -m scripts.seed_demo [--password Demo@123] [--seed 2026]
Run after `scripts.import_geo` and `scripts.seed`. Refuses to run if soldiers or units
already exist, so it never mixes with real data. All people in it are fictional.
"""

import argparse
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import (  # noqa: E402
    AwardRecord,
    Commune,
    Country,
    Decision,
    DecisionItem,
    DisciplineRecord,
    District,
    DocumentIncoming,
    DocumentOutgoing,
    DocumentType,
    Lookup,
    Position,
    Province,
    Rank,
    RetirementRecord,
    Role,
    SeparationRecord,
    Soldier,
    SoldierChild,
    SoldierEducation,
    SoldierLanguage,
    Specialty,
    TrainingCourse,
    TrainingParticipant,
    Unit,
    User,
    Village,
)
from app.models.decision import DECISION_KINDS  # noqa: E402
from app.services.soldier import add_history, add_movement  # noqa: E402

TODAY = date.today()
# Soldiers are entered with their state as of this date; decisions from 2025 onwards change it.
BASELINE = date(2024, 12, 31)
ISSUER = "រដ្ឋមន្ត្រីក្រសួងមហាផ្ទៃ"

KH_DIGITS = str.maketrans("0123456789", "០១២៣៤៥៦៧៨៩")


def kh(n) -> str:
    return str(n).translate(KH_DIGITS)


# ---------------------------------------------------------------- unit tree
# (code, name_kh, name_en, kind, children); kind drives positions and specialties
UNITS = ("MOI", "ក្រសួងមហាផ្ទៃ", "Ministry of Interior", "hq", [
    ("GDA", "អគ្គនាយកដ្ឋានរដ្ឋបាល", "General Department of Administration", "admin", [
        ("GDA-PER", "នាយកដ្ឋានបុគ្គលិក", "Department of Personnel", "admin", [
            ("GDA-PER-ATP", "ការិយាល័យតែងតាំង ផ្លាស់ប្ដូរ និងដំឡើងឋានន្តរស័ក្តិ",
             "Office of Appointment, Transfer and Promotion", "admin", []),
            ("GDA-PER-MGT", "ការិយាល័យគ្រប់គ្រងបុគ្គលិក", "Personnel Management Office", "admin", []),
            ("GDA-PER-PEN", "ការិយាល័យសោធននិវត្តន៍ និងរបបសន្តិសុខសង្គម", "Pension and Social Security Office", "admin", []),
        ]),
        ("GDA-FIN", "នាយកដ្ឋានរដ្ឋបាល និងហិរញ្ញវត្ថុ", "Department of Administration and Finance", "finance", [
            ("GDA-FIN-ADM", "ការិយាល័យរដ្ឋបាល", "Administration Office", "admin", []),
            ("GDA-FIN-ACC", "ការិយាល័យគណនេយ្យ និងហិរញ្ញវត្ថុ", "Accounting and Finance Office", "finance", []),
        ]),
        ("GDA-LOG", "នាយកដ្ឋានភស្តុភារ", "Department of Logistics", "logistics", [
            ("GDA-LOG-SUP", "ការិយាល័យសម្ភារៈ និងបរិក្ខារ", "Supplies and Equipment Office", "logistics", []),
            ("GDA-LOG-VEH", "ការិយាល័យយានយន្ត", "Vehicle Office", "logistics", []),
        ]),
        ("GDA-ICT", "នាយកដ្ឋានព័ត៌មានវិទ្យា", "Department of Information Technology", "ict", []),
    ]),
    ("GRD", "បញ្ជាការដ្ឋានកងការពារ", "Guard Command", "troop", [
        ("GRD-B1", "វរសេនាតូចការពារលេខ១", "1st Guard Battalion", "troop", [
            ("GRD-B1-C1", "សេនាធំទី១", "1st Company", "troop", []),
            ("GRD-B1-C2", "សេនាធំទី២", "2nd Company", "troop", []),
        ]),
        ("GRD-B2", "វរសេនាតូចការពារលេខ២", "2nd Guard Battalion", "troop", [
            ("GRD-B2-C1", "សេនាធំទី១", "1st Company", "troop", []),
            ("GRD-B2-C2", "សេនាធំទី២", "2nd Company", "troop", []),
        ]),
        ("GRD-INT", "វរសេនាតូចអន្តរាគមន៍", "Intervention Battalion", "troop", [
            ("GRD-INT-C1", "សេនាធំអន្តរាគមន៍ទី១", "1st Intervention Company", "troop", []),
        ]),
        ("GRD-COM", "ការិយាល័យទំនាក់ទំនង និងទូរគមនាគមន៍", "Communications Office", "ict", []),
    ]),
    ("TRC", "មជ្ឈមណ្ឌលបណ្ដុះបណ្ដាល", "Training Centre", "training", [
        ("TRC-ACA", "ការិយាល័យសិក្សា", "Academic Office", "training", []),
        ("TRC-STU", "ការិយាល័យគ្រប់គ្រងសិក្ខាកាម", "Trainee Management Office", "training", []),
    ]),
    ("MED", "មជ្ឈមណ្ឌលសុខាភិបាល", "Health Centre", "medical", [
        ("MED-CLI", "ផ្នែកពិគ្រោះ និងព្យាបាលជំងឺ", "Clinic", "medical", []),
    ]),
])

SPECIALTY_BY_KIND = {
    "hq": ["រដ្ឋបាល និងបុគ្គលិក", "ច្បាប់"],
    "admin": ["រដ្ឋបាល និងបុគ្គលិក", "ច្បាប់", "ព័ត៌មានវិទ្យា"],
    "finance": ["ហិរញ្ញវត្ថុ", "រដ្ឋបាល និងបុគ្គលិក"],
    "logistics": ["ភស្តុភារ", "បើកបរ និងជួសជុលយានយន្ត", "វិស្វកម្ម"],
    "ict": ["ព័ត៌មានវិទ្យា", "ទូរគមនាគមន៍"],
    "troop": ["ថ្មើរជើង", "ការពារ និងអន្តរាគមន៍", "ចារកម្ម និងស៊ើបការណ៍", "បើកបរ និងជួសជុលយានយន្ត"],
    "training": ["រដ្ឋបាល និងបុគ្គលិក", "ថ្មើរជើង", "ច្បាប់"],
    "medical": ["វេជ្ជសាស្ត្រ"],
}

# ---------------------------------------------------------------- people
FAMILY = [
    ("សុខ", "SOK"), ("ចាន់", "CHAN"), ("ហេង", "HENG"), ("គឹម", "KIM"), ("លី", "LY"), ("ម៉ៅ", "MAO"),
    ("ស៊ុន", "SUN"), ("ពេជ្រ", "PICH"), ("ឈឹម", "CHHIM"), ("កែវ", "KEO"), ("ញឹម", "NHIM"), ("ទេព", "TEP"),
    ("សេង", "SENG"), ("ហ៊ុល", "HUL"), ("ខៀវ", "KHIEV"), ("យឹម", "YIM"), ("ភួង", "PHOUNG"), ("ឯក", "EK"),
    ("វង្ស", "VONG"), ("អ៊ុក", "OUK"), ("ជា", "CHEA"), ("មាស", "MEAS"), ("នូ", "NOU"), ("ប៊ុន", "BUN"),
    ("ឡុង", "LONG"), ("ថោង", "THONG"), ("សំ", "SAM"), ("ព្រំ", "PROM"), ("ផល", "PHAL"), ("សយ", "SOY"),
]
MALE = [
    ("ដារ៉ា", "DARA"), ("វិសាល", "VISAL"), ("សំណាង", "SAMNANG"), ("ពិសិដ្ឋ", "PISETH"), ("សុផល", "SOPHAL"),
    ("ចំរើន", "CHAMROEUN"), ("វណ្ណៈ", "VANNAK"), ("ប៊ុនថន", "BUNTHON"), ("សុខា", "SOKHA"), ("រិទ្ធី", "RITHY"),
    ("សារ៉េត", "SARETH"), ("បូរ៉ា", "BORA"), ("ធារ៉ា", "THEARA"), ("កុសល", "KOSAL"), ("សុវណ្ណ", "SOVANN"),
    ("មករា", "MAKARA"), ("វិចិត្រ", "VICHET"), ("សុភ័ក្ត្រ", "SOPHEAK"), ("សុធា", "SOTHEA"), ("ឧត្តម", "OUDOM"),
    ("ប៊ុនណា", "BUNNA"), ("វឌ្ឍនា", "VATHANA"), ("សម្បត្តិ", "SAMBATH"), ("ចាន់ថន", "CHANTHON"),
    ("ពិសាល", "PISAL"), ("សុជាតិ", "SOCHEAT"), ("រដ្ឋា", "RATHA"), ("វីរៈ", "VIREAK"), ("សេរីវុធ", "SEREYVUTH"),
    ("ម៉េងហ៊ាង", "MENGHEANG"),
]
FEMALE = [
    ("ស្រីមុំ", "SREYMOM"), ("សុភាព", "SOPHEAP"), ("ចន្ទ្រា", "CHANTREA"), ("ផល្លា", "PHALLA"),
    ("សុគន្ធា", "SOKUNTHEA"), ("ធីតា", "THIDA"), ("ចិន្ដា", "CHENDA"), ("ម៉ាលីស", "MALIS"), ("សុជាតា", "SOCHEATA"),
    ("ពិសី", "PISEY"), ("ស្រីល័ក្ខ", "SREYLEAK"), ("រស្មី", "RASMEY"), ("ច័ន្ទថា", "CHANTHA"), ("ដាលីន", "DALIN"),
    ("សុវណ្ណារី", "SOVANNARY"), ("លក្ខិណា", "LEAKHENA"),
]

PHONE_PREFIX = ["012", "011", "015", "016", "017", "070", "077", "078", "085", "089", "092", "096", "097", "098"]

SCHOOLS = {
    "បឋមសិក្សា": ["សាលាបឋមសិក្សាជាតិ"],
    "អនុវិទ្យាល័យ": ["អនុវិទ្យាល័យជាតិ"],
    "វិទ្យាល័យ": ["វិទ្យាល័យព្រះស៊ីសុវត្ថិ", "វិទ្យាល័យបាក់ទូក", "វិទ្យាល័យសន្ធរម៉ុក", "វិទ្យាល័យខេត្ត"],
    "បរិញ្ញាបត្ររង": ["វិទ្យាស្ថានបច្ចេកវិទ្យាកម្ពុជា", "វិទ្យាស្ថានជាតិពហុបច្ចេកទេសកម្ពុជា"],
    "បរិញ្ញាបត្រ": ["សាកលវិទ្យាល័យភូមិន្ទភ្នំពេញ", "សាកលវិទ្យាល័យភូមិន្ទនីតិសាស្ត្រ និងវិទ្យាសាស្ត្រសេដ្ឋកិច្ច",
                    "សាកលវិទ្យាល័យជាតិគ្រប់គ្រង", "សាកលវិទ្យាល័យវិទ្យាសាស្ត្រសុខាភិបាល", "វិទ្យាស្ថានបច្ចេកវិទ្យាកម្ពុជា"],
    "អនុបណ្ឌិត": ["សាកលវិទ្យាល័យភូមិន្ទនីតិសាស្ត្រ និងវិទ្យាសាស្ត្រសេដ្ឋកិច្ច", "សាកលវិទ្យាល័យជាតិគ្រប់គ្រង",
                  "សាកលវិទ្យាល័យភូមិន្ទភ្នំពេញ"],
    "បណ្ឌិត": ["សាកលវិទ្យាល័យភូមិន្ទភ្នំពេញ"],
}
MAJORS = {
    "រដ្ឋបាល និងបុគ្គលិក": "រដ្ឋបាលសាធារណៈ", "ច្បាប់": "នីតិសាស្ត្រ", "ព័ត៌មានវិទ្យា": "វិទ្យាសាស្ត្រកុំព្យូទ័រ",
    "ហិរញ្ញវត្ថុ": "គណនេយ្យ និងហិរញ្ញវត្ថុ", "ភស្តុភារ": "គ្រប់គ្រងពាណិជ្ជកម្ម", "វិស្វកម្ម": "វិស្វកម្មសំណង់",
    "ទូរគមនាគមន៍": "វិស្វកម្មអគ្គិសនី និងអេឡិចត្រូនិក", "វេជ្ជសាស្ត្រ": "វេជ្ជសាស្ត្រ",
}

# rank -> (min, max) years of service at BASELINE, typical for someone currently holding it
SERVICE_YEARS = {
    "ពលទាហានទោ": (1, 3), "ពលទាហានឯក": (2, 5),
    "ពលបាលត្រី": (4, 8), "ពលបាលទោ": (6, 10), "ពលបាលឯក": (8, 13),
    "ព្រឹន្ទបាលត្រី": (10, 15), "ព្រឹន្ទបាលទោ": (12, 18), "ព្រឹន្ទបាលឯក": (14, 22),
    "អនុសេនីយ៍ត្រី": (3, 8), "អនុសេនីយ៍ទោ": (5, 11), "អនុសេនីយ៍ឯក": (8, 14),
    "វរសេនីយ៍ត្រី": (12, 20), "វរសេនីយ៍ទោ": (16, 24), "វរសេនីយ៍ឯក": (20, 30),
    "ឧត្តមសេនីយ៍ត្រី": (24, 32), "ឧត្តមសេនីយ៍ទោ": (27, 34),
}
OFFICER_RANKS = {"អនុសេនីយ៍ត្រី", "អនុសេនីយ៍ទោ", "អនុសេនីយ៍ឯក", "វរសេនីយ៍ត្រី", "វរសេនីយ៍ទោ", "វរសេនីយ៍ឯក",
                 "ឧត្តមសេនីយ៍ត្រី", "ឧត្តមសេនីយ៍ទោ"}

# roster per unit level and kind: (position, [possible ranks], how many)
HEADS = {
    1: [],
    2: {"troop": [("មេបញ្ជាការ", ["ឧត្តមសេនីយ៍ទោ", "ឧត្តមសេនីយ៍ត្រី"], 1),
                  ("មេបញ្ជាការរង", ["ឧត្តមសេនីយ៍ត្រី", "វរសេនីយ៍ឯក"], 2),
                  ("នាយសេនាធិការ", ["វរសេនីយ៍ឯក"], 1)],
        "default": [("អគ្គនាយក", ["ឧត្តមសេនីយ៍ទោ", "ឧត្តមសេនីយ៍ត្រី"], 1),
                    ("អគ្គនាយករង", ["ឧត្តមសេនីយ៍ត្រី", "វរសេនីយ៍ឯក"], 2)]},
    3: {"troop": [("មេវរសេនាតូច", ["វរសេនីយ៍ទោ", "វរសេនីយ៍ឯក"], 1),
                  ("មេវរសេនាតូចរង", ["វរសេនីយ៍ត្រី", "វរសេនីយ៍ទោ"], 2)],
        "default": [("ប្រធាននាយកដ្ឋាន", ["វរសេនីយ៍ឯក", "វរសេនីយ៍ទោ"], 1),
                    ("អនុប្រធាននាយកដ្ឋាន", ["វរសេនីយ៍ទោ", "វរសេនីយ៍ត្រី"], 2)]},
    4: {"troop": [("មេសេនាធំ", ["អនុសេនីយ៍ឯក", "វរសេនីយ៍ត្រី"], 1),
                  ("មេសេនាតូច", ["អនុសេនីយ៍ទោ", "អនុសេនីយ៍ត្រី"], 2),
                  ("មេក្រុម", ["ពលបាលឯក", "ពលបាលទោ", "ព្រឹន្ទបាលត្រី"], 3)],
        "default": [("ប្រធានការិយាល័យ", ["វរសេនីយ៍ត្រី", "វរសេនីយ៍ទោ"], 1),
                    ("អនុប្រធានការិយាល័យ", ["អនុសេនីយ៍ឯក", "វរសេនីយ៍ត្រី"], 1)]},
}
STAFF = {
    "troop": ("ពលទាហាន", ["ពលទាហានទោ", "ពលទាហានឯក", "ពលទាហានឯក", "ពលបាលត្រី"], (6, 9)),
    "default": ("មន្ត្រីជំនាញ", ["អនុសេនីយ៍ត្រី", "អនុសេនីយ៍ទោ", "អនុសេនីយ៍ឯក", "ព្រឹន្ទបាលត្រី",
                                 "ព្រឹន្ទបាលទោ", "ព្រឹន្ទបាលឯក", "ពលបាលឯក"], (3, 5)),
}

INCOMING_SUBJECTS = [
    "សំណើសុំដំឡើងឋានន្តរស័ក្តិជូននាយទាហាន និងនាយទាហានរងចំនួន {n} រូប ប្រចាំឆ្នាំ {y}",
    "សំណើសុំផ្លាស់ប្ដូរកងឯកភាពជូនយោធិនចំនួន {n} រូប",
    "របាយការណ៍ស្ដីពីស្ថានភាពកម្លាំងយោធិនប្រចាំខែ {m} ឆ្នាំ {y}",
    "សំណើសុំតែងតាំងមុខតំណែងប្រធាន និងអនុប្រធានការិយាល័យ",
    "លិខិតអញ្ជើញចូលរួមកិច្ចប្រជុំបូកសរុបលទ្ធផលការងារប្រចាំឆមាសទី{h} ឆ្នាំ {y}",
    "សំណើសុំបញ្ជូនយោធិនចូលរួមវគ្គបណ្ដុះបណ្ដាលរយៈពេលខ្លី",
    "បញ្ជីរាយនាមយោធិនដែលត្រូវចូលនិវត្តន៍ក្នុងឆ្នាំ {y}",
    "សំណើសុំផ្ដល់ប័ណ្ណសរសើរជូនយោធិនដែលមានស្នាដៃឆ្នើមក្នុងការបំពេញភារកិច្ច",
    "សារាចរស្ដីពីការរៀបចំបញ្ជីឈ្មោះយោធិនដែលត្រូវដំឡើងឋានន្តរស័ក្តិប្រចាំឆ្នាំ {y}",
    "សេចក្ដីណែនាំស្ដីពីការគ្រប់គ្រង និងរក្សាទុកឯកសារប្រវត្តិរូបយោធិន",
    "របាយការណ៍ស្ដីពីការអនុវត្តវិន័យ និងសីលធម៌យោធិនប្រចាំត្រីមាសទី{q} ឆ្នាំ {y}",
    "សំណើសុំបញ្ចូលយោធិនជាយោធិនប្រភេទ២ ដោយសារបញ្ហាសុខភាព",
]
INCOMING_TYPES = {0: "សំណើ", 1: "សំណើ", 2: "របាយការណ៍", 3: "សំណើ", 4: "លិខិតអញ្ជើញ", 5: "សំណើ", 6: "លិខិត",
                  7: "សំណើ", 8: "សារាចរ", 9: "សេចក្ដីណែនាំ", 10: "របាយការណ៍", 11: "សំណើ"}
EXTERNAL_SENDERS = ["អគ្គលេខាធិការដ្ឋានក្រសួងមហាផ្ទៃ", "ក្រសួងមុខងារសាធារណៈ", "ក្រសួងសេដ្ឋកិច្ច និងហិរញ្ញវត្ថុ",
                    "ខុទ្ទកាល័យរដ្ឋមន្ត្រី", "បេឡាជាតិរបបសន្តិសុខសង្គម"]
OUTGOING_SUBJECTS = [
    ("លិខិត", "ការជូនដំណឹងអំពីលទ្ធផលនៃការពិនិត្យសំណើសុំដំឡើងឋានន្តរស័ក្តិ"),
    ("លិខិត", "ការស្នើសុំបញ្ជីរាយនាម និងឯកសារភ្ជាប់របស់យោធិនដែលត្រូវចូលនិវត្តន៍"),
    ("លិខិតអញ្ជើញ", "អញ្ជើញចូលរួមកិច្ចប្រជុំពិនិត្យបញ្ជីឈ្មោះយោធិនស្នើសុំដំឡើងឋានន្តរស័ក្តិ"),
    ("សារាចរ", "ការរៀបចំ និងបញ្ជូនបញ្ជីកម្លាំងយោធិនប្រចាំឆមាស"),
    ("សេចក្ដីណែនាំ", "នីតិវិធីស្នើសុំផ្លាស់ប្ដូរកងឯកភាព និងមុខតំណែង"),
    ("របាយការណ៍", "លទ្ធផលការងារតែងតាំង ផ្លាស់ប្ដូរ និងដំឡើងឋានន្តរស័ក្តិប្រចាំឆមាស"),
    ("លិខិត", "ការបញ្ជូនសិក្ខាកាមចូលរួមវគ្គបណ្ដុះបណ្ដាល"),
    ("លិខិត", "ការផ្ទៀងផ្ទាត់ព័ត៌មានប្រវត្តិរូបយោធិន"),
]
AWARD_REASONS = [
    "បានបំពេញភារកិច្ចប្រកបដោយស្មារតីទទួលខុសត្រូវខ្ពស់ និងទទួលបានលទ្ធផលល្អប្រសើរ ប្រចាំឆ្នាំ {y}",
    "បានចូលរួមយ៉ាងសកម្មក្នុងការរក្សាសន្តិសុខ សណ្ដាប់ធ្នាប់ ក្នុងពិធីបុណ្យចូលឆ្នាំថ្មីប្រពៃណីជាតិ ឆ្នាំ {y}",
    "បានចូលរួមក្នុងប្រតិបត្តិការជួយសង្គ្រោះប្រជាពលរដ្ឋរងគ្រោះដោយទឹកជំនន់ ឆ្នាំ {y}",
    "មានស្នាដៃឆ្នើមក្នុងការងារគ្រប់គ្រងរដ្ឋបាល និងឯកសារ",
    "បានបម្រើការងារយូរឆ្នាំ ដោយភាពស្មោះត្រង់ និងគ្មានកំហុសវិន័យ",
]
DISCIPLINE_REASONS = [
    "អវត្តមានពីការងារដោយគ្មានច្បាប់អនុញ្ញាតចំនួន {d} ថ្ងៃ",
    "មិនគោរពម៉ោងធ្វើការ និងបទបញ្ជារបស់ថ្នាក់ដឹកនាំ",
    "បើកបរយានយន្តរបស់អង្គភាពដោយគ្មានការអនុញ្ញាត",
    "ធ្វេសប្រហែសក្នុងការរក្សាទុកសម្ភារៈ និងអាវុធរបស់អង្គភាព",
]


class Builder:
    def __init__(self, db, rng: random.Random, password: str):
        self.db, self.rng, self.password = db, rng, password
        self.admin = db.scalar(select(User).where(User.username == "admin"))
        self.ranks = {r.name_kh: r for r in db.scalars(select(Rank))}
        self.rank_by_id = {r.id: r for r in self.ranks.values()}
        self.positions = {p.name_kh: p for p in db.scalars(select(Position))}
        self.pos_by_id = {p.id: p for p in self.positions.values()}
        self.specialties = {s.name_kh: s for s in db.scalars(select(Specialty))}
        self.doc_types = {d.name_kh: d for d in db.scalars(select(DocumentType))}
        self.lk = {}
        for lk in db.scalars(select(Lookup)):
            self.lk.setdefault(lk.category, {})[lk.code or lk.name_kh] = lk
        self.countries = {c.name_en: c for c in db.scalars(select(Country))}
        self.units: dict[str, Unit] = {}
        self.unit_kind: dict[int, str] = {}
        self.soldiers: list[Soldier] = []
        self.heads: dict[int, Soldier] = {}  # unit id -> head
        self.locked: set[int] = set()  # soldiers reserved for retirement/separation stories
        self.military_seq = 0
        self.used_nid: set[str] = set()
        self.village_ids_by_province = self._villages()

    def _villages(self) -> dict[int, list[int]]:
        rows = self.db.execute(
            select(Village.id, District.province_id).join(Commune, Commune.id == Village.commune_id)
            .join(District, District.id == Commune.district_id)
        ).all()
        out: dict[int, list[int]] = {}
        for vid, pid in rows:
            out.setdefault(pid, []).append(vid)
        return out

    # ------------------------------------------------------------ helpers
    def rand_date(self, start: date, end: date) -> date:
        if end <= start:
            return start
        return start + timedelta(days=self.rng.randint(0, (end - start).days))

    def years_before(self, d: date, years: float) -> date:
        return d - timedelta(days=int(years * 365.25))

    def phone(self) -> str:
        return f"{self.rng.choice(PHONE_PREFIX)} {self.rng.randint(100, 999)} {self.rng.randint(100, 999)}"

    def national_id(self) -> str:
        while True:
            nid = f"{self.rng.randint(10, 25):02d}{self.rng.randint(0, 9999999):07d}"
            if nid not in self.used_nid:
                self.used_nid.add(nid)
                return nid

    def person(self, gender: str) -> tuple[str, str]:
        fam = self.rng.choice(FAMILY)
        given = self.rng.choice(MALE if gender == "M" else FEMALE)
        return f"{fam[0]} {given[0]}", f"{fam[1]} {given[1]}"

    def province_name(self, pid: int) -> str:
        return self.db.get(Province, pid).name_kh

    def position_name(self, s: Soldier) -> str | None:
        return self.pos_by_id[s.current_position_id].name_kh if s.current_position_id else None

    # ------------------------------------------------------------ users
    def users(self) -> None:
        roles = {r.name: r for r in self.db.scalars(select(Role))}
        defs = [
            ("officer", "សុខ សុភាព", "Officer", None),
            ("approver", "ហេង វិសាល", "Approver", None),
            ("viewer", "កែវ ចន្ទ្រា", "Viewer", None),
            ("guard.officer", "មាស ដារ៉ា", "Officer", "GRD"),
        ]
        for username, name, role, scope in defs:
            if self.db.scalar(select(User).where(User.username == username)):
                continue
            self.db.add(User(username=username, password_hash=hash_password(self.password), full_name=name,
                             phone=self.phone(), role_id=roles[role].id,
                             unit_scope_id=self.units[scope].id if scope else None))
        self.db.flush()

    # ------------------------------------------------------------ units
    def build_units(self, node=UNITS, parent: Unit | None = None, level: int = 1, order: int = 1) -> None:
        code, name_kh, name_en, kind, children = node
        u = Unit(parent_id=parent.id if parent else None, level=level, code=code, name_kh=name_kh, name_en=name_en,
                 sort_order=order)
        self.db.add(u)
        self.db.flush()
        u.path = f"{parent.path if parent else '/'}{u.id}/"
        self.units[code] = u
        self.unit_kind[u.id] = kind
        for i, child in enumerate(children, start=1):
            self.build_units(child, u, level + 1, i)

    # ------------------------------------------------------------ soldiers
    def make_soldier(self, unit: Unit, position: str, rank_name: str, *, gender: str | None = None,
                     dob: date | None = None, enlisted: date | None = None, recruit: bool = False) -> Soldier:
        rng = self.rng
        kind = self.unit_kind[unit.id]
        gender = gender or ("F" if rng.random() < (0.3 if kind in {"admin", "finance", "medical"} else 0.05) else "M")
        rank = self.ranks[rank_name]
        officer = rank_name in OFFICER_RANKS

        if enlisted is None:
            lo, hi = SERVICE_YEARS[rank_name]
            enlisted = self.years_before(BASELINE, rng.uniform(lo, hi))
            enlisted = enlisted.replace(day=1)
        if dob is None:
            enlist_age = rng.uniform(21, 25) if officer else rng.uniform(18, 23)
            dob = self.years_before(enlisted, enlist_age)
            # nobody in the regular roster should already be at retirement age
            max_age = 58 if gender == "M" else 53
            if (TODAY - dob).days / 365.25 > max_age:
                dob = self.years_before(TODAY, rng.uniform(max_age - 4, max_age))
                enlisted = max(enlisted, self.years_before(dob, -20).replace(day=1))

        ref = max(BASELINE, enlisted)
        if recruit:
            rank_date = position_date = unit_date = enlisted
            from_unit = None
        else:
            gap = (rank.min_years_to_next or 3) + 2
            rank_date = max(enlisted, self.years_before(ref, rng.uniform(0.3, gap))).replace(day=1)
            position_date = self.rand_date(max(enlisted, self.years_before(ref, 6)), ref)
            if rng.random() < 0.55:
                unit_date, from_unit = enlisted, None
            else:
                unit_date = self.rand_date(enlisted, position_date)
                prov = rng.choice(list(self.village_ids_by_province))
                from_unit = f"អង្គភាពការពារខេត្ត{self.province_name(prov)}"

        name_kh, name_latin = self.person(gender)
        birth_prov = rng.choice(list(self.village_ids_by_province))
        cur_prov = rng.choice([12, 12, 12, 8, 8, 5, 14])  # mostly Phnom Penh and nearby provinces
        cur_prov = cur_prov if cur_prov in self.village_ids_by_province else birth_prov

        age_now = (TODAY - dob).days / 365.25
        married = age_now > 24 and rng.random() < min(0.95, (age_now - 20) / 12)
        marital = self.lk["marital_status"]["married" if married else "single"]
        if married and age_now > 45 and rng.random() < 0.06:
            marital = self.lk["marital_status"][rng.choice(["divorced", "widowed"])]

        edu_levels = (["វិទ្យាល័យ", "បរិញ្ញាបត្រ", "បរិញ្ញាបត្រ", "អនុបណ្ឌិត"] if officer
                      else ["អនុវិទ្យាល័យ", "វិទ្យាល័យ", "វិទ្យាល័យ", "បរិញ្ញាបត្ររង", "បរិញ្ញាបត្រ"])
        if rank_name in {"វរសេនីយ៍ឯក", "ឧត្តមសេនីយ៍ត្រី", "ឧត្តមសេនីយ៍ទោ"}:
            edu_levels = ["បរិញ្ញាបត្រ", "អនុបណ្ឌិត", "អនុបណ្ឌិត", "បណ្ឌិត"]
        if kind == "troop" and not officer:
            edu_levels = ["បឋមសិក្សា", "អនុវិទ្យាល័យ", "អនុវិទ្យាល័យ", "វិទ្យាល័យ"]
        edu = rng.choice(edu_levels)
        specialty = self.specialties.get(rng.choice(SPECIALTY_BY_KIND[kind]))

        self.military_seq += 1
        s = Soldier(
            military_id=f"{enlisted.year}{self.military_seq:05d}",
            name_kh=name_kh, name_latin=name_latin, gender=gender, date_of_birth=dob,
            national_id=self.national_id() if rng.random() < 0.95 else None,
            phone=self.phone(), blood_type_id=rng.choice(list(self.lk["blood_type"].values())).id,
            birth_village_id=rng.choice(self.village_ids_by_province[birth_prov]),
            current_village_id=rng.choice(self.village_ids_by_province[cur_prov]),
            current_address_text=(f"ផ្ទះលេខ {kh(rng.randint(1, 250))} ផ្លូវលេខ {kh(rng.randint(1, 600))}"
                                  if cur_prov == 12 and rng.random() < 0.6 else None),
            current_rank_id=rank.id, rank_date=rank_date,
            current_position_id=self.positions[position].id, position_date=position_date,
            current_unit_id=unit.id, unit_transfer_date=unit_date, from_unit_text=from_unit,
            enlistment_date=enlisted, status_id=self.lk["soldier_status"]["active"].id,
            education_level_id=self.lk["education_level"][edu].id,
            specialty_id=specialty.id if specialty else None,
            marital_status_id=marital.id,
            father_name=f"{name_kh.split()[0]} {rng.choice(MALE)[0]}",
            mother_name=self.person("F")[0],
            created_by=self.admin.id, updated_by=self.admin.id,
        )
        if enlisted.year < 1999 and rng.random() < 0.45:
            s.combat_veteran = True
            s.combat_note = f"ចូលរួមប្រតិបត្តិការការពារបូរណភាពទឹកដី ឆ្នាំ {kh(rng.randint(max(enlisted.year, 1990), 1998))}"

        if married:
            spouse_gender = "F" if gender == "M" else "M"
            s.spouse_name = self.person(spouse_gender)[0]
            s.spouse_job_id = rng.choice(list(self.lk["occupation"].values())).id
            wed = self.years_before(TODAY, rng.uniform(1, max(1.5, age_now - 23)))
            for _ in range(rng.choice([0, 1, 1, 2, 2, 2, 3, 3, 4])):
                cg = rng.choice("MF")
                cdob = self.rand_date(wed, TODAY - timedelta(days=60))
                s.children.append(SoldierChild(name=f"{name_kh.split()[0]} {rng.choice(MALE if cg == 'M' else FEMALE)[0]}",
                                               gender=cg, date_of_birth=cdob))
            s.children_count = len(s.children)

        # education history
        school = rng.choice(SCHOOLS[edu])
        if edu in {"បរិញ្ញាបត្ររង", "បរិញ្ញាបត្រ", "អនុបណ្ឌិត", "បណ្ឌិត"}:
            years = {"បរិញ្ញាបត្ររង": 2, "បរិញ្ញាបត្រ": 4, "អនុបណ្ឌិត": 2, "បណ្ឌិត": 4}[edu]
            end = self.rand_date(self.years_before(dob, -22), min(TODAY, self.years_before(dob, -40)))
            start = self.years_before(end, years)
            s.educations.append(SoldierEducation(
                kind="general", education_level_id=self.lk["education_level"][edu].id,
                specialty_text=MAJORS.get(specialty.name_kh if specialty else "", "គ្រប់គ្រងសាធារណៈ"),
                institution=school, country_id=self.countries["Cambodia"].id, start_date=start, end_date=end,
                duration_text=f"{kh(years)} ឆ្នាំ"))
        else:
            grad = self.years_before(dob, -18)
            s.educations.append(SoldierEducation(
                kind="general", education_level_id=self.lk["education_level"][edu].id, institution=school,
                country_id=self.countries["Cambodia"].id, end_date=grad if grad < TODAY else None))
        if officer:
            start = self.rand_date(enlisted, max(enlisted, self.years_before(ref, 1)))
            abroad = rank_name not in {"អនុសេនីយ៍ត្រី", "អនុសេនីយ៍ទោ"} and rng.random() < 0.25
            country = self.countries[rng.choice(["Vietnam", "China", "France", "Australia", "Russia"])] if abroad \
                else self.countries["Cambodia"]
            s.educations.append(SoldierEducation(
                kind="specialty", specialty_text=specialty.name_kh if specialty else "បញ្ជាការ និងសេនាធិការ",
                institution="សាលាបញ្ជាការ និងសេនាធិការ" if abroad else "សាលាបណ្ដុះបណ្ដាលនាយទាហាន",
                country_id=country.id, is_abroad=abroad, start_date=start, end_date=start + timedelta(days=330),
                duration_text=f"{kh(11)} ខែ"))

        # languages
        for lang in rng.sample(["អង់គ្លេស", "អង់គ្លេស", "បារាំង", "ចិន", "វៀតណាម", "ថៃ"],
                               k=rng.choice([0, 0, 1, 1, 1, 2]) if officer or edu == "បរិញ្ញាបត្រ" else rng.choice([0, 0, 0, 1])):
            if all(lang_row.language_id != self.lk["language"][lang].id for lang_row in s.languages):
                s.languages.append(SoldierLanguage(language_id=self.lk["language"][lang].id,
                                                   level=rng.choice(["ល្អណាស់", "ល្អ", "ល្អ", "មធ្យម", "មធ្យម", "ខ្សោយ"])))

        self.db.add(s)
        self.db.flush()
        add_history(self.db, s, "initial", s.rank_date or s.enlistment_date, new_rank=s.current_rank_id,
                    new_position=s.current_position_id, new_unit=s.current_unit_id, note="ទិន្នន័យដំបូង")
        add_movement(self.db, s.id, s.current_unit_id, "in", "recruit", s.unit_transfer_date or s.enlistment_date,
                     "soldiers", s.id)
        self.soldiers.append(s)
        return s

    def build_soldiers(self) -> None:
        for unit in self.units.values():
            if unit.level == 1:
                continue
            kind = self.unit_kind[unit.id]
            has_children = any(u.parent_id == unit.id for u in self.units.values())
            office = not has_children and unit.name_kh.startswith(("ការិយាល័យ", "ផ្នែក"))
            roster = HEADS[4 if office else unit.level]
            roster = roster.get(kind, roster["default"])
            for i, (position, ranks, count) in enumerate(roster):
                for _ in range(count if not (has_children and i > 0) else 1):
                    s = self.make_soldier(unit, position, self.rng.choice(ranks))
                    if i == 0:
                        self.heads[unit.id] = s
            if not has_children or unit.level == 4:
                position, ranks, (lo, hi) = STAFF.get(kind, STAFF["default"])
                if kind != "troop" and self.rng.random() < 0.5:
                    position = "មន្ត្រីរដ្ឋបាល"
                for _ in range(self.rng.randint(lo, hi)):
                    self.make_soldier(unit, position, self.rng.choice(ranks))

        # new recruits who joined after the baseline
        companies = [u for u in self.units.values() if u.level == 4 and self.unit_kind[u.id] == "troop"]
        intake = date(2025, 11, 1)
        for _ in range(8):
            s = self.make_soldier(self.rng.choice(companies), "ពលទាហាន", "ពលទាហានទោ", gender="M",
                                  dob=self.years_before(intake, self.rng.uniform(18, 21)), enlisted=intake, recruit=True)
            self.locked.add(s.id)

        # staff close to the retirement age, so the dashboard alerts have something to show
        admin_units = [u for u in self.units.values() if u.level == 4 and self.unit_kind[u.id] != "troop"]
        for months_ahead in (1, 2, 4, 5):
            gender = "F" if months_ahead == 4 else "M"
            age = 60 if gender == "M" else 55
            birthday = date(TODAY.year - age, TODAY.month, 15) + timedelta(days=30 * months_ahead)
            self.make_soldier(self.rng.choice(admin_units), "មន្ត្រីជំនាញ",
                              self.rng.choice(["វរសេនីយ៍ត្រី", "វរសេនីយ៍ទោ", "ព្រឹន្ទបាលឯក"]),
                              gender=gender, dob=birthday, enlisted=self.years_before(birthday, -22).replace(day=1))
        self.db.flush()

    # ------------------------------------------------------------ decisions
    def eligible_for_promotion(self, s: Soldier, eff: date) -> bool:
        rank = self.rank_by_id[s.current_rank_id]
        if s.id in self.locked or rank.name_kh not in SERVICE_YEARS or rank.name_kh.startswith("ឧត្តម"):
            return False
        if rank.name_kh == "ព្រឹន្ទបាលឯក":  # NCO → officer needs the officer course, keep out of the demo
            return False
        years = (eff - s.rank_date).days / 365.25 if s.rank_date else 0
        return years >= (rank.min_years_to_next or 2)

    def next_rank(self, s: Soldier) -> Rank:
        cur = self.rank_by_id[s.current_rank_id]
        return min((r for r in self.ranks.values() if r.sort_order > cur.sort_order), key=lambda r: r.sort_order)

    def apply_items(self, d: Decision) -> None:
        """Same state changes as the approve endpoint (app/api/v1/decisions.py)."""
        eff = d.effective_date
        for it in d.items:
            s = self.db.get(Soldier, it.soldier_id)
            it.old_rank_id, it.old_position_id, it.old_unit_id = s.current_rank_id, s.current_position_id, s.current_unit_id
            it.old_rank_date, it.old_position_date = s.rank_date, s.position_date
            it.old_unit_date, it.old_from_unit_text = s.unit_transfer_date, s.from_unit_text
            if it.new_rank_id:
                s.current_rank_id, s.rank_date = it.new_rank_id, eff
            if it.new_position_id:
                s.current_position_id, s.position_date = it.new_position_id, eff
            if it.new_unit_id and it.new_unit_id != s.current_unit_id:
                add_movement(self.db, s.id, s.current_unit_id, "out", "transfer_out", eff, "decisions", d.id)
                add_movement(self.db, s.id, it.new_unit_id, "in", "transfer_in", eff, "decisions", d.id)
                s.from_unit_text = self.db.get(Unit, s.current_unit_id).name_kh
                s.current_unit_id, s.unit_transfer_date = it.new_unit_id, eff
            add_history(self.db, s, d.kind, eff, old_rank=it.old_rank_id, new_rank=it.new_rank_id,
                        old_position=it.old_position_id, new_position=it.new_position_id,
                        old_unit=it.old_unit_id, new_unit=it.new_unit_id, decision_id=d.id,
                        note=f"{DECISION_KINDS[d.kind]} លេខ {d.decision_no}")
        # approved by the director on the decision date: the records are updated at once
        d.status, d.approved_by = "approved", self.admin.id
        d.approved_at = datetime.combine(d.decision_date, datetime.min.time()) + timedelta(hours=15)
        d.published_by, d.published_at = self.admin.id, d.approved_at
        d.status_changed_at = d.published_at

    def pick_items(self, kind: str, eff: date, count: int, used: set[int]) -> list[DecisionItem]:
        rng = self.rng
        pool = [s for s in self.soldiers if s.id not in self.locked and s.id not in used]
        rng.shuffle(pool)
        items = []
        if kind == "promote":
            for s in pool:
                if self.eligible_for_promotion(s, eff):
                    items.append(DecisionItem(soldier_id=s.id, new_rank_id=self.next_rank(s).id))
                if len(items) == count:
                    break
        elif kind == "appoint":
            # deputies step up to head of office, staff officers to deputy
            moves = {"អនុប្រធានការិយាល័យ": "ប្រធានការិយាល័យ", "មន្ត្រីជំនាញ": "អនុប្រធានការិយាល័យ",
                     "មេសេនាតូច": "មេសេនាធំ", "អនុប្រធាននាយកដ្ឋាន": "ប្រធាននាយកដ្ឋាន", "មេក្រុម": "មេសេនាតូច"}
            for s in pool:
                cur = self.position_name(s)
                if cur in moves and self.rank_by_id[s.current_rank_id].name_kh in OFFICER_RANKS | {"ព្រឹន្ទបាលឯក"}:
                    items.append(DecisionItem(soldier_id=s.id, new_position_id=self.positions[moves[cur]].id,
                                              note="តាមសំណើរបស់អង្គភាព"))
                if len(items) == count:
                    break
        else:  # transfer to another working-level unit of the same kind
            parents = {u.parent_id for u in self.units.values()}
            for s in pool:
                kind_s = self.unit_kind[s.current_unit_id]
                targets = [u for u in self.units.values() if u.id not in parents and u.id != s.current_unit_id
                           and self.unit_kind[u.id] == kind_s]
                if targets and self.position_name(s) in {"មន្ត្រីជំនាញ", "មន្ត្រីរដ្ឋបាល", "ពលទាហាន", "មេក្រុម"}:
                    items.append(DecisionItem(soldier_id=s.id, new_unit_id=rng.choice(targets).id,
                                              note="ផ្លាស់ប្ដូរតាមតម្រូវការការងារ"))
                if len(items) == count:
                    break
        used.update(it.soldier_id for it in items)
        return items

    def build_decisions(self, out_docs: dict[str, DocumentOutgoing]) -> None:
        plan = [
            # kind, decision_date, effective_date, count, status, notes
            ("appoint", date(2025, 3, 10), date(2025, 3, 15), 3, "approved", "តែងតាំងមុខតំណែងប្រធាន និងអនុប្រធានការិយាល័យ"),
            ("promote", date(2025, 6, 20), date(2025, 7, 1), 10, "approved", "ដំឡើងឋានន្តរស័ក្តិប្រចាំឆមាសទី១ ឆ្នាំ២០២៥"),
            ("transfer", date(2025, 8, 25), date(2025, 9, 1), 4, "approved", "ផ្លាស់ប្ដូរកងឯកភាពតាមតម្រូវការការងារ"),
            ("promote", date(2025, 12, 22), date(2026, 1, 1), 12, "approved", "ដំឡើងឋានន្តរស័ក្តិប្រចាំឆមាសទី២ ឆ្នាំ២០២៥"),
            ("appoint", date(2026, 2, 16), date(2026, 3, 1), 4, "approved", "តែងតាំងមុខតំណែងថ្នាក់ដឹកនាំអង្គភាព"),
            ("transfer", date(2026, 5, 18), date(2026, 6, 1), 3, "approved", "ផ្លាស់ប្ដូរកងឯកភាពតាមសំណើរបស់អង្គភាព"),
            ("promote", date(2026, 6, 22), date(2026, 7, 1), 8, "approved", "ដំឡើងឋានន្តរស័ក្តិប្រចាំឆមាសទី១ ឆ្នាំ២០២៦"),
            ("transfer", date(2026, 7, 20), date(2026, 8, 1), 1, "cancelled", "បានលុបចោលតាមសំណើរបស់សាមីខ្លួន"),
        ]
        used_by_kind = {"promote": set(), "appoint": set(), "transfer": set()}
        for kind, d_date, eff, count, status, notes in plan:
            doc = out_docs[f"decision:{d_date.isoformat()}"]
            d = Decision(kind=kind, decision_no=doc.outgoing_no, decision_date=d_date, effective_date=eff,
                         issued_by=ISSUER, outgoing_document_id=doc.id, status="draft", notes=notes,
                         created_by=self.admin.id, updated_by=self.admin.id)
            # a soldier promoted twice in a row would need the minimum years in between; reset per half-year
            d.items = self.pick_items(kind, eff, count, used_by_kind[kind] if kind != "promote" else set())
            self.db.add(d)
            self.db.flush()
            if status == "approved":
                self.apply_items(d)
            else:  # stopped during the approval workflow
                d.status = "rejected"
                d.status_changed_at = datetime.combine(d_date, datetime.min.time()) + timedelta(hours=10)
                self._snapshot_old(d)
            self.db.flush()

        # drafts waiting for approval
        for kind, count, notes in [("promote", 6, "សំណើដំឡើងឋានន្តរស័ក្តិប្រចាំឆមាសទី២ ឆ្នាំ២០២៦"),
                                   ("appoint", 2, "សេចក្ដីព្រាងតែងតាំងមុខតំណែង"),
                                   ("transfer", 2, "សេចក្ដីព្រាងផ្លាស់ប្ដូរកងឯកភាព")]:
            eff = date(TODAY.year + 1, 1, 1) if kind == "promote" else TODAY + timedelta(days=20)
            d = Decision(kind=kind, decision_no="",
                         decision_date=TODAY - timedelta(days=self.rng.randint(2, 10)), effective_date=eff,
                         issued_by=ISSUER, status="draft", status_changed_at=datetime.now(), notes=notes,
                         created_by=self.admin.id, updated_by=self.admin.id)
            d.items = self.pick_items(kind, eff, count, used_by_kind[kind] if kind != "promote" else set())
            self.db.add(d)
            self.db.flush()
            self._snapshot_old(d)

    def _snapshot_old(self, d: Decision) -> None:
        for it in d.items:
            s = self.db.get(Soldier, it.soldier_id)
            it.old_rank_id, it.old_position_id, it.old_unit_id = s.current_rank_id, s.current_position_id, s.current_unit_id

    # ------------------------------------------------------------ documents
    def build_documents(self) -> dict[str, DocumentOutgoing]:
        rng = self.rng
        decision_dates = [date(2025, 3, 10), date(2025, 6, 20), date(2025, 8, 25), date(2025, 12, 22),
                          date(2026, 2, 16), date(2026, 5, 18), date(2026, 6, 22), date(2026, 7, 20)]
        decision_subjects = {
            date(2025, 3, 10): ("សេចក្ដីសម្រេច", "ស្ដីពីការតែងតាំងមុខតំណែងប្រធាន និងអនុប្រធានការិយាល័យ"),
            date(2025, 6, 20): ("ប្រកាស", "ស្ដីពីការដំឡើងឋានន្តរស័ក្តិជូននាយទាហាន និងនាយទាហានរង ប្រចាំឆមាសទី១ ឆ្នាំ២០២៥"),
            date(2025, 8, 25): ("សេចក្ដីសម្រេច", "ស្ដីពីការផ្លាស់ប្ដូរកងឯកភាពជូនយោធិន"),
            date(2025, 12, 22): ("ប្រកាស", "ស្ដីពីការដំឡើងឋានន្តរស័ក្តិជូននាយទាហាន និងនាយទាហានរង ប្រចាំឆមាសទី២ ឆ្នាំ២០២៥"),
            date(2026, 2, 16): ("សេចក្ដីសម្រេច", "ស្ដីពីការតែងតាំងមុខតំណែងថ្នាក់ដឹកនាំអង្គភាព"),
            date(2026, 5, 18): ("សេចក្ដីសម្រេច", "ស្ដីពីការផ្លាស់ប្ដូរកងឯកភាពជូនយោធិន"),
            date(2026, 6, 22): ("ប្រកាស", "ស្ដីពីការដំឡើងឋានន្តរស័ក្តិជូននាយទាហាន និងនាយទាហានរង ប្រចាំឆមាសទី១ ឆ្នាំ២០២៦"),
            date(2026, 7, 20): ("សេចក្ដីសម្រេច", "ស្ដីពីការផ្លាស់ប្ដូរកងឯកភាពជូនយោធិន"),
        }
        specs = []  # (date, key, type_name, subject, unit)
        for d in decision_dates:
            t, subj = decision_subjects[d]
            specs.append((d, f"decision:{d.isoformat()}", t, subj, self.units["GDA-PER"]))
        units = [u for u in self.units.values() if u.level in (2, 3)]
        for i in range(34):
            d = self.rand_date(date(2025, 1, 6), TODAY - timedelta(days=1))
            if d.weekday() >= 5:
                d -= timedelta(days=d.weekday() - 4)
            t, subj = rng.choice(OUTGOING_SUBJECTS)
            specs.append((d, f"general:{i}", t, subj, rng.choice(units)))
        specs.sort(key=lambda x: (x[0], x[1]))

        out: dict[str, DocumentOutgoing] = {}
        seq_by_year: dict[int, int] = {}
        for d, key, t, subj, unit in specs:
            seq_by_year[d.year] = seq_by_year.get(d.year, 0) + 1
            seq = seq_by_year[d.year]
            head = self.heads.get(unit.id)
            doc = DocumentOutgoing(
                outgoing_no=f"{seq}/{str(d.year)[-2:]}", seq=seq, year=d.year, subject=subj, doc_date=d,
                document_type_id=self.doc_types[t].id, unit_id=unit.id,
                recipient_name=head.name_kh if head else None, recipient_phone=head.phone if head else None,
                status="sent", created_by=self.admin.id, updated_by=self.admin.id)
            self.db.add(doc)
            out[key] = doc

        senders = [u.name_kh for u in self.units.values() if u.level in (2, 3)] + EXTERNAL_SENDERS
        in_specs = []
        for _ in range(48):
            d = self.rand_date(date(2025, 1, 3), TODAY - timedelta(days=1))
            if d.weekday() >= 5:
                d -= timedelta(days=d.weekday() - 4)
            in_specs.append(d)
        in_specs.sort()
        no_by_year: dict[int, int] = {}
        for d in in_specs:
            no_by_year[d.year] = no_by_year.get(d.year, 0) + 1
            idx = rng.randrange(len(INCOMING_SUBJECTS))
            subj = INCOMING_SUBJECTS[idx].format(n=kh(rng.randint(2, 15)), y=kh(d.year), m=kh(d.month),
                                                 h=kh(1 if d.month <= 6 else 2), q=kh((d.month - 1) // 3 + 1))
            sender = rng.choice(EXTERNAL_SENDERS if idx in (8, 9) else senders)
            self.db.add(DocumentIncoming(
                incoming_no=f"{no_by_year[d.year]:04d}", year=d.year, subject=subj,
                doc_date=d - timedelta(days=rng.randint(1, 5)), received_date=d,
                document_type_id=self.doc_types[INCOMING_TYPES[idx]].id, from_unit=sender, status="received",
                created_by=self.admin.id, updated_by=self.admin.id))
        self.db.flush()
        return out

    # ------------------------------------------------------------ records
    def build_training(self) -> None:
        rng = self.rng
        courses = [
            ("វគ្គបណ្ដុះបណ្ដាលនាយទាហានជាន់ខ្ពស់ ជំនាន់ទី១២", "long", "សាលាបញ្ជាការ និងសេនាធិការ", "Cambodia",
             date(2025, 2, 3), date(2025, 12, 19), ["វរសេនីយ៍ត្រី", "វរសេនីយ៍ទោ"], 5, "ការពារ និងអន្តរាគមន៍"),
            ("វគ្គបណ្ដុះបណ្ដាលនាយទាហានជាន់ខ្ពស់ ជំនាន់ទី១៣", "long", "សាលាបញ្ជាការ និងសេនាធិការ", "Cambodia",
             date(2026, 2, 2), date(2026, 12, 18), ["វរសេនីយ៍ត្រី", "អនុសេនីយ៍ឯក"], 4, "ការពារ និងអន្តរាគមន៍"),
            ("វគ្គបណ្ដុះបណ្ដាលនាយទាហានថ្នាក់មធ្យម", "long", "បណ្ឌិត្យសភាការពារជាតិ", "Vietnam",
             date(2025, 9, 1), date(2026, 6, 30), ["អនុសេនីយ៍ឯក", "អនុសេនីយ៍ទោ"], 2, "ថ្មើរជើង"),
            ("វគ្គបណ្ដុះបណ្ដាលគ្រប់គ្រងរដ្ឋបាល និងឯកសារ", "short", "មជ្ឈមណ្ឌលបណ្ដុះបណ្ដាល", "Cambodia",
             date(2025, 4, 21), date(2025, 5, 2), None, 12, "រដ្ឋបាល និងបុគ្គលិក"),
            ("វគ្គភាសាអង់គ្លេសកម្រិតមធ្យម", "short", "មជ្ឈមណ្ឌលបណ្ដុះបណ្ដាល", "Cambodia",
             date(2025, 6, 2), date(2025, 8, 29), None, 10, None),
            ("វគ្គព័ត៌មានវិទ្យាកម្រិតមូលដ្ឋាន", "short", "នាយកដ្ឋានព័ត៌មានវិទ្យា", "Cambodia",
             date(2025, 10, 6), date(2025, 10, 24), None, 14, "ព័ត៌មានវិទ្យា"),
            ("វគ្គសង្គ្រោះបឋម", "short", "មជ្ឈមណ្ឌលសុខាភិបាល", "Cambodia",
             date(2026, 3, 9), date(2026, 3, 13), None, 15, "វេជ្ជសាស្ត្រ"),
            ("វគ្គបច្ចេកទេសការពារ និងអន្តរាគមន៍", "short", "បញ្ជាការដ្ឋានកងការពារ", "Cambodia",
             date(2026, 8, 3), date(2026, 8, 28), None, 16, "ការពារ និងអន្តរាគមន៍"),
            ("វគ្គគ្រប់គ្រងភស្តុភារ", "short", "មហាវិទ្យាល័យភស្តុភារ", "China",
             date(2026, 4, 6), date(2026, 5, 29), None, 3, "ភស្តុភារ"),
        ]
        cert = 0
        for name, ctype, inst, country, start, end, ranks, n, spec in courses:
            level = "refresher" if name.startswith(("វគ្គបច្ចេកទេស", "វគ្គសង្គ្រោះ", "វគ្គភាសា")) else "basic"
            c = TrainingCourse(name=name, course_type=ctype, level=level, institution=inst,
                               country_id=self.countries[country].id,
                               specialty_id=self.specialties[spec].id if spec else None, start_date=start, end_date=end,
                               created_by=self.admin.id, updated_by=self.admin.id)
            pool = [s for s in self.soldiers if s.id not in self.locked and s.enlistment_date < start
                    and (ranks is None or self.rank_by_id[s.current_rank_id].name_kh in ranks)]
            done = end < TODAY
            for s in rng.sample(pool, min(n, len(pool))):
                cert += 1
                c.participants.append(TrainingParticipant(
                    soldier_id=s.id, result=rng.choice(["ល្អណាស់", "ល្អ", "ល្អ", "មធ្យម"]) if done else None,
                    certificate_no=f"{cert:04d}/{str(end.year)[-2:]}" if done else None))
                if not done and ctype == "long":
                    s.status_id = self.lk["soldier_status"]["studying"].id
            self.db.add(c)
        self.db.flush()

    def build_awards_and_discipline(self) -> None:
        rng = self.rng
        pool = [s for s in self.soldiers if s.id not in self.locked]
        no_by_year: dict[int, int] = {}
        for d in sorted(self.rand_date(date(2025, 1, 15), TODAY - timedelta(days=3)) for _ in range(42)):
            s = rng.choice(pool)
            no = no_by_year[d.year] = no_by_year.get(d.year, 0) + 1
            type_code = rng.choice(["card", "card", "card", "letter", "letter", "medal"])
            self.db.add(AwardRecord(
                soldier_id=s.id, award_type_id=self.lk["award_type"][type_code].id,
                reason=rng.choice(AWARD_REASONS).format(y=kh(d.year if d.month > 3 else d.year - 1)),
                decision_no=f"{no:03d}/{str(d.year)[-2:]} ស.ស.រ", decision_date=d,
                created_by=self.admin.id, updated_by=self.admin.id))
        kinds = list(self.lk["discipline_type"].values())
        dates = sorted(self.rand_date(date(2025, 2, 1), TODAY - timedelta(days=10)) for _ in range(7))
        for i, d in enumerate(dates):
            s = rng.choice(pool)
            dtype = kinds[min(i % 3, len(kinds) - 1)]
            rec = DisciplineRecord(
                soldier_id=s.id, discipline_type_id=dtype.id,
                reason=rng.choice(DISCIPLINE_REASONS).format(d=kh(rng.randint(3, 10))),
                decision_no=f"{sum(x.year == d.year for x in dates[:i + 1]):03d}/{str(d.year)[-2:]} វ.ន", decision_date=d,
                start_date=d + timedelta(days=1), end_date=d + timedelta(days=rng.choice([15, 30, 60])),
                created_by=self.admin.id, updated_by=self.admin.id)
            self.db.add(rec)
        # one ongoing suspension
        active = self.lk["soldier_status"]["active"].id
        s = rng.choice([x for x in pool if x.status_id == active]) if pool else None
        if s:
            d = TODAY - timedelta(days=12)
            self.db.add(DisciplineRecord(
                soldier_id=s.id, discipline_type_id=self.lk["discipline_type"]["ពិន័យដាក់វិន័យ"].id,
                reason="ប្រព្រឹត្តអំពើល្មើសនឹងវិន័យយោធា ក្នុងពេលបំពេញភារកិច្ច កំពុងរង់ចាំការស៊ើបអង្កេត",
                decision_no=f"{sum(x.year == d.year for x in dates) + 1:03d}/{str(d.year)[-2:]} វ.ន",
                decision_date=d, start_date=d + timedelta(days=1),
                end_date=d + timedelta(days=90), created_by=self.admin.id, updated_by=self.admin.id))
            s.status_id = self.lk["soldier_status"]["suspended"].id
            self.locked.add(s.id)
        self.db.flush()

    def _leave(self, s: Soldier, record, status_code: str, table: str, reason: str) -> None:
        """Same effect as the retirement/separation after_save hook (app/api/v1/records.py)."""
        record.previous_status_id, record.previous_unit_id = s.status_id, s.current_unit_id
        self.db.add(record)
        self.db.flush()
        s.status_id = self.lk["soldier_status"][status_code].id
        add_movement(self.db, s.id, record.previous_unit_id, "out", reason, record.effective_date, table, record.id)
        self.locked.add(s.id)

    def build_leavers(self) -> None:
        rng = self.rng
        units_admin = [u for u in self.units.values() if u.level == 4 and self.unit_kind[u.id] != "troop"]
        no = 0
        # pensions: soldiers who reached 60 in 2025–2026
        for birthday in (date(1965, 2, 14), date(1965, 8, 3), date(1965, 11, 27), date(1966, 4, 9), date(1966, 7, 21)):
            if date(birthday.year + 60, birthday.month, 1) >= TODAY:
                continue
            s = self.make_soldier(rng.choice(units_admin), "មន្ត្រីជំនាញ",
                                  rng.choice(["វរសេនីយ៍ទោ", "វរសេនីយ៍ឯក", "ព្រឹន្ទបាលឯក"]), gender="M",
                                  dob=birthday, enlisted=date(birthday.year + 21, 3, 1))
            eff = date(birthday.year + 60 + (birthday.month == 12), birthday.month % 12 + 1, 1)
            no += 1
            self._leave(s, RetirementRecord(
                soldier_id=s.id, type="pension", decision_no=f"{no:03d}/{str(eff.year)[-2:]} ប្រ.ក",
                decision_date=eff - timedelta(days=25), effective_date=eff,
                pension_amount=rng.choice([1_250_000, 1_480_000, 1_620_000, 1_890_000]),
                notes="ចូលនិវត្តន៍តាមអាយុកំណត់", created_by=self.admin.id, updated_by=self.admin.id),
                "retired", "retirement_records", "retire")
        # category 2
        cand = [s for s in self.soldiers if s.id not in self.locked and self.unit_kind[s.current_unit_id] == "troop"
                and self.rank_by_id[s.current_rank_id].name_kh.startswith("ពល")]
        s = rng.choice(cand)
        no += 1
        self._leave(s, RetirementRecord(
            soldier_id=s.id, type="category2", decision_no=f"{no:03d}/26 ប្រ.ក", decision_date=date(2026, 3, 20),
            effective_date=date(2026, 4, 1), notes="រងរបួសក្នុងពេលបំពេញភារកិច្ច មិនអាចបន្តការងារបាន",
            created_by=self.admin.id, updated_by=self.admin.id), "category2", "retirement_records", "category2")
        # separations
        for code, eff, note in [("resign", date(2025, 10, 1), "លាឈប់ដោយស្ម័គ្រចិត្ត ដើម្បីបន្តការសិក្សា"),
                                ("transfer_out", date(2026, 2, 1), "ផ្ទេរទៅបម្រើការងារនៅក្រសួងផ្សេង"),
                                ("death", date(2025, 6, 12), "ទទួលមរណភាពដោយជំងឺ"),
                                ("desert", date(2026, 5, 4), "បោះបង់ការងារលើសពី ៣០ ថ្ងៃ គ្មានមូលហេតុ")]:
            cand = [x for x in self.soldiers if x.id not in self.locked and x.enlistment_date < eff
                    and self.position_name(x) in {"ពលទាហាន", "មន្ត្រីរដ្ឋបាល", "មន្ត្រីជំនាញ"}]
            s = rng.choice(cand)
            no += 1
            self._leave(s, SeparationRecord(
                soldier_id=s.id, reason_id=self.lk["separation_reason"][code].id,
                decision_no=f"{no:03d}/{str(eff.year)[-2:]} ស.ស.រ", decision_date=eff - timedelta(days=10),
                effective_date=eff, notes=note, created_by=self.admin.id, updated_by=self.admin.id),
                "separated", "separation_records", "separate")
        self.db.flush()


def build_staffing(db, rng: random.Random) -> int:
    """Staffing table for every unit from its current roster: quota = serving soldiers, sometimes with
    a vacancy, and the rank range seen in that position."""
    from app.models import UnitPosition
    from app.services.staffing import serving

    rows = db.execute(serving(select(Soldier.current_unit_id, Soldier.current_position_id, func.count(Soldier.id),
                                     func.min(Rank.sort_order), func.max(Rank.sort_order)))
                      .join(Rank, Rank.id == Soldier.current_rank_id)
                      .where(Soldier.current_unit_id.is_not(None), Soldier.current_position_id.is_not(None))
                      .group_by(Soldier.current_unit_id, Soldier.current_position_id)).all()
    rank_by_order = {r.sort_order: r.id for r in db.scalars(select(Rank))}
    added = 0
    for unit_id, position_id, count, low, high in rows:
        if db.scalar(select(UnitPosition.id).where(UnitPosition.unit_id == unit_id, UnitPosition.position_id == position_id)):
            continue
        db.add(UnitPosition(unit_id=unit_id, position_id=position_id, quota=count + (rng.random() < 0.3),
                            min_rank_id=rank_by_order.get(low), max_rank_id=rank_by_order.get(min(high + 1, 100))))
        added += 1
    db.flush()
    return added


# one demo user per approval level (roles from scripts/seed.py)
# one demo user per role of the approval workflow (New.txt §12; roles from scripts/seed.py)
WORKFLOW_USERS = [
    ("assistant", "ឈឹម សុផល", "Assistant"),
    ("deputy.office", "ទេព សុគន្ធា", "Deputy Chief of Office"),
    ("chief.office", "ហ៊ុល វណ្ណៈ", "Chief of Office"),
    ("deputy.director", "ខៀវ ចំរើន", "Deputy Director"),
    ("director", "វង្ស សំណាង", "Director"),
]
STEP_COMMENTS = {  # opinion given when leaving a step
    "draft": "ភ្ជាប់សំណើ និងឯកសារគ្រប់គ្រាន់", "deputy_office": "បានទទួលទិស — ពិនិត្យលក្ខខណ្ឌ ក្របខណ្ឌ និងវិន័យ គ្រប់គ្រាន់",
    "chief_office": "ត្រឹមត្រូវតាមក្របខណ្ឌ", "deputy_director": "បានបូកសរុប ដាក់ជូននាយកសម្រេច", "submitted": "សម្រេចឯកភាព",
}


def build_workflow(db, password: str) -> None:
    """Approval log for the demo decisions: a user per workflow role, the full trail of every approved decision,
    rejected files with a reason, and drafts part-way through the workflow (one of them overdue)."""
    from app.core.permissions import FLOW, WORKFLOW_STAGES
    from app.models import DecisionStep

    roles = {r.name: r.id for r in db.scalars(select(Role))}
    users = {}
    for username, name, role in WORKFLOW_USERS:
        u = db.scalar(select(User).where(User.username == username))
        if not u:
            u = User(username=username, password_hash=hash_password(password), full_name=name, role_id=roles[role])
            db.add(u)
            db.flush()
        users[role] = u
    # who acts at each status: the assistant submits the draft, then one role per step
    actor_at = {"draft": users["Assistant"],
                **dict(zip(WORKFLOW_STAGES, (users[r] for _, _, r in WORKFLOW_USERS[1:]), strict=True))}

    def trail(d, until: str, start: datetime, step: timedelta) -> datetime:
        when, status = start, "draft"
        for to_status in FLOW[1:FLOW.index(until) + 1]:
            actor = actor_at[status]
            db.add(DecisionStep(decision_id=d.id, action="submit" if status == "draft" else "approve",
                                from_status=status, to_status=to_status, user_id=actor.id,
                                comment=STEP_COMMENTS.get(status), created_at=when))
            if to_status == "approved":  # the director's approval updates the records
                d.approved_by, d.approved_at = actor.id, when
                d.published_by, d.published_at = actor.id, when
            status, when = to_status, when + step
        d.status, d.status_changed_at = until, when - step
        return when

    decisions = db.scalars(select(Decision).where(Decision.deleted_at.is_(None)).order_by(Decision.id)).all()
    logged = set(db.scalars(select(DecisionStep.decision_id)))
    drafts = []
    for d in decisions:
        if d.id in logged:
            continue
        start = datetime.combine(d.decision_date, datetime.min.time()) - timedelta(days=8) + timedelta(hours=9)
        if d.status == "approved":
            trail(d, "approved", start, timedelta(days=2))
        elif d.status in ("rejected", "cancelled") and not d.published_at:
            when = trail(d, "chief_office", start, timedelta(days=1))
            db.add(DecisionStep(decision_id=d.id, action="reject", from_status="chief_office", to_status="rejected",
                                user_id=actor_at["chief_office"].id, created_at=when,
                                comment="យោធិនបានស្នើសុំមិនផ្លាស់ប្ដូរ — បញ្ចប់សំណុំរឿង"))
            d.status, d.status_changed_at = "rejected", when
        elif d.status == "draft":
            drafts.append(d)
    # drafts in progress: one waiting for the director longer than the overdue limit, one just received by the deputy
    for d, until, days_ago in zip(drafts, ("submitted", "deputy_office"), (9, 1), strict=False):
        trail(d, until, datetime.now() - timedelta(days=days_ago + 5), timedelta(days=1))
        d.status_changed_at = datetime.now() - timedelta(days=days_ago)
    db.flush()


def build_conscripts(db, rng: random.Random, count: int = 40) -> int:
    """Youth doing military service: person, registration, medical exam for those called, service for those serving."""
    from app.models import Conscript, ConscriptMedical, ConscriptRegistration, ConscriptService

    if db.scalar(select(func.count(Conscript.id))):
        return 0
    villages = db.execute(select(Village.id, District.id, District.province_id)
                          .join(Commune, Commune.id == Village.commune_id)
                          .join(District, District.id == Commune.district_id)).all()
    education = {lk.name_kh: lk.id for lk in db.scalars(select(Lookup).where(Lookup.category == "education_level"))}
    blood_types = list(db.scalars(select(Lookup.id).where(Lookup.category == "blood_type")))
    specialties = list(db.scalars(select(Specialty.id)))
    single = db.scalar(select(Lookup.id).where(Lookup.category == "marital_status", Lookup.code == "single"))
    companies = list(db.scalars(select(Unit).where(Unit.level == 4, Unit.code.like("GRD-%"))))
    private = db.scalar(select(Rank.id).where(Rank.name_kh == "ពលទាហានទោ"))
    statuses = ["registered"] * 14 + ["called"] * 9 + ["served"] * 9 + ["exempted"] * 4 + ["deferred"] * 4
    reasons = {"exempted": ["health", "family"], "deferred": ["study", "study", "family"]}
    for i in range(count):
        gender = "F" if rng.random() < 0.1 else "M"
        fam, given = rng.choice(FAMILY), rng.choice(MALE if gender == "M" else FEMALE)
        year = rng.choice([2025, 2025, 2026])
        dob = date(year - 18, rng.randint(1, 12), rng.randint(1, 28))
        vid, did, pid = rng.choice(villages)
        c = Conscript(conscript_no=f"KT-{year}-{i + 1:04d}", name_kh=f"{fam[0]} {given[0]}", name_latin=f"{fam[1]} {given[1]}",
                      gender=gender, date_of_birth=dob, birth_village_id=vid, current_village_id=vid,
                      national_id=f"3{rng.randint(10_000_000, 99_999_999)}", nationality="ខ្មែរ",
                      father_name=f"{fam[0]} {rng.choice(MALE)[0]}", mother_name=f"{rng.choice(FAMILY)[0]} {rng.choice(FEMALE)[0]}",
                      phone=f"0{rng.choice([12, 15, 16, 70, 77, 89, 96])} {rng.randint(100, 999)} {rng.randint(100, 999)}",
                      marital_status_id=single, children_count=0,
                      education_level_id=education.get(rng.choice(["អនុវិទ្យាល័យ", "វិទ្យាល័យ", "វិទ្យាល័យ", "បរិញ្ញាបត្ររង"])),
                      profession=rng.choice([None, "កសិករ", "កម្មករ", "សិស្ស", "ជាងម៉ាស៊ីន", "អ្នកបើកបរ"]),
                      languages=rng.choice([None, None, "អង់គ្លេស"]), driving_license=rng.choice([None, None, "A", "B"]),
                      blood_type_id=rng.choice(blood_types) if blood_types else None,
                      specialty_id=rng.choice(specialties) if specialties and rng.random() < 0.5 else None)
        db.add(c)
        db.flush()
        status = statuses[i % len(statuses)]
        db.add(ConscriptRegistration(conscript_id=c.id, register_no=f"{year}/{pid:02d}/{i + 1:04d}", registration_year=year,
                                     duty_year=year if status in ("called", "served") else None, province_id=pid,
                                     district_id=did, status=status,
                                     reason=rng.choice(reasons[status]) if status in reasons else None))
        if status in ("called", "served") or (status == "exempted" and rng.random() < 0.5):
            exam = date(year, rng.randint(2, 4), rng.randint(1, 28))
            db.add(ConscriptMedical(conscript_id=c.id, exam_date=exam, height_cm=round(rng.uniform(155, 182), 1),
                                    weight_kg=round(rng.uniform(48, 78), 1),
                                    result="fail" if status == "exempted" else "pass",
                                    examiner="មជ្ឈមណ្ឌលសុខាភិបាល"))
        if status == "served" and companies:
            start = date(year, 6, 1)
            db.add(ConscriptService(conscript_id=c.id, start_date=start, end_date=date(year + 1, 11, 30),
                                    unit_id=rng.choice(companies).id, rank_id=private, role="ពលទាហាន",
                                    trainings="វគ្គហ្វឹកហ្វឺនយោធាមូលដ្ឋាន ៣ ខែ", order_no=f"{rng.randint(10, 99)}/{str(year)[-2:]} ប.ក"))
    db.flush()
    return count


def main(password: str, seed: int) -> None:
    db = SessionLocal()
    try:
        if db.scalar(select(func.count(Soldier.id))) or db.scalar(select(func.count(Unit.id))):
            sys.exit("Units or soldiers already exist – the demo dataset is only loaded into an empty system.")
        if not db.scalar(select(func.count(Village.id))):
            sys.exit("No villages found – run `python -m scripts.import_geo` first.")
        if not db.scalar(select(func.count(Position.id))) or not db.scalar(select(User.id).where(User.username == "admin")):
            sys.exit("Reference data missing – run `python -m scripts.seed` first.")

        b = Builder(db, random.Random(seed), password)
        b.build_units()
        b.users()
        b.build_soldiers()
        b.build_leavers()  # before decisions, so retirees are never promoted after leaving
        out_docs = b.build_documents()
        b.build_decisions(out_docs)
        b.build_training()
        b.build_awards_and_discipline()
        build_staffing(db, random.Random(seed))
        build_workflow(db, password)
        build_conscripts(db, random.Random(seed))
        db.commit()

        print(f"Demo data loaded: {len(b.units)} units, {len(b.soldiers)} soldiers, "
              f"{db.scalar(select(func.count(Decision.id)))} decisions, "
              f"{db.scalar(select(func.count(DocumentIncoming.id)))} incoming / "
              f"{db.scalar(select(func.count(DocumentOutgoing.id)))} outgoing documents.")
        print(f"Demo users (password {password}): officer, approver, viewer, guard.officer (Guard Command only), "
              f"and one per approval level: {', '.join(u for u, _, _ in WORKFLOW_USERS)}")
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--password", default="Demo@123", help="password for the demo users")
    ap.add_argument("--seed", type=int, default=2026, help="random seed (same seed = same data)")
    args = ap.parse_args()
    main(args.password, args.seed)
