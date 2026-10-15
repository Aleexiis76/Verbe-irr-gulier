import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import random
import io
import re
import json
import hashlib
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from gtts import gTTS
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="TOEIC Verbs", layout="centered")

# =====================================================================
# 1. DOMAIN MODELS (Modèles de données)
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
        mapping = {
            "Infinitive": self.infinitive,
            "Preterit": self.preterit,
            "Past Participle": self.past_participle,
            "Translation": self.translation
        }
        return mapping[col_name]


@dataclass
class SRSCard:
    verb_id: int
    state: str = "new"          # "new", "learning", "review"
    step: int = 0               # 0 = début apprentissage, 1 = palier +10min franchi
    interval_days: int = 0      # Intervalle long terme en jours
    due_timestamp: str = ""     # ISO format datetime
    introduced_date: str = ""   # YYYY-MM-DD

    def is_due(self, now: datetime) -> bool:
        if not self.due_timestamp:
            return True
        return datetime.fromisoformat(self.due_timestamp) <= now


@dataclass
class EvaluationResult:
    status: str                 # "EXACT", "INCOMPLETE", "WRONG"
    missing_translations: List[str]
    verb: Verb


# =====================================================================
# 2. REPOSITORIES (Accès aux données & Persistance)
# =====================================================================

class IVerbRepository(ABC):
    @abstractmethod
    def get_all(self) -> List[Verb]: pass

    @abstractmethod
    def get_by_id(self, verb_id: int) -> Verb: pass


class StaticVerbRepository(IVerbRepository):
    """Charge la liste officielle des 127 verbes irréguliers par niveau et fréquence."""

    CSV_DATA = """Level;Infinitive;Preterit;Past Participle;Translation
A1;be;was/were;been;être
A1;have;had;had;avoir
A1;do;did;done;faire
A1;say;said;said;dire
A1;go;went;gone;aller
A1;get;got;gotten;obtenir, recevoir
A1;make;made;made;faire, fabriquer
A1;know;knew;known;connaître, savoir
A1;think;thought;thought;penser
A1;take;took;taken;prendre
A1;see;saw;seen;voir
A1;come;came;come;venir
A1;find;found;found;trouver
A1;give;gave;given;donner
A1;tell;told;told;dire, raconter
A1;feel;felt;felt;toucher, se sentir
A1;become;became;become;devenir
A1;leave;left;left;partir de, sortir de, quitter
A1;put;put;put;mettre
A1;mean;meant;meant;signifier
A1;keep;kept;kept;garder
A1;let;let;let;laisser, permettre
A1;begin;began;begun;commencer
A1;hear;heard;heard;entendre
A1;run;ran;run;courir
A1;hold;held;held;tenir
A1;bring;brought;brought;amener, apporter
A1;write;wrote;written;écrire
A1;sit;sat;sat;(s')asseoir
A1;stand;stood;stood;être debout, se tenir debout
A1;lose;lost;lost;perdre
A1;pay;payed / paid;payed / paid;payer
A1;meet;met;met;rencontrer, retrouver
A1;set;set;set;mettre, poser, placer
A1;lead;led;led;conduire, mener
A1;understand;understood;understood;comprendre
A1;speak;spoke;spoken;parler
A1;read;read;read;lire
A1;spend;spent;spent;dépenser
A1;grow;grew;grown;grandir, pousser
A1;win;won;won;gagner
A1;buy;bought;bought;acheter
A1;send;sent;sent;envoyer
A1;build;built;built;bâtir, construire
A1;fall;fell;fallen;tomber
A1;cut;cut;cut;couper
A2;sell;sold;sold;vendre
A2;drive;drove;driven;conduire, mener
A2;break;broke;broken;casser
A2;wear;wore;worn;porter (des vêtements)
A2;hit;hit;hit;frapper
A2;eat;ate;eaten;manger
A2;teach;taught;taught;enseigner
A2;catch;caught;caught;attraper
A2;draw;drew;drawn;dessiner
A2;choose;chose;chosen;choisir
A2;seek;sought;sought;chercher, rechercher
A2;deal;dealt;dealt;distribuer
A2;fight;fought;fought;lutter, combattre
A2;throw;threw;thrown;jeter, lancer
A2;rise;rose;risen;se lever
A2;shoot;shot;shot;tirer
A2;lie;lay;lain;s'allonger
A2;lay;laid;laid;mettre, poser
A2;hang;hung;hung;suspendre, accrocher, monter, poser
A2;forget;forgot;forgotten;oublier
B1;shake;shook;shaken;secouer, agiter
B1;fly;flew;flown;voler
B1;sing;sang;sung;chanter
B1;beat;beat;beaten;battre, frapper
B1;be born;was born;been born;naître
B1;cost;cost;cost;coûter
B1;hurt;hurt;hurt;faire du mal à, se blesser
B1;strike;struck;stricken;frapper, faire grève
B1;sleep;slept;slept;dormir
B1;stick;stuck;stuck;piquer, planter, être collé
B1;drink;drank;drunk;boire
B1;hide;hid;hidden;cacher, se cacher
B1;ride;rode;ridden;monter à, faire du
B1;feed;fed;fed;nourrir
B1;fit;fit;fit;aller à, entrer
B1;spread;spread;spread;étendre, étaler, s'élargir
B1;blow;blew;blown;pousser, chasser, souffler
B1;shut;shut;shut;(re)fermer, repousser
B1;bear;bore;born;porter, se diriger
B1;wake;woke;woken;se réveiller, s'éveiller
B1;steal;stole;stolen;voler, dérober
B1;slide;slid;slid;glisser, se glisser
B1;bend;bent;bent;courber, plier, pencher, faire ployer, tordre
B1;tear;tore;torn;déchirer
B2;ring;rang;rung;sonner
B2;light;lit;lit;allumer, éclairer
B2;swing;swung;swung;se balancer, osciller
B2;dig;dug;dug;creuser, bêcher, arracher
B2;bind;bound;bound;attacher, entourer, bander
B2;quit;quit;quit;quitter, sortir, partir
B2;arise;arose;arisen;surgir, se présenter, résulter
B2;sweep;swept;swept;balayer, ramoner
B2;spin;spun;spun;filer, fabriquer, faire tourner
B2;wind;wound;wound;enrouler, envelopper, remonter
B2;bet;bet;bet;parier
B2;overcome;overcame;overcome;surmonter, triompher de, battre
B2;withdraw;withdrew;withdrawn;(se) retirer, se replier
B2;freeze;froze;frozen;geler, se congeler, se figer
B2;sink;sank;sunk;couler, baisser
B2;swim;swam;swum;nager
B2;split;split;split;fendre, diviser
B2;flee;fled;fled;(s')enfuir
B2;rid;rid;rid;débarrasser, laisser tomber
B2;undergo;underwent;undergone;subir, éprouver
B2;swear;swore;sworn;jurer
B2;shine;shone;shone;briller
B2;upset;upset;upset;renverser, bouleverser, vexer
B2;burst;burst;burst;éclater, crever
B2;speed;speeded/sped;speeded/sped;aller à toute vitesse
B2;forgive;forgave;forgiven;pardonner
B2;rebuild;rebuilt;rebuilt;rebâtir, refaire
B2;undertake;undertook;undertaken;entreprendre, se charger de, assumer
B2;spring;sprang;sprung;bondir
B2;oversee;oversaw;overseen;surveiller
B2;shed;shed;shed;perdre, verser
B2;shrink;shrank;shrunk;rétrécir, (se) réduire
B2;sneak;snuck;snuck;entrer/sortir furtivement, faire qqc discrètement, s'éclipser
B2;cling;clang;clung;se cramponner, adhérer, coller
B2;forbid;forbade;forbidden;interdire
B2;spit;spit/spat;spit/spat;cracher, crépiter
B2;kneel;kneeled/knelt;kneeled/knelt;s'agenouiller, être agenouillé"""

    def __init__(self):
        df = pd.read_csv(io.StringIO(self.CSV_DATA), sep=";")
        self._verbs: List[Verb] = [
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

    def get_all(self) -> List[Verb]:
        return self._verbs

    def get_by_id(self, verb_id: int) -> Verb:
        return self._verbs[verb_id]


class IUserDataRepository(ABC):
    @abstractmethod
    def get_user_pin_hash(self, username: str) -> Optional[str]: pass

    @abstractmethod
    def create_user(self, username: str, pin_hash: str) -> None: pass

    @abstractmethod
    def get_errors(self, username: str) -> List[int]: pass

    @abstractmethod
    def save_errors(self, username: str, error_ids: List[int], flush: bool = True) -> None: pass

    @abstractmethod
    def get_failures(self, username: str) -> Dict[int, int]: pass

    @abstractmethod
    def increment_failure(self, username: str, verb_id: int, flush: bool = False) -> None: pass

    @abstractmethod
    def get_paused_session(self, username: str) -> Dict: pass

    @abstractmethod
    def save_paused_session(self, username: str, session_data: Dict, flush: bool = True) -> None: pass

    @abstractmethod
    def get_srs_cards(self, username: str) -> Dict[int, SRSCard]: pass

    @abstractmethod
    def save_srs_cards(self, username: str, cards: Dict[int, SRSCard], flush: bool = True) -> None: pass

    @abstractmethod
    def flush_all(self, username: str) -> None: pass


@st.cache_resource
def get_gspread_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scopes
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_url(st.secrets["spreadsheet_url"])
    
    try:
        ws = sheet.worksheet("app_data")
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title="app_data", rows=100, cols=5)
        ws.append_row(["username", "pin_hash", "errors_json", "session_json", "srs_json"])
    return ws


