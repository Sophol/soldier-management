"""Military ID cards (អត្តសញ្ញាណប័ណ្ណយោធិន): statuses, reasons and the SQL conditions shared by the card list,
the soldier list and the reports (001រចនាសម្ព័ន្ធ: cards still showing an old rank or position, cards about to
expire, and why a card was made or replaced)."""

from datetime import date

from sqlalchemy import and_, or_, select

from app.models import MilitaryCard, Soldier

CARD_STATUS = {"issued": "ចេញរួច", "pending": "មិនទាន់ចេញ", "expired": "ផុតកំណត់", "lost": "បាត់", "replaced": "ជំនួស"}
# មូលហេតុធ្វើ ឬប្ដូរប័ណ្ណ
CARD_REASONS = {
    "first": "ធ្វើលើកដំបូង", "promotion": "ឡើងឋានន្តរស័ក្តិ", "position": "ប្ដូរមុខតំណែង", "transfer": "ផ្លាស់ប្ដូរអង្គភាព",
    "expired": "ផុតកំណត់", "lost": "បាត់", "damaged": "ខូចខាត", "correction": "កែព័ត៌មានខុស", "other": "ផ្សេងៗ",
}
# why a card that is still valid no longer matches the soldier (ត្រូវធ្វើប័ណ្ណថ្មី)
OUTDATED = {"rank": "ឡើងស័ក្តិក្រោយថ្ងៃចេញប័ណ្ណ", "position": "ប្ដូរមុខតំណែងក្រោយថ្ងៃចេញប័ណ្ណ"}


def card_status(c: MilitaryCard) -> str:
    """An issued card past its expiry date is expired (ផុតកំណត់)."""
    if c.status == "issued" and c.expiry_date and c.expiry_date < date.today():
        return "expired"
    return c.status


def outdated_reasons(c: MilitaryCard) -> list[str]:
    """Keys of OUTDATED: the soldier was promoted / changed position after this (still valid) card was issued."""
    s = c.soldier
    if card_status(c) != "issued" or not c.issue_date or not s:
        return []
    out = []
    if s.rank_date and s.rank_date > c.issue_date:
        out.append("rank")
    if s.position_date and s.position_date > c.issue_date:
        out.append("position")
    return out


def valid_card_clause():
    """A card the soldier can use today: issued, not deleted and not past its expiry date."""
    return and_(MilitaryCard.deleted_at.is_(None), MilitaryCard.status == "issued",
                or_(MilitaryCard.expiry_date.is_(None), MilitaryCard.expiry_date >= date.today()))


def _changed_since_issue(kind: str | None):
    changed = {"rank": Soldier.rank_date > MilitaryCard.issue_date,
               "position": Soldier.position_date > MilitaryCard.issue_date}
    return changed[kind] if kind in changed else or_(*changed.values())


def outdated_card_clause(kind: str | None = None):
    """On military_cards rows: valid cards whose soldier was promoted (kind "rank"), changed position ("position")
    or either (None) after the card was issued, the same rule as outdated_reasons."""
    return and_(valid_card_clause(), MilitaryCard.issue_date.is_not(None),
                select(Soldier.id).where(Soldier.id == MilitaryCard.soldier_id, _changed_since_issue(kind)).exists())


def soldier_card_clause(kind: str):
    """On soldiers rows: "none" = no valid card (never issued, still pending, expired, lost...);
    "outdated" = a valid card that still shows an old rank or position."""
    cards = select(MilitaryCard.id).where(MilitaryCard.soldier_id == Soldier.id, valid_card_clause())
    if kind == "none":
        return ~cards.exists()
    return cards.where(MilitaryCard.issue_date.is_not(None), _changed_since_issue(None)).exists()
