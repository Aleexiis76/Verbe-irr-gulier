import streamlit as st
import pandas as pd
import io
import re
import json
import hashlib
import unicodedata
from difflib import SequenceMatcher
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from gtts import gTTS
import gspread
from google.oauth2.service_account import Credentials

# =====================================================================
# 1. MODÈLES DE DONNÉES
# =====================================================================

@dataclass(frozen=True)
class Verb:
    id: int
    level: str
    infinitive: str
    preterit: str
    past_participle: str
    translation: str

    def get_field(self, col_name: str) -> str:
        return {
            "Infinitive": self.infinitive,
            "Preterit": self.preterit,
            "Past Participle": self.past_participle,
            "Translation": self.translation
        }[col_name]


@dataclass
class SRSCard:
    verb_id: int
    state: str = "new"
    step: int = 0
    interval_days: int = 0
    due_timestamp: str = ""
    introduced_date: str = ""

    def is_due(self, now: datetime) -> bool:
        return True if not self.due_timestamp else datetime.fromisoformat(self.due_timestamp) <= now


@dataclass
class FieldFeedback:
    col: str
    user_val: str
    expected_val: str
    is_correct: bool
    hint: str = ""


@dataclass
class EvaluationResult:
    status: str  # "EXACT", "INCOMPLETE", "WRONG"
    missing_translations: List[str]
    verb: Verb
    given_col: str
    feedbacks: List[FieldFeedback]


# =====================================================================
# 2. ACCÈS AUX DONNÉES (CSV & GOOGLE SHEETS)
# =====================================================================

@st.cache_resource
def load_verbs() -> List[Verb]:
    df = pd.read_csv("verbs.csv", sep=";")
    return [
        Verb(
            id=int(idx),
            level=str(row["Level"]).strip(),
            infinitive=str(row["Infinitive"]).strip(),
            preterit=str(row["Preterit"]).strip(),
            past_participle=str(row["Past Participle"]).strip(),
            translation=str(row["Translation"]).strip()
        )
        for idx, row in df.iterrows()
    ]


class VerbRepository:
    def __init__(self):
        self._verbs = load_verbs()

    def get_all(self) -> List[Verb]:
        return self._verbs

    def get_by_id(self, verb_id: int) -> Verb:
        return self._verbs[verb_id]


@st.cache_resource
def get_gspread_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    sheet = gspread.authorize(creds).open_by_url(st.secrets["spreadsheet_url"])
    try:
        return sheet.worksheet("app_data")
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title="app_data", rows=100, cols=5)
        ws.append_row(["username", "pin_hash", "errors_json", "session_json", "srs_json"])
        return ws