class GoogleSheetsUserRepository(IUserDataRepository):
    """
    Persiste les données dans l'onglet 'app_data' avec cache en mémoire vive
    et écriture groupée pour éviter toute latence réseau entre les questions.
    """

    def __init__(self):
        self.ws = get_gspread_sheet()

    def _find_user_row(self, username: str) -> Tuple[Optional[int], Optional[Dict]]:
        records = self.ws.get_all_records()
        for idx, row in enumerate(records, start=2):
            if str(row.get("username", "")).strip().lower() == username.strip().lower():
                return idx, row
        return None, None

    def _ensure_cache(self, username: str):
        if "db_cache" not in st.session_state or st.session_state.db_cache.get("username") != username:
            row_idx, row_data = self._find_user_row(username)
            if row_data:
                raw_session = json.loads(row_data.get("session_json") or "{}")
                failures = {int(k): int(v) for k, v in raw_session.get("_failures", {}).items()}
                paused = {k: v for k, v in raw_session.items() if k != "_failures"}
                st.session_state.db_cache = {
                    "username": username,
                    "row_idx": row_idx,
                    "pin_hash": str(row_data.get("pin_hash", "")),
                    "errors": json.loads(row_data.get("errors_json") or "[]"),
                    "paused": paused,
                    "failures": failures,
                    "srs": json.loads(row_data.get("srs_json") or "{}")
                }
            else:
                st.session_state.db_cache = {"username": None}

    def get_user_pin_hash(self, username: str) -> Optional[str]:
        _, row_data = self._find_user_row(username)
        return str(row_data["pin_hash"]) if row_data else None

    def create_user(self, username: str, pin_hash: str) -> None:
        self.ws.append_row([username.strip(), pin_hash, "[]", "{}", "{}"])
        if "db_cache" in st.session_state:
            del st.session_state["db_cache"]
        self._ensure_cache(username)

    def get_errors(self, username: str) -> List[int]:
        self._ensure_cache(username)
        return list(st.session_state.db_cache.get("errors", []))

    def save_errors(self, username: str, error_ids: List[int], flush: bool = True) -> None:
        self._ensure_cache(username)
        st.session_state.db_cache["errors"] = error_ids
        if flush:
            self.flush_all(username)

    def get_failures(self, username: str) -> Dict[int, int]:
        self._ensure_cache(username)
        return dict(st.session_state.db_cache.get("failures", {}))

    def increment_failure(self, username: str, verb_id: int, flush: bool = False) -> None:
        self._ensure_cache(username)
        failures = st.session_state.db_cache.get("failures", {})
        failures[verb_id] = failures.get(verb_id, 0) + 1
        st.session_state.db_cache["failures"] = failures
        if flush:
            self.flush_all(username)

    def get_paused_session(self, username: str) -> Dict:
        self._ensure_cache(username)
        return dict(st.session_state.db_cache.get("paused", {}))

    def save_paused_session(self, username: str, session_data: Dict, flush: bool = True) -> None:
        self._ensure_cache(username)
        st.session_state.db_cache["paused"] = session_data
        if flush:
            self.flush_all(username)

    def get_srs_cards(self, username: str) -> Dict[int, SRSCard]:
        self._ensure_cache(username)
        raw_srs = st.session_state.db_cache.get("srs", {})
        return {int(k): SRSCard(**v) for k, v in raw_srs.items()}

    def save_srs_cards(self, username: str, cards: Dict[int, SRSCard], flush: bool = True) -> None:
        self._ensure_cache(username)
        serialized = {str(k): asdict(v) for k, v in cards.items()}
        st.session_state.db_cache["srs"] = serialized
        if flush:
            self.flush_all(username)

    def flush_all(self, username: str) -> None:
        """Envoie toutes les modifications à Google Sheets en une seule requête groupée."""
        self._ensure_cache(username)
        cache = st.session_state.db_cache
        row_idx = cache.get("row_idx")
        if not row_idx:
            return
        combined_session = dict(cache.get("paused", {}))
        combined_session["_failures"] = {str(k): v for k, v in cache.get("failures", {}).items()}
        
        self.ws.update(
            range_name=f"C{row_idx}:E{row_idx}",
            values=[[
                json.dumps(cache.get("errors", [])),
                json.dumps(combined_session),
                json.dumps(cache.get("srs", {}))
            ]]
        )


