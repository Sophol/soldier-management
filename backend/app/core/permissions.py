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
    # approval workflow: each level of the decision workflow is its own permission (action "approve" only)
    "wf_review": "លំហូរអនុម័ត ២. មន្ត្រីជំនាញពិនិត្យលក្ខខណ្ឌ",
    "wf_deputy_office": "លំហូរអនុម័ត ៣. នាយរងការិយាល័យ",
    "wf_chief_office": "លំហូរអនុម័ត ៤. ប្រធានការិយាល័យ",
    "wf_deputy_department": "លំហូរអនុម័ត ៥. នាយរងនាយកដ្ឋាន",
    "wf_director": "លំហូរអនុម័ត ៦. នាយកដ្ឋាន (នាយក)",
    "wf_leadership": "លំហូរអនុម័ត ៧. ថ្នាក់ដឹកនាំកំពូល",
    "wf_publish": "លំហូរអនុម័ត ៨. ចេញលិខិត និងផ្សព្វផ្សាយ",
    "conscripts": "យុវជនបំពេញកាតព្វកិច្ចយោធា",
    "conscript_medical": "ការពិនិត្យសុខភាពយុវជនកាតព្វកិច្ច",
    "users": "អ្នកប្រើប្រាស់",
    "roles": "តួនាទី និងសិទ្ធិ",
    "geography": "រាជធានី/ខេត្ត...ភូមិ",
    "lookups": "បញ្ជីទិន្នន័យជំនួយ",
    "settings": "ការកំណត់ប្រព័ន្ធ",
    "audit": "កំណត់ហេតុសកម្មភាព",
}

SYSTEM_MODULES = {"users", "roles", "settings", "audit"}

# modules that only use some of the actions (the permission matrix hides the others)
MODULE_ACTIONS: dict[str, list[str]] = {
    **{m: ["approve"] for m in MODULES if m.startswith("wf_")},
    "conscript_medical": ["view", "create", "update", "delete"],
}


def module_actions(module: str) -> list[str]:
    return MODULE_ACTIONS.get(module, ACTIONS)


# decision workflow (answer.txt): status = the step the decision is waiting at
WORKFLOW_STAGES: dict[str, str] = {  # status -> label; each needs permission wf_<status>.approve
    "review": "ពិនិត្យលក្ខខណ្ឌ (មន្ត្រីជំនាញ)",
    "deputy_office": "រង់ចាំនាយរងការិយាល័យ",
    "chief_office": "រង់ចាំប្រធានការិយាល័យ",
    "deputy_department": "រង់ចាំនាយរងនាយកដ្ឋាន",
    "director": "រង់ចាំនាយកដ្ឋាន",
    "leadership": "រង់ចាំថ្នាក់ដឹកនាំកំពូល",
}
DECISION_STATUSES: dict[str, str] = {
    "draft": "ព្រាង",
    **WORKFLOW_STAGES,
    "approved": "បានអនុម័ត (រង់ចាំចេញលិខិត)",
    "published": "បានផ្សព្វផ្សាយ",
    "rejected": "បានបដិសេធ",
    "cancelled": "បានលុបចោល",
}
FLOW = ["draft", *WORKFLOW_STAGES, "approved", "published"]  # forward order
DECISION_MODULE = {"appoint": "decisions_appoint", "transfer": "decisions_transfer", "promote": "decisions_promote"}