class UserRepository:
    def __init__(self):
        self.ws = get_gspread_sheet()

    def _find_user_row(self, username: str) -> Tuple[Optional[int], Optional[Dict]]:
        for idx, row in enumerate(self.ws.get_all_records(), start=2):
            if str(row.get("username", "")).strip().lower() == username.strip().lower():
                return idx, row
        return None, None

    def _ensure_cache(self, username: str):
        if "db_cache" not in st.session_state or st.session_state.db_cache.get("username", "").lower() != username.strip().lower():
            row_idx, row_data = self._find_user_row(username)
            if row_data:
                raw_sess = json.loads(row_data.get("session_json") or "{}")
                st.session_state.db_cache = {
                    "username": str(row_data.get("username", username)).strip(),
                    "row_idx": row_idx,
                    "pin_hash": str(row_data.get("pin_hash", "")),
                    "errors": json.loads(row_data.get("errors_json") or "[]"),
                    "paused": {k: v for k, v in raw_sess.items() if not str(k).startswith("_")},
                    "failures": {int(k): int(v) for k, v in raw_sess.get("_failures", {}).items()},
                    "streak": int(raw_sess.get("_streak", 0)),
                    "last_login": str(raw_sess.get("_last_login", "")),
                    "srs": json.loads(row_data.get("srs_json") or "{}")
                }
            else:
                st.session_state.db_cache = {"username": ""}

    def get_user_pin_hash(self, username: str) -> Optional[str]:
        _, row = self._find_user_row(username)
        return str(row["pin_hash"]) if row else None

    def create_user(self, username: str, pin_hash: str) -> None:
        self.ws.append_row([username.strip(), pin_hash, "[]", "{}", "{}"])
        st.session_state.pop("db_cache", None)

    def list_all_users(self) -> List[str]:
        return [str(r.get("username", "")).strip() for r in self.ws.get_all_records() if str(r.get("username", "")).strip()]

    def update_user_pin(self, username: str, new_pin_hash: str) -> bool:
        row_idx, _ = self._find_user_row(username)
        if not row_idx: return False
        self.ws.update_cell(row_idx, 2, new_pin_hash)
        return True

    def delete_user(self, username: str) -> bool:
        row_idx, _ = self._find_user_row(username)
        if not row_idx: return False
        self.ws.delete_rows(row_idx)
        return True

    def get_errors(self, username: str) -> List[int]:
        self._ensure_cache(username)
        return list(st.session_state.db_cache.get("errors", []))

    def save_errors(self, username: str, error_ids: List[int], flush: bool = True) -> None:
        self._ensure_cache(username)
        st.session_state.db_cache["errors"] = error_ids
        if flush: self.flush_all(username)

    def get_failures(self, username: str) -> Dict[int, int]:
        self._ensure_cache(username)
        return dict(st.session_state.db_cache.get("failures", {}))

    def increment_failure(self, username: str, verb_id: int, flush: bool = False) -> None:
        self._ensure_cache(username)
        failures = st.session_state.db_cache.get("failures", {})
        failures[verb_id] = failures.get(verb_id, 0) + 1
        st.session_state.db_cache["failures"] = failures
        if flush: self.flush_all(username)

    def get_paused_session(self, username: str) -> Dict:
        self._ensure_cache(username)
        return dict(st.session_state.db_cache.get("paused", {}))

    def save_paused_session(self, username: str, session_data: Dict, flush: bool = True) -> None:
        self._ensure_cache(username)
        st.session_state.db_cache["paused"] = session_data
        if flush: self.flush_all(username)

    def get_srs_cards(self, username: str) -> Dict[int, SRSCard]:
        self._ensure_cache(username)
        return {int(k): SRSCard(**v) for k, v in st.session_state.db_cache.get("srs", {}).items()}

    def save_srs_cards(self, username: str, cards: Dict[int, SRSCard], flush: bool = True) -> None:
        self._ensure_cache(username)
        st.session_state.db_cache["srs"] = {str(k): asdict(v) for k, v in cards.items()}
        if flush: self.flush_all(username)

    def update_login_streak(self, username: str) -> int:
        self._ensure_cache(username)
        today = datetime.now().strftime("%Y-%m-%d")
        last_login = st.session_state.db_cache.get("last_login", "")
        streak = st.session_state.db_cache.get("streak", 0)
        if last_login == today: return streak

        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        streak = (streak + 1) if last_login == yesterday else 1
        st.session_state.db_cache["last_login"] = today
        st.session_state.db_cache["streak"] = streak
        self.flush_all(username)
        return streak

    def flush_all(self, username: str) -> None:
        self._ensure_cache(username)
        cache = st.session_state.db_cache
        row_idx = cache.get("row_idx")
        if not row_idx: return
        combined_sess = dict(cache.get("paused", {}))
        combined_sess["_failures"] = {str(k): v for k, v in cache.get("failures", {}).items()}
        combined_sess["_streak"] = cache.get("streak", 0)
        combined_sess["_last_login"] = cache.get("last_login", "")
        self.ws.update(
            range_name=f"C{row_idx}:E{row_idx}",
            values=[[json.dumps(cache.get("errors", [])), json.dumps(combined_sess), json.dumps(cache.get("srs", {}))]]
        )


# =====================================================================
# 3. SERVICES MÉTIER (AUTH, ÉVALUATION INTELLIGENTE, SRS, AUDIO)
# =====================================================================