# =====================================================================
# 3. SERVICES (Logique Métier)
# =====================================================================

class AuthService:
    """Gère l'authentification par Pseudo + Code PIN à 4 chiffres."""

    def __init__(self, user_repo: IUserDataRepository):
        self.user_repo = user_repo

    @staticmethod
    def _hash_pin(pin: str) -> str:
        return hashlib.sha256(pin.strip().encode("utf-8")).hexdigest()

    @staticmethod
    def is_valid_pin(pin: str) -> bool:
        return len(pin.strip()) == 4 and pin.strip().isdigit()

    def login(self, username: str, pin: str) -> Tuple[bool, str]:
        username = username.strip()
        if not username:
            return False, "Entre un pseudo."
        if not self.is_valid_pin(pin):
            return False, "Le code PIN doit contenir exactement 4 chiffres."
        
        stored_hash = self.user_repo.get_user_pin_hash(username)
        if not stored_hash:
            return False, "Ce pseudo n'existe pas. Crée un compte d'abord."
        
        if stored_hash != self._hash_pin(pin):
            return False, "Code PIN incorrect."
        return True, "Connexion réussie."

    def register(self, username: str, pin: str) -> Tuple[bool, str]:
        username = username.strip()
        if not username:
            return False, "Entre un pseudo."
        if not self.is_valid_pin(pin):
            return False, "Le code PIN doit contenir exactement 4 chiffres."
        
        if self.user_repo.get_user_pin_hash(username) is not None:
            return False, "Ce pseudo est déjà pris."
        
        self.user_repo.create_user(username, self._hash_pin(pin))
        return True, "Compte créé avec succès."


class EvaluationService:
    """
    Évalue les réponses :
    - Anglais : strict (orthographe et variantes was/were obligatoires).
    - Français : souple sur les accents et les parenthèses, détection des réponses partielles.
    """

    @staticmethod
    def _normalize_english(text: str) -> str:
        text = text.strip().lower()
        text = re.sub(r'\s*/\s*', '/', text)
        text = re.sub(r'\s+', ' ', text)
        return text

    @staticmethod
    def _normalize_french(token: str) -> str:
        token = token.strip().lower().replace("’", "'")
        # Supprime les accents pour tolérer les oublis sur clavier mobile
        token = ''.join(
            c for c in unicodedata.normalize('NFD', token)
            if unicodedata.category(c) != 'Mn'
        )
        token = re.sub(r'\s+', ' ', token)
        return token

    @classmethod
    def _expand_french_variants(cls, raw_translation: str) -> Tuple[List[str], Dict[str, str]]:
        raw_parts = [p.strip() for p in re.split(r'[,/;]', raw_translation) if p.strip()]
        canonical_list = []
        variant_map = {}

        for part in raw_parts:
            canonical_list.append(part)
            norm_part = cls._normalize_french(part)
            variant_map[norm_part] = part

            no_parens = cls._normalize_french(re.sub(r'\([^)]*\)', '', part))
            with_parens_content = cls._normalize_french(re.sub(r'[()]', '', part))
            
            if no_parens:
                variant_map[no_parens] = part
            if with_parens_content:
                variant_map[with_parens_content] = part

        return canonical_list, variant_map

    def evaluate(self, verb: Verb, given_col: str, user_inputs: Dict[str, str]) -> EvaluationResult:
        cols = ["Infinitive", "Preterit", "Past Participle", "Translation"]
        missing_cols = [c for c in cols if c != given_col]

        # 1. Vérification stricte des colonnes anglaises
        for col in missing_cols:
            if col != "Translation":
                expected_en = self._normalize_english(verb.get_field(col))
                user_en = self._normalize_english(user_inputs.get(col, ""))
                if user_en != expected_en:
                    return EvaluationResult(status="WRONG", missing_translations=[], verb=verb)

        # 2. Vérification de la traduction française (tolérance aux accents + réponses partielles)
        if "Translation" in missing_cols:
            user_raw = user_inputs.get("Translation", "").strip()
            if not user_raw:
                return EvaluationResult(status="WRONG", missing_translations=[], verb=verb)

            canonical_expected, variant_map = self._expand_french_variants(verb.translation)
            user_tokens = [self._normalize_french(t) for t in re.split(r'[,/;]', user_raw) if t.strip()]

            if not user_tokens:
                return EvaluationResult(status="WRONG", missing_translations=[], verb=verb)

            matched_canonicals = set()
            for u_tok in user_tokens:
                if u_tok in variant_map:
                    matched_canonicals.add(variant_map[u_tok])
                else:
                    return EvaluationResult(status="WRONG", missing_translations=[], verb=verb)

            missing = [c for c in canonical_expected if c not in matched_canonicals]
            if missing:
                return EvaluationResult(status="INCOMPLETE", missing_translations=missing, verb=verb)

        return EvaluationResult(status="EXACT", missing_translations=[], verb=verb)


