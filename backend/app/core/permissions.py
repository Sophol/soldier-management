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
    "id_cards": "ការងារអត្តសញ្ញាណប័ណ្ណយោធិន",
    "retirement": "សោធននិវត្តន៍ និងយោធិនប្រភេទ២",
    "separation": "យោធិនចេញពីជួរ",
    "reports": "របាយការណ៍",
    # approval workflow (New.txt §12): each level is its own permission (action "approve" only)
    "wf_deputy_office": "លំហូរអនុម័ត ២. នាយរងការិយាល័យ (ទទួលទិស)",
    "wf_chief_office": "លំហូរអនុម័ត ៣. នាយការិយាល័យ",
    "wf_deputy_director": "លំហូរអនុម័ត ៤. នាយករង (បូកសរុប)",
    "wf_director": "លំហូរអនុម័ត ៥. នាយក (អនុម័ត)",
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


# decision workflow (New.txt §12): ជំនួយការ enters and submits -> នាយរងការិយាល័យ receives it (ទទួលទិស) ->
# នាយការិយាល័យ -> នាយករង consolidates (បូកសរុប) -> submitted to នាយក (កំពុងដាក់សំណើ) -> approved (អនុម័ត).
# The status is the step the decision is waiting at; soldier records change when the នាយក approves.
WORKFLOW_STAGES: dict[str, str] = {  # status -> label
    "deputy_office": "រង់ចាំនាយរងការិយាល័យ (ទទួលទិស)",
    "chief_office": "រង់ចាំនាយការិយាល័យ",
    "deputy_director": "រង់ចាំនាយករង (បូកសរុប)",
    "submitted": "កំពុងដាក់សំណើ (រង់ចាំនាយក)",
}
STAGE_PERMISSION: dict[str, str] = {  # status -> module whose "approve" lets a user act at that step
    "deputy_office": "wf_deputy_office",
    "chief_office": "wf_chief_office",
    "deputy_director": "wf_deputy_director",
    "submitted": "wf_director",
}
DECISION_STATUSES: dict[str, str] = {
    "draft": "ព្រាង",
    **WORKFLOW_STAGES,
    "approved": "បានអនុម័ត",
    "rejected": "បានបដិសេធ",
    "cancelled": "បានលុបចោល",
}
# statuses of the earlier 8-step workflow, still found in approval logs
LEGACY_STATUSES = {"review": "ពិនិត្យលក្ខខណ្ឌ (មន្ត្រីជំនាញ)", "deputy_department": "រង់ចាំនាយរងនាយកដ្ឋាន",
                   "director": "រង់ចាំនាយកដ្ឋាន", "leadership": "រង់ចាំថ្នាក់ដឹកនាំកំពូល", "published": "បានផ្សព្វផ្សាយ"}
FLOW = ["draft", *WORKFLOW_STAGES, "approved"]  # forward order
DECISION_MODULE = {"appoint": "decisions_appoint", "transfer": "decisions_transfer", "promote": "decisions_promote"}