class AuthService:
    ADMIN_USERNAME = "alexis"

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    @staticmethod
    def _hash_pin(pin: str) -> str:
        return hashlib.sha256(pin.strip().encode("utf-8")).hexdigest()

    @staticmethod
    def is_valid_pin(pin: str) -> bool:
        return len(pin.strip()) == 4 and pin.strip().isdigit()

    @classmethod
    def is_admin(cls, username: str) -> bool:
        return username.strip().lower() == cls.ADMIN_USERNAME

    def login(self, username: str, pin: str) -> Tuple[bool, str]:
        username = username.strip()
        if not username: return False, "Entre un pseudo."
        if not self.is_valid_pin(pin): return False, "Le code PIN doit contenir exactement 4 chiffres."
        stored_hash = self.user_repo.get_user_pin_hash(username)
        if not stored_hash:
            if self.is_admin(username):
                self.user_repo.create_user("Alexis", self._hash_pin(pin))
                return True, "Compte Administrateur initialisé."
            return False, "Ce compte n'existe pas. Demande à Alexis de te créer un accès."
        return (True, "Connexion réussie.") if stored_hash == self._hash_pin(pin) else (False, "Code PIN incorrect.")

    def admin_create_user(self, admin_user: str, new_u: str, pin: str) -> Tuple[bool, str]:
        if not self.is_admin(admin_user): return False, "Action réservée à l'administrateur."
        new_u = new_u.strip()
        if not new_u or not self.is_valid_pin(pin): return False, "Pseudo valide et PIN à 4 chiffres requis."
        if self.user_repo.get_user_pin_hash(new_u) is not None: return False, "Ce pseudo existe déjà."
        self.user_repo.create_user(new_u, self._hash_pin(pin))
        return True, f"Compte '{new_u}' créé."

    def admin_reset_pin(self, admin_user: str, target_u: str, new_pin: str) -> Tuple[bool, str]:
        if not self.is_admin(admin_user) or not self.is_valid_pin(new_pin): return False, "PIN à 4 chiffres requis."
        ok = self.user_repo.update_user_pin(target_u, self._hash_pin(new_pin))
        return (True, f"PIN de '{target_u}' mis à jour.") if ok else (False, "Utilisateur introuvable.")

    def admin_delete_user(self, admin_user: str, target_u: str) -> Tuple[bool, str]:
        if not self.is_admin(admin_user) or self.is_admin(target_u): return False, "Action non autorisée."
        ok = self.user_repo.delete_user(target_u)
        return (True, f"Compte '{target_u}' supprimé.") if ok else (False, "Utilisateur introuvable.")