class SRSService:
    """Implémente l'algorithme de répétition espacée (Anki) par ordre de fréquence TOEIC."""

    LONG_TERM_STEPS = [1, 3, 7, 16, 35, 90]
    MAX_NEW_PER_DAY = 10

    def __init__(self, verb_repo: IVerbRepository, user_repo: IUserDataRepository):
        self.verb_repo = verb_repo
        self.user_repo = user_repo

    def get_daily_queue(self, username: str, force_early: bool = False) -> Tuple[List[SRSCard], int]:
        cards = self.user_repo.get_srs_cards(username)
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        introduced_today = sum(1 for c in cards.values() if c.introduced_date == today_str)
        remaining_new_quota = max(0, self.MAX_NEW_PER_DAY - introduced_today)

        # Introduction dans l'ordre exact de fréquence du TOEIC (du plus fréquent au plus rare)
        if remaining_new_quota > 0:
            all_verb_ids = [v.id for v in self.verb_repo.get_all()]
            unseen_ids = [vid for vid in all_verb_ids if vid not in cards]
            if unseen_ids:
                new_selection = unseen_ids[:remaining_new_quota]
                for vid in new_selection:
                    cards[vid] = SRSCard(
                        verb_id=vid,
                        state="learning",
                        step=0,
                        interval_days=0,
                        due_timestamp=now.isoformat(),
                        introduced_date=today_str
                    )
                self.user_repo.save_srs_cards(username, cards, flush=True)

        due_now = []
        waiting_learning = []

        for card in cards.values():
            if card.is_due(now):
                due_now.append(card)
            elif card.state == "learning":
                if force_early:
                    due_now.append(card)
                else:
                    waiting_learning.append(card)

        due_now.sort(key=lambda c: c.due_timestamp)
        return due_now, len(waiting_learning)

    def get_button_labels(self, card: SRSCard) -> Dict[str, str]:
        if card.state in ("new", "learning"):
            if card.step == 0:
                return {
                    "again": "🔄 À revoir (+1 min)",
                    "hard": "⚠️ Difficile (+5 min)",
                    "good": "✅ Correct (+10 min)",
                    "easy": "⭐ Facile (+4 j)"
                }
            else:
                return {
                    "again": "🔄 À revoir (+1 min)",
                    "hard": "⚠️ Difficile (+5 min)",
                    "good": "✅ Correct (+1 j)",
                    "easy": "⭐ Facile (+4 j)"
                }
        else:
            curr = max(1, card.interval_days)
            hard_days = max(curr + 1, int(round(curr * 1.2)))
            good_days = self._next_good_interval(curr)
            easy_days = self._next_good_interval(good_days)
            return {
                "again": "🔄 À revoir (+1 min)",
                "hard": f"⚠️ Difficile (+{hard_days} j)",
                "good": f"✅ Correct (+{good_days} j)",
                "easy": f"⭐ Facile (+{easy_days} j)"
            }

    def _next_good_interval(self, current_days: int) -> int:
        for step in self.LONG_TERM_STEPS:
            if step > current_days:
                return step
        return int(round(current_days * 2.2))

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
                    card.state = "review"
                    card.interval_days = 1
                    card.due_timestamp = (now + timedelta(days=1)).isoformat()
            elif rating == "easy":
                card.state = "review"
                card.interval_days = 4
                card.due_timestamp = (now + timedelta(days=4)).isoformat()
        else:
            curr = max(1, card.interval_days)
            if rating == "again":
                card.state = "learning"
                card.step = 0
                card.interval_days = 0
                card.due_timestamp = (now + timedelta(minutes=1)).isoformat()
                self._record_error(username, verb_id)
            elif rating == "hard":
                card.interval_days = max(curr + 1, int(round(curr * 1.2)))
                card.due_timestamp = (now + timedelta(days=card.interval_days)).isoformat()
            elif rating == "good":
                card.interval_days = self._next_good_interval(curr)
                card.due_timestamp = (now + timedelta(days=card.interval_days)).isoformat()
            elif rating == "easy":
                good_d = self._next_good_interval(curr)
                card.interval_days = self._next_good_interval(good_d)
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
    """Génère la synthèse vocale en anglais américain (lecture manuelle uniquement)."""

    @staticmethod
    @st.cache_data(show_spinner=False)
    def get_audio(text: str) -> bytes:
        clean_text = text.replace("/", ", ")
        tts = gTTS(text=clean_text, lang='en-US')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return fp.getvalue()


