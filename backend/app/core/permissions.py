"""Module keys and actions used by role-based permissions."""

ACTIONS = ["view", "create", "update", "delete", "search", "print", "export", "approve"]

MODULES: dict[str, str] = {
    "dashboard": "ផ្ទាំងគ្រប់គ្រង",
    "org_units": "ស្ថាប័នកងឯកភាព",
    "ranks": "ឋានន្តរស័ក្តិ",
    "positions": "មុខតំណែង",
    "specialties": "ជំនាញឯកទេស",
    "doc_types": "ប្រភេទឯកសារ",
    "doc_in": "ឯកសារចូល",
    "doc_out": "ឯកសារចេញ",
    "soldiers": "គ្រប់គ្រងយោធិន",
    "strength": "ការងារកើនថយ",
    "decisions_appoint": "តែងតាំងមុខតំណែង",
    "decisions_transfer": "ផ្លាស់ប្ដូរ",
    "decisions_promote": "ដំឡើងឋានន្តរស័ក្តិ",
    "training": "ការងារបណ្ដុះបណ្ដាល",
    "discipline": "ការងារវិន័យ និងទណ្ឌកម្ម",
    "awards": "ការងារសរសើរ និងគ្រឿងឥស្សរិយយស",
    "retirement": "សោធននិវត្តន៍ និងយោធិនប្រភេទ២",
    "separation": "យោធិនចេញពីជួរ",
    "reports": "របាយការណ៍",
    "users": "អ្នកប្រើប្រាស់",
    "roles": "តួនាទី និងសិទ្ធិ",
    "geography": "រាជធានី/ខេត្ត...ភូមិ",
    "lookups": "បញ្ជីទិន្នន័យជំនួយ",
    "settings": "ការកំណត់ប្រព័ន្ធ",
    "audit": "កំណត់ហេតុសកម្មភាព",
}

SYSTEM_MODULES = {"users", "roles", "settings", "audit"}
DECISION_MODULE = {"appoint": "decisions_appoint", "transfer": "decisions_transfer", "promote": "decisions_promote"}