class EvaluationService:
    COLS = ["Infinitive", "Preterit", "Past Participle", "Translation"]

    @staticmethod
    def normalize_en(text: str) -> str:
        text = re.sub(r'\s*/\s*', '/', text.strip().lower())
        return re.sub(r'\s+', ' ', text)

    @staticmethod
    def normalize_fr(token: str) -> str:
        token = token.strip().lower().replace("’", "'")
        token = ''.join(c for c in unicodedata.normalize('NFD', token) if unicodedata.category(c) != 'Mn')
        return re.sub(r'\s+', ' ', token)

    @classmethod
    def _expand_fr_variants(cls, raw_trans: str) -> Tuple[List[str], Dict[str, str]]:
        raw_parts = [p.strip() for p in re.split(r'[,/;]', raw_trans) if p.strip()]
        canonical, vmap = [], {}
        for part in raw_parts:
            canonical.append(part)
            vmap[cls.normalize_fr(part)] = part
            no_p = cls.normalize_fr(re.sub(r'\([^)]*\)', '', part))
            with_p = cls.normalize_fr(re.sub(r'[()]', '', part))
            if no_p: vmap[no_p] = part
            if with_p: vmap[with_p] = part
        return canonical, vmap

    @classmethod
    def _diagnose_en_error(cls, verb: Verb, col: str, user_en: str, expected_en: str) -> str:
        if not user_en:
            return "Champ laissé vide."
        # 1. Détection d'inversion de colonne
        other_cols = [c for c in ["Infinitive", "Preterit", "Past Participle"] if c != col]
        for oc in other_cols:
            other_val = cls.normalize_en(verb.get_field(oc))
            if user_en == other_val and other_val != expected_en:
                return f"🔄 Inversion : tu as tapé la forme de la colonne « {oc} » !"
        # 2. Détection de faute de frappe (proximité orthographique >= 75%)
        ratio = SequenceMatcher(None, user_en, expected_en).ratio()
        if ratio >= 0.72:
            return "⚠️ Faute de frappe : tu y étais presque, vérifie l'orthographe à une lettre près !"
        return ""

    def evaluate(self, verb: Verb, given_col: str, user_inputs: Dict[str, str]) -> EvaluationResult:
        missing_cols = [c for c in self.COLS if c != given_col]
        feedbacks: List[FieldFeedback] = []
        any_wrong = False
        missing_trans: List[str] = []

        for col in missing_cols:
            raw_user = user_inputs.get(col, "").strip()
            expected_raw = verb.get_field(col)

            if col != "Translation":
                u_en = self.normalize_en(raw_user)
                e_en = self.normalize_en(expected_raw)
                if u_en == e_en:
                    feedbacks.append(FieldFeedback(col, raw_user, expected_raw, True))
                else:
                    any_wrong = True
                    hint = self._diagnose_en_error(verb, col, u_en, e_en)
                    feedbacks.append(FieldFeedback(col, raw_user, expected_raw, False, hint))
            else:
                canonical_expected, variant_map = self._expand_fr_variants(expected_raw)
                user_tokens = [self.normalize_fr(t) for t in re.split(r'[,/;]', raw_user) if t.strip()]
                if not user_tokens:
                    any_wrong = True
                    feedbacks.append(FieldFeedback(col, raw_user, expected_raw, False, "Champ laissé vide."))
                    continue

                matched, token_wrong, typo_hint = set(), False, ""
                for u_tok in user_tokens:
                    if u_tok in variant_map:
                        matched.add(variant_map[u_tok])
                    else:
                        token_wrong = True
                        best_ratio = max((SequenceMatcher(None, u_tok, k).ratio() for k in variant_map), default=0)
                        if best_ratio >= 0.75:
                            typo_hint = "⚠️ Faute de frappe sur la traduction française !"

                if token_wrong:
                    any_wrong = True
                    feedbacks.append(FieldFeedback(col, raw_user, expected_raw, False, typo_hint))
                else:
                    missing_trans = [c for c in canonical_expected if c not in matched]
                    if missing_trans:
                        feedbacks.append(FieldFeedback(col, raw_user, expected_raw, False, f"Traduction partielle (manquant : {', '.join(missing_trans)})"))
                    else:
                        feedbacks.append(FieldFeedback(col, raw_user, expected_raw, True))

        status = "WRONG" if any_wrong else ("INCOMPLETE" if missing_trans else "EXACT")
        return EvaluationResult(status=status, missing_translations=missing_trans, verb=verb, given_col=given_col, feedbacks=feedbacks)