# =====================================================================
# 4. CONTROLLER & VIEWS (Navigation par onglets et Interface Mobile)
# =====================================================================

class AppController:
    COLS = ["Infinitive", "Preterit", "Past Participle", "Translation"]

    def __init__(
        self,
        verb_repo: IVerbRepository,
        user_repo: IUserDataRepository,
        auth_service: AuthService,
        eval_service: EvaluationService,
        srs_service: SRSService,
        audio_service: AudioService
    ):
        self.verb_repo = verb_repo
        self.user_repo = user_repo
        self.auth_service = auth_service
        self.eval_service = eval_service
        self.srs_service = srs_service
        self.audio_service = audio_service
        self._init_session_state()

    def _init_session_state(self):
        defaults = {
            "current_user": None,
            # État Entraînement
            "training_active": False,
            "queue": [],
            "current_idx": None,
            "given_col": None,
            "score": 0,
            "total": 0,
            "last_eval": None,
            "unsaved_count": 0,
            # État Flashcards
            "fc_active": False,
            "fc_queue": [],
            "flashcard_revealed": False,
            # État SRS
            "srs_active": False,
            "srs_current_card": None,
            "srs_given_col": None,
            "srs_eval_result": None,
            "srs_force_early": False
        }
        for k, v in defaults.items():
            if k not in st.session_state:
                st.session_state[k] = v

    @staticmethod
    def _disable_mobile_autocorrect():
        """Désactive la majuscule automatique et le correcteur orthographique sur mobile."""
        components.html(
            """
            <script>
            const inputs = window.parent.document.querySelectorAll('input[type="text"]');
            inputs.forEach(input => {
                input.setAttribute('autocapitalize', 'none');
                input.setAttribute('autocorrect', 'off');
                input.setAttribute('spellcheck', 'false');
            });
            </script>
            """,
            height=0
        )

    def run(self):
        st.title("TOEIC Irregular Verbs")

        if not st.session_state.current_user:
            self._render_auth_view()
            return

        user = st.session_state.current_user

        # Barre supérieure utilisateur
        col_u1, col_u2 = st.columns([3, 1])
        with col_u1:
            st.caption(f"👤 Connecté : **{user}**")
        with col_u2:
            if st.button("Déconnexion"):
                self.user_repo.flush_all(user)
                st.session_state.current_user = None
                st.rerun()

        # Navigation principale par onglets mobiles
        tab_srs, tab_train, tab_fc, tab_stats = st.tabs([
            "🧠 SRS (Anki)",
            "🎯 S'entraîner",
            "🗂️ Flashcards",
            "📊 Statistiques"
        ])

        with tab_srs:
            self._render_srs_tab(user)
        with tab_train:
            self._render_training_tab(user)
        with tab_fc:
            self._render_flashcards_tab(user)
        with tab_stats:
            self._render_stats_tab(user)

        self._disable_mobile_autocorrect()

    # -----------------------------------------------------------------
    # VUE : AUTHENTIFICATION
    # -----------------------------------------------------------------
    def _render_auth_view(self):
        st.subheader("Identification")
        tab_login, tab_reg = st.tabs(["Connexion", "Créer un compte"])

        with tab_login:
            with st.form("login_form"):
                u_login = st.text_input("Pseudo :")
                p_login = st.text_input("Code PIN (4 chiffres) :", type="password", max_chars=4)
                if st.form_submit_button("Se connecter", type="primary", use_container_width=True):
                    ok, msg = self.auth_service.login(u_login, p_login)
                    if ok:
                        st.session_state.current_user = u_login.strip()
                        st.rerun()
                    else:
                        st.error(msg)

        with tab_reg:
            with st.form("reg_form"):
                u_reg = st.text_input("Choisis un pseudo :")
                p_reg = st.text_input("Choisis un code PIN (4 chiffres) :", type="password", max_chars=4)
                if st.form_submit_button("Créer mon compte", type="primary", use_container_width=True):
                    ok, msg = self.auth_service.register(u_reg, p_reg)
                    if ok:
                        st.session_state.current_user = u_reg.strip()
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    # -----------------------------------------------------------------
    # ONGLET 1 : MODE SRS (ANKI)
    # -----------------------------------------------------------------
    def _render_srs_tab(self, user: str):
        st.subheader("Mémoire à long terme (SRS)")

        if not st.session_state.srs_active:
            st.caption("10 nouveaux verbes/jour max (par ordre de fréquence TOEIC) + révisions espacées.")
            if st.button("Lancer ma session SRS du jour", type="primary", use_container_width=True):
                st.session_state.srs_active = True
                st.session_state.srs_current_card = None
                st.session_state.srs_eval_result = None
                st.session_state.srs_force_early = False
                st.rerun()
            return

        if st.session_state.srs_current_card is None:
            due_cards, waiting_count = self.srs_service.get_daily_queue(
                user, force_early=st.session_state.srs_force_early
            )
            st.session_state.srs_force_early = False

            if not due_cards:
                if waiting_count > 0:
                    st.info(f"⏳ Tu as **{waiting_count} verbe(s)** en cours d'apprentissage qui reviennent dans quelques minutes (+1 / +5 / +10 min).")
                    col_w1, col_w2 = st.columns(2)
                    with col_w1:
                        if st.button("🔄 Actualiser", use_container_width=True):
                            st.rerun()
                    with col_w2:
                        if st.button("⏩ Réviser sans attendre", type="primary", use_container_width=True):
                            st.session_state.srs_force_early = True
                            st.rerun()
                else:
                    st.success("🎉 Bravo ! Tu as terminé toutes tes révisions SRS et tes 10 nouveaux verbes du jour.")

                if st.button("Fermer la session SRS", use_container_width=True):
                    st.session_state.srs_active = False
                    st.rerun()
                return

            st.session_state.srs_current_card = due_cards[0]
            st.session_state.srs_given_col = random.choice(self.COLS)
            st.session_state.srs_eval_result = None

        card: SRSCard = st.session_state.srs_current_card
        v = self.verb_repo.get_by_id(card.verb_id)
        given_c = st.session_state.srs_given_col
        missing_cols = [c for c in self.COLS if c != given_c]

        st.caption(f"Niveau TOEIC : **{v.level}**")
        st.markdown(f"### {given_c} : **{v.get_field(given_c)}**")
        if given_c != "Translation":
            st.audio(self.audio_service.get_audio(v.get_field(given_c)), format="audio/mp3")

        # Étape 1 : Saisie active
        if st.session_state.srs_eval_result is None:
            with st.form("srs_form", clear_on_submit=True):
                user_inputs = {col: st.text_input(f"{col} :", autocomplete="off") for col in missing_cols}
                if st.form_submit_button("Vérifier ma réponse", type="primary", use_container_width=True):
                    st.session_state.srs_eval_result = self.eval_service.evaluate(v, given_c, user_inputs)
                    st.rerun()

        # Étape 2 : Correction complète + Grille 2x2 de boutons d'intervalles
        else:
            res: EvaluationResult = st.session_state.srs_eval_result
            if res.status == "EXACT":
                st.success("✅ **Réponse exacte !**")
            elif res.status == "INCOMPLETE":
                st.warning(f"⚠️ **Réponse incomplète** — Traduction(s) manquante(s) : `{', '.join(res.missing_translations)}`")
            else:
                st.error("❌ **Réponse fausse**")

            st.markdown("#### Ensemble complet à retenir :")
            st.write(f"- **Infinitif :** {v.infinitive}")
            st.write(f"- **Prétérit :** {v.preterit}")
            st.write(f"- **Participe Passé :** {v.past_participle}")
            st.write(f"- **Toutes les traductions :** **{v.translation}**")
            st.audio(self.audio_service.get_audio(f"{v.infinitive}, {v.preterit}, {v.past_participle}"), format="audio/mp3")

            st.markdown("##### Choisis l'intervalle de répétition :")
            labels = self.srs_service.get_button_labels(card)

            # Grille 2x2 ergonomique pour écran de téléphone
            row1_col1, row1_col2 = st.columns(2)
            with row1_col1:
                if st.button(labels["again"], use_container_width=True):
                    self.srs_service.process_rating(user, v.id, "again")
                    st.session_state.srs_current_card = None
                    st.rerun()
            with row1_col2:
                if st.button(labels["hard"], use_container_width=True):
                    self.srs_service.process_rating(user, v.id, "hard")
                    st.session_state.srs_current_card = None
                    st.rerun()

            row2_col1, row2_col2 = st.columns(2)
            with row2_col1:
                if st.button(labels["good"], type="primary", use_container_width=True):
                    self.srs_service.process_rating(user, v.id, "good")
                    st.session_state.srs_current_card = None
                    st.rerun()
            with row2_col2:
                if st.button(labels["easy"], use_container_width=True):
                    self.srs_service.process_rating(user, v.id, "easy")
                    st.session_state.srs_current_card = None
                    st.rerun()

        st.write("---")
        if st.button("Quitter la session SRS", use_container_width=True):
            st.session_state.srs_current_card = None
            st.session_state.srs_active = False
            st.rerun()

    # -----------------------------------------------------------------
    # ONGLET 2 : MODE ENTRAÎNEMENT (LISTES)
    # -----------------------------------------------------------------
    def _render_training_tab(self, user: str):
        errors = self.user_repo.get_errors(user)
        paused = self.user_repo.get_paused_session(user)

        # Écran de configuration si aucun entraînement n'est actif
        if not st.session_state.training_active:
            st.subheader("S'entraîner par listes")

            # 1. Option de reprise si une session est en pause
            if paused and paused.get("current_idx") is not None:
                rem = len(paused.get("queue", [])) + 1
                st.info(f"⏸️ Session en pause : **{rem} verbe(s) restant(s)** (Score : {paused.get('score', 0)}/{paused.get('total', 0)}).")
                if st.button("▶️ Reprendre la session en pause", type="primary", use_container_width=True):
                    st.session_state.queue = paused["queue"]
                    st.session_state.score = paused["score"]
                    st.session_state.total = paused["total"]
                    st.session_state.current_idx = paused["current_idx"]
                    st.session_state.given_col = paused["given_col"]
                    st.session_state.last_eval = None
                    st.session_state.unsaved_count = 0
                    st.session_state.training_active = True
                    self.user_repo.save_paused_session(user, {}, flush=True)
                    st.rerun()
                st.write("---")

            # 2. Configuration d'une nouvelle session
            tr_source = st.radio(
                "Source Entraînement :",
                ["Tous les verbes (127)", f"Mes erreurs ({len(errors)})"],
                key="tr_src"
            )

            level_filter = "Tous"
            nb_verbs = 127
            if tr_source.startswith("Tous"):
                c_lvl, c_nb = st.columns(2)
                with c_lvl:
                    level_filter = st.selectbox("Niveau :", ["Tous", "A1", "A2", "B1", "B2"])
                with c_nb:
                    nb_verbs = st.selectbox("Nombre de verbes :", [20, 50, 100, 127])

            if st.button("Lancer l'entraînement", type="primary", use_container_width=True):
                if tr_source.startswith("Mes erreurs") and not errors:
                    st.warning("Aucune erreur enregistrée pour le moment.")
                else:
                    if tr_source.startswith("Mes erreurs"):
                        pool = list(errors)
                    else:
                        verbs_pool = self.verb_repo.get_all()
                        if level_filter != "Tous":
                            verbs_pool = [v for v in verbs_pool if v.level == level_filter]
                        pool = [v.id for v in verbs_pool]

                    sample_size = len(pool) if tr_source.startswith("Mes erreurs") else min(nb_verbs, len(pool))
                    sampled = random.sample(pool, sample_size)

                    st.session_state.current_idx = sampled.pop(0)
                    st.session_state.queue = sampled
                    st.session_state.total = sample_size
                    st.session_state.score = 0
                    st.session_state.given_col = random.choice(self.COLS)
                    st.session_state.last_eval = None
                    st.session_state.unsaved_count = 0
                    st.session_state.training_active = True
                    st.rerun()
            return

        # --- ENTRAÎNEMENT ACTIF ---
        # 1. Écran de retour sur erreur ou réponse incomplète
        if st.session_state.last_eval is not None:
            res: EvaluationResult = st.session_state.last_eval
            v = res.verb

            if res.status == "INCOMPLETE":
                st.warning("⚠️ **Réponse incomplète** (1 point accordé, mais ajouté à tes erreurs)")
                st.write(f"**Traduction(s) manquante(s) :** `{', '.join(res.missing_translations)}`")
            else:
                st.error("❌ **Erreur sur le verbe précédent**")

            st.markdown("#### Ensemble complet à retenir :")
            st.write(f"- **Infinitif :** {v.infinitive}")
            st.write(f"- **Prétérit :** {v.preterit}")
            st.write(f"- **Participe Passé :** {v.past_participle}")
            st.write(f"- **Toutes les traductions :** **{v.translation}**")
            st.audio(self.audio_service.get_audio(f"{v.infinitive}, {v.preterit}, {v.past_participle}"), format="audio/mp3")

            if st.button("Continuer", type="primary", use_container_width=True):
                st.session_state.last_eval = None
                st.rerun()
            return

        # 2. Fin de session
        if st.session_state.current_idx is None:
            self.user_repo.flush_all(user)
            st.success(f"🎉 Session terminée ! Score : **{st.session_state.score} / {st.session_state.total}**")
            if st.button("Retour à la configuration", type="primary", use_container_width=True):
                st.session_state.training_active = False
                st.rerun()
            return

        # 3. Saisie active
        done_count = st.session_state.total - len(st.session_state.queue)
        st.progress(done_count / st.session_state.total, text=f"Verbe {done_count} / {st.session_state.total}")

        v = self.verb_repo.get_by_id(st.session_state.current_idx)
        given_c = st.session_state.given_col
        missing_cols = [c for c in self.COLS if c != given_c]

        st.caption(f"Niveau TOEIC : **{v.level}**")
        st.markdown(f"### {given_c} : **{v.get_field(given_c)}**")
        if given_c != "Translation":
            st.audio(self.audio_service.get_audio(v.get_field(given_c)), format="audio/mp3")

        with st.form("training_form", clear_on_submit=True):
            user_inputs = {col: st.text_input(f"{col} :", autocomplete="off") for col in missing_cols}
            submitted = st.form_submit_button("Valider", type="primary", use_container_width=True)

            if submitted:
                eval_res = self.eval_service.evaluate(v, given_c, user_inputs)
                st.session_state.unsaved_count += 1
                should_flush = (st.session_state.unsaved_count >= 5) or (len(st.session_state.queue) == 0)

                if eval_res.status == "EXACT":
                    st.session_state.score += 1
                    if v.id in errors:
                        errors.remove(v.id)
                        self.user_repo.save_errors(user, errors, flush=False)
                elif eval_res.status == "INCOMPLETE":
                    st.session_state.score += 1
                    if v.id not in errors:
                        errors.append(v.id)
                        self.user_repo.save_errors(user, errors, flush=False)
                    st.session_state.last_eval = eval_res
                else:
                    if v.id not in errors:
                        errors.append(v.id)
                        self.user_repo.save_errors(user, errors, flush=False)
                    self.user_repo.increment_failure(user, v.id, flush=False)
                    st.session_state.last_eval = eval_res

                if should_flush:
                    self.user_repo.flush_all(user)
                    st.session_state.unsaved_count = 0

                if st.session_state.queue:
                    st.session_state.current_idx = st.session_state.queue.pop(0)
                    st.session_state.given_col = random.choice(self.COLS)
                else:
                    st.session_state.current_idx = None
                st.rerun()

        st.write("---")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("⏸️ Mettre en pause", use_container_width=True):
                self.user_repo.save_paused_session(user, {
                    "queue": st.session_state.queue,
                    "total": st.session_state.total,
                    "score": st.session_state.score,
                    "current_idx": st.session_state.current_idx,
                    "given_col": st.session_state.given_col
                }, flush=True)
                st.session_state.training_active = False
                st.rerun()
        with c2:
            if st.button("⏹️ Arrêter définitivement", use_container_width=True):
                self.user_repo.save_paused_session(user, {}, flush=True)
                st.session_state.current_idx = None
                st.session_state.queue = []
                st.session_state.training_active = False
                st.rerun()

    # -----------------------------------------------------------------
    # ONGLET 3 : FLASHCARDS (CATALOGUE & DÉFILEMENT)
    # -----------------------------------------------------------------
    def _render_flashcards_tab(self, user: str):
        errors = self.user_repo.get_errors(user)

        if not st.session_state.fc_active:
            st.subheader("Flashcards (Catalogue & Révision)")
            fc_source = st.radio(
                "Source :",
                ["Tous les verbes (127)", f"Mes erreurs ({len(errors)})"],
                key="fc_src"
            )
            fc_style = st.radio(
                "Méthode :",
                ["Catalogue (Choisir les verbes)", "Défilement aléatoire"],
                key="fc_style"
            )

            source_verbs = (
                [self.verb_repo.get_by_id(i) for i in errors]
                if fc_source.startswith("Mes erreurs")
                else self.verb_repo.get_all()
            )

            selected_fc_ids = []
            if fc_style == "Catalogue (Choisir les verbes)":
                if not source_verbs:
                    st.caption("Aucun verbe disponible dans cette source.")
                else:
                    options_map = {f"[{v.level}] {v.infinitive} ({v.translation})": v.id for v in source_verbs}
                    chosen_labels = st.multiselect(
                        "Recherche et sélectionne tes verbes :",
                        options=list(options_map.keys())
                    )
                    selected_fc_ids = [options_map[lbl] for lbl in chosen_labels]

                    if selected_fc_ids and st.checkbox("Afficher directement la fiche récapitulative ici"):
                        for vid in selected_fc_ids:
                            vb = self.verb_repo.get_by_id(vid)
                            with st.expander(f"**{vb.infinitive}** ({vb.level}) — {vb.translation}"):
                                st.write(f"**Prétérit :** `{vb.preterit}` | **Participe Passé :** `{vb.past_participle}`")
                                st.audio(self.audio_service.get_audio(f"{vb.infinitive}, {vb.preterit}, {vb.past_participle}"), format="audio/mp3")

            if st.button("Lancer les Flashcards", type="primary", use_container_width=True):
                if not source_verbs:
                    st.warning("Aucune erreur enregistrée pour le moment.")
                elif fc_style == "Catalogue (Choisir les verbes)" and not selected_fc_ids:
                    st.warning("Sélectionne au moins un verbe dans le catalogue.")
                else:
                    if fc_style == "Catalogue (Choisir les verbes)":
                        st.session_state.fc_queue = list(selected_fc_ids)
                    else:
                        ids = [v.id for v in source_verbs]
                        random.shuffle(ids)
                        st.session_state.fc_queue = ids
                    st.session_state.flashcard_revealed = False
                    st.session_state.fc_active = True
                    st.rerun()
            return

        # Défilement actif des flashcards
        if not st.session_state.fc_queue:
            st.success("Toutes les flashcards sélectionnées ont été révisées !")
            if st.button("Retour au catalogue", type="primary", use_container_width=True):
                st.session_state.fc_active = False
                st.rerun()
            return

        v = self.verb_repo.get_by_id(st.session_state.fc_queue[0])
        st.caption(f"Cartes restantes : {len(st.session_state.fc_queue)} | Niveau : **{v.level}**")
        st.markdown(f"## {v.infinitive}")
        st.audio(self.audio_service.get_audio(v.infinitive), format="audio/mp3")

        if not st.session_state.flashcard_revealed:
            if st.button("Révéler", type="primary", use_container_width=True):
                st.session_state.flashcard_revealed = True
                st.rerun()
        else:
            st.info(
                f"**Prétérit :** {v.preterit}  \n"
                f"**Participe Passé :** {v.past_participle}  \n"
                f"**Traduction complète :** {v.translation}"
            )
            st.audio(self.audio_service.get_audio(f"{v.infinitive}, {v.preterit}, {v.past_participle}"), format="audio/mp3")

            if st.button("Carte suivante ➡️", type="primary", use_container_width=True):
                st.session_state.fc_queue.pop(0)
                st.session_state.flashcard_revealed = False
                st.rerun()

        st.write("---")
        if st.button("Quitter les flashcards", use_container_width=True):
            st.session_state.fc_active = False
            st.rerun()

    # -----------------------------------------------------------------
    # ONGLET 4 : STATISTIQUES & BÊTES NOIRES
    # -----------------------------------------------------------------
    def _render_stats_tab(self, user: str):
        st.subheader("Tableau de bord & Statistiques")
        errors = self.user_repo.get_errors(user)
        failures = self.user_repo.get_failures(user)
        srs_cards = self.user_repo.get_srs_cards(user)

        review_count = sum(1 for c in srs_cards.values() if c.state == "review")
        learning_count = sum(1 for c in srs_cards.values() if c.state == "learning")

        c1, c2, c3 = st.columns(3)
        c1.metric("Acquis (SRS)", f"{review_count} / 127")
        c2.metric("En cours (SRS)", learning_count)
        c3.metric("Erreurs actives", len(errors))

        st.write("---")
        st.markdown("#### 🔥 Tes 10 Bêtes noires (Verbes les plus ratés)")
        if not failures:
            st.caption("Aucun échec enregistré pour le moment.")
        else:
            sorted_fails = sorted(failures.items(), key=lambda x: x[1], reverse=True)[:10]
            for vid, count in sorted_fails:
                vb = self.verb_repo.get_by_id(vid)
                st.write(
                    f"- **[{vb.level}] {vb.infinitive}** (`{vb.preterit}`, `{vb.past_participle}`) "
                    f"— *{vb.translation}* : **{count} erreur(s)**"
                )


# =====================================================================
# 5. ENTRY POINT (Injection de dépendances)
# =====================================================================

def main():
    verb_repo = StaticVerbRepository()
    user_repo = GoogleSheetsUserRepository()
    
    auth_service = AuthService(user_repo)
    eval_service = EvaluationService()
    srs_service = SRSService(verb_repo, user_repo)
    audio_service = AudioService()

    controller = AppController(
        verb_repo=verb_repo,
        user_repo=user_repo,
        auth_service=auth_service,
        eval_service=eval_service,
        srs_service=srs_service,
        audio_service=audio_service
    )
    controller.run()

if __name__ == "__main__":
    main()