class SRSService:
    LONG_TERM_STEPS = [1, 3, 7, 16, 35, 90]
    MAX_NEW_PER_DAY = 10

    def __init__(self, verb_repo: VerbRepository, user_repo: UserRepository):
        self.verb_repo = verb_repo
        self.user_repo = user_repo

    def get_daily_summary(self, username: str) -> Tuple[int, int, int]:
        """Retourne (nouveaux_du_jour, a_revoir_maintenant, en_attente_minutes) sans modifier la base."""
        cards = self.user_repo.get_srs_cards(username)
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        introduced_today = sum(1 for c in cards.values() if c.introduced_date == today_str)
        quota = max(0, self.MAX_NEW_PER_DAY - introduced_today)
        unseen_count = sum(1 for v in self.verb_repo.get_all() if v.id not in cards)
        new_available = min(quota, unseen_count)

        due_new = sum(
            1 for c in cards.values()
            if c.is_due(now) and c.introduced_date == today_str and c.state == "learning" and c.step == 0
        )
        due_reviews = sum(1 for c in cards.values() if c.is_due(now)) - due_new
        waiting = sum(1 for c in cards.values() if not c.is_due(now) and c.state == "learning")

        return (new_available + due_new), due_reviews, waiting
        
    def get_daily_queue(self, username: str, force_early: bool = False) -> Tuple[List[SRSCard], int]:
        cards = self.user_repo.get_srs_cards(username)
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        introduced_today = sum(1 for c in cards.values() if c.introduced_date == today_str)
        quota = max(0, self.MAX_NEW_PER_DAY - introduced_today)

        if quota > 0:
            unseen = [v.id for v in self.verb_repo.get_all() if v.id not in cards]
            for vid in unseen[:quota]:
                cards[vid] = SRSCard(verb_id=vid, state="learning", step=0, interval_days=0, due_timestamp=now.isoformat(), introduced_date=today_str)
            if unseen[:quota]:
                self.user_repo.save_srs_cards(username, cards, flush=True)

        due_now, waiting = [], []
        for card in cards.values():
            if card.is_due(now) or (card.state == "learning" and force_early):
                due_now.append(card)
            elif card.state == "learning":
                waiting.append(card)

        due_now.sort(key=lambda c: c.due_timestamp)
        return due_now, len(waiting)

    def _next_good_interval(self, curr: int) -> int:
        for s in self.LONG_TERM_STEPS:
            if s > curr: return s
        return int(round(curr * 2.2))

    def get_button_labels(self, card: SRSCard) -> Dict[str, str]:
        if card.state in ("new", "learning"):
            g_lbl = "+10 min" if card.step == 0 else "+1 j"
            return {"again": "🔄 À revoir (+1 min)", "hard": "⚠️ Difficile (+5 min)", "good": f"✅ Correct ({g_lbl})", "easy": "⭐ Facile (+4 j)"}
        curr = max(1, card.interval_days)
        h_d = max(curr + 1, int(round(curr * 1.2)))
        g_d = self._next_good_interval(curr)
        e_d = self._next_good_interval(g_d)
        return {"again": "🔄 À revoir (+1 min)", "hard": f"⚠️ Difficile (+{h_d} j)", "good": f"✅ Correct (+{g_d} j)", "easy": f"⭐ Facile (+{e_d} j)"}

    def process_rating(self, username: str, verb_id: int, rating: str) -> None:
        cards = self.user_repo.get_srs_cards(username)
        card = cards.get(verb_id, SRSCard(verb_id=verb_id, state="learning"))
        now = datetime.now()

        if card.state in ("new", "learning"):
            if rating == "again":
                card.step = 0
                card.due_timestamp = (now + timedelta(minutes=1)).isoformat()
                self._record_error(username, verb_id)
            elif rating == "hard":
                card.due_timestamp = (now + timedelta(minutes=5)).isoformat()
            elif rating == "good":
                if card.step == 0:
                    card.step = 1
                    card.due_timestamp = (now + timedelta(minutes=10)).isoformat()
                else:
                    card.state, card.interval_days = "review", 1
                    card.due_timestamp = (now + timedelta(days=1)).isoformat()
            elif rating == "easy":
                card.state, card.interval_days = "review", 4
                card.due_timestamp = (now + timedelta(days=4)).isoformat()
        else:
            curr = max(1, card.interval_days)
            if rating == "again":
                card.state, card.step, card.interval_days = "learning", 0, 0
                card.due_timestamp = (now + timedelta(minutes=1)).isoformat()
                self._record_error(username, verb_id)
            elif rating == "hard":
                card.interval_days = max(curr + 1, int(round(curr * 1.2)))
                card.due_timestamp = (now + timedelta(days=card.interval_days)).isoformat()
            elif rating == "good":
                card.interval_days = self._next_good_interval(curr)
                card.due_timestamp = (now + timedelta(days=card.interval_days)).isoformat()
            elif rating == "easy":
                card.interval_days = self._next_good_interval(self._next_good_interval(curr))
                card.due_timestamp = (now + timedelta(days=card.interval_days)).isoformat()

        cards[verb_id] = card
        self.user_repo.save_srs_cards(username, cards, flush=True)

    def _record_error(self, username: str, verb_id: int) -> None:
        errors = self.user_repo.get_errors(username)
        if verb_id not in errors:
            errors.append(verb_id)
            self.user_repo.save_errors(username, errors, flush=False)
        self.user_repo.increment_failure(username, verb_id, flush=False)


class AudioService:
    @staticmethod
    @st.cache_data(show_spinner=False)
    def get_audio(text: str) -> bytes:
        tts = gTTS(text=text.replace("/", ", "), lang='en-US')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return fp.getvalue()
