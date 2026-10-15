import streamlit as st
import pandas as pd
import random
import io
import re
import json
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from gtts import gTTS
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="TOEIC Irregular Verbs", layout="centered")

# =====================================================================
# 1. DOMAIN MODELS
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
    step: int = 0               
    interval_days: int = 0      
    due_timestamp: str = ""     
    introduced_date: str = ""   

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
# 2. REPOSITORIES
# =====================================================================

class IVerbRepository(ABC):
    @abstractmethod
    def get_all(self) -> List[Verb]: pass
    @abstractmethod
    def get_by_id(self, verb_id: int) -> Verb: pass


class StaticVerbRepository(IVerbRepository):
    """Charge la liste officielle des 127 verbes avec leurs niveaux (A1 à B2)."""
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
A1;win;won;gagner
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
A2;catch;caught;attraper;attraper
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
A2;hang;hung;hung;suspendre, accrocher
A2;forget;forgot;forgotten;oublier
B1;shake;shook;shaken;secouer, agiter
B1;fly;flew;flown;voler
B1;sing;sang;sung;chanter
B1;beat;beat;beaten;battre, frapper
B1;be born;was born;been born;naître
B1;cost;cost;cost;coûter
B1;hurt;hurt;hurt;se blesser, faire du mal
B1;strike;struck;stricken;frapper, faire grève
B1;sleep;slept;slept;dormir
B1;stick;stuck;stuck;piquer, planter
B1;drink;drank;drunk;boire
B1;hide;hid;hidden;cacher, se cacher
B1;ride;rode;ridden;monter à, faire du
B1;feed;fed;fed;nourrir
B1;fit;fit;fit;aller à, entrer
B1;spread;spread;spread;étendre, étaler
B1;blow;blew;blown;souffler, pousser
B1;shut;shut;shut;refermer, repousser
B1;bear;bore;born;porter, se diriger
B1;wake;woke;woken;se réveiller
B1;steal;stole;stolen;voler, dérober
B1;slide;slid;slid;glisser
B1;bend;bent;bent;courber, plier, tordre
B1;tear;tore;torn;déchirer
B2;ring;rang;rung;sonner
B2;light;lit;lit;allumer, éclairer
B2;swing;swung;swung;se balancer
B2;dig;dug;dug;creuser, bêcher
B2;bind;bound;bound;attacher, entourer
B2;quit;quit;quit;quitter, sortir
B2;arise;arose;arisen;surgir, résulter
B2;sweep;swept;swept;balayer
B2;spin;spun;spun;filer, faire tourner
B2;wind;wound;wound;enrouler, remonter
B2;bet;bet;bet;parier
B2;overcome;overcame;overcome;surmonter, triompher
B2;withdraw;withdrew;withdrawn;se retirer
B2;freeze;froze;frozen;geler, se figer
B2;sink;sank;sunk;couler, baisser
B2;swim;swam;swum;nager
B2;split;split;split;fendre, diviser
B2;flee;fled;fled;s'enfuir
B2;rid;rid;rid;débarrasser
B2;undergo;underwent;undergone;subir, éprouver
B2;swear;swore;sworn;jurer
B2;shine;shone;shone;briller
B2;upset;upset;upset;bouleverser, vexer
B2;burst;burst;burst;éclater, crever
B2;speed;speeded/sped;speeded/sped;aller à toute vitesse
B2;forgive;forgave;forgiven;pardonner
B2;rebuild;rebuilt;rebuilt;rebâtir, refaire
B2;undertake;undertook;undertaken;entreprendre
B2;spring;sprang;sprung;bondir
B2;oversee;oversaw;overseen;surveiller
B2;shed;shed;shed;perdre, verser
B2;shrink;shrank;shrunk;rétrécir
B2;sneak;snuck;snuck;entrer furtivement
B2;cling;clang;clung;se cramponner, coller
B2;forbid;forbade;forbidden;interdire
B2;spit;spit/spat;spit/spat;cracher
B2;kneel;kneeled/knelt;kneeled/knelt;s'agenouiller"""

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

    def get_all(self) -> List[Verb]: return self._verbs
    def get_by_id(self, verb_id: int) -> Verb: return self._verbs[verb_id]


class IUserDataRepository(ABC):
    @abstractmethod
    def get_user_pin_hash(self, username: str) -> Optional[str]: pass
    @abstractmethod
    def create_user(self, username: str, pin_hash: str) -> None: pass
    @abstractmethod
    def get_user_data(self, username: str) -> Dict: pass
    @abstractmethod
    def save_user_data(self, username: str, data: Dict) -> None: pass


@st.cache_resource
def get_gspread_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(st.secrets["spreadsheet_url"])
    try:
        ws = sheet.worksheet("app_data_v2")
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title="app_data_v2", rows=100, cols=3)
        ws.append_row(["username", "pin_hash", "json_data"])
    return ws


class GoogleSheetsUserRepository(IUserDataRepository):
    """Gère le stockage persistant dans Google Sheets avec mise en cache locale pour éviter la latence."""

    def __init__(self):
        self.ws = get_gspread_sheet()

    def _find_row(self, username: str) -> Tuple[Optional[int], Optional[Dict]]:
        records = self.ws.get_all_records()
        for idx, row in enumerate(records, start=2):
            if str(row.get("username", "")).strip().lower() == username.strip().lower():
                return idx, row
        return None, None

    def _sync_cache(self, username: str):
        if "db_cache" not in st.session_state or st.session_state.db_cache.get("username") != username:
            row_idx, row_data = self._find_row(username)
            if row_data:
                st.session_state.db_cache = {
                    "username": username,
                    "row_idx": row_idx,
                    "pin_hash": str(row_data.get("pin_hash", "")),
                    "data": json.loads(row_data.get("json_data") or "{}")
                }
            else:
                st.session_state.db_cache = {"username": None}

    def get_user_pin_hash(self, username: str) -> Optional[str]:
        _, row = self._find_row(username)
        return str(row["pin_hash"]) if row else None

    def create_user(self, username: str, pin_hash: str) -> None:
        initial_data = {"errors": [], "failure_counts": {}, "session": {}, "srs": {}}
        self.ws.append_row([username.strip(), pin_hash, json.dumps(initial_data)])
        if "db_cache" in st.session_state: del st.session_state["db_cache"]
        self._sync_cache(username)

    def get_user_data(self, username: str) -> Dict:
        self._sync_cache(username)
        return st.session_state.db_cache.get("data", {"errors": [], "failure_counts": {}, "session": {}, "srs": {}})

    def save_user_data(self, username: str, data: Dict) -> None:
        self._sync_cache(username)
        st.session_state.db_cache["data"] = data
        row_idx = st.session_state.db_cache["row_idx"]
        self.ws.update_cell(row_idx, 3, json.dumps(data))


# =====================================================================
# 3. SERVICES
# =====================================================================

class AuthService:
    def __init__(self, repo: IUserDataRepository): self.repo = repo

    @staticmethod
    def _hash(pin: str) -> str:
        return hashlib.sha256(pin.strip().encode("utf-8")).hexdigest()

    def login(self, username: str, pin: str) -> Tuple[bool, str]:
        username = username.strip()
        if not username or len(pin.strip()) != 4 or not pin.strip().isdigit():
            return False, "Pseudo requis et code PIN à 4 chiffres obligatoire."
        stored = self.repo.get_user_pin_hash(username)
        if not stored or stored != self._hash(pin):
            return False, "Identifiants incorrects."
        return True, "OK"

    def register(self, username: str, pin: str) -> Tuple[bool, str]:
        username = username.strip()
        if not username or len(pin.strip()) != 4 or not pin.strip().isdigit():
            return False, "Pseudo requis et code PIN à 4 chiffres."
        if self.repo.get_user_pin_hash(username) is not None:
            return False, "Ce pseudo existe déjà."
        self.repo.create_user(username, self._hash(pin))
        return True, "Compte créé !"


class EvaluationService:
    """Évalue les réponses avec normalisation stricte en anglais et tolérance aux accents en français."""

    @staticmethod
    def _normalize_en(text: str) -> str:
        text = text.strip().lower()
        text = re.sub(r'\s*/\s*', '/', text)
        return re.sub(r'\s+', ' ', text)

    @staticmethod
    def _normalize_fr(text: str) -> str:
        text = text.strip().lower().replace("’", "'")
        # Supprime les accents pour tolérer les oublis sur téléphone
        import unicodedata
        text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
        return re.sub(r'\s+', ' ', text)

    def evaluate(self, verb: Verb, given_col: str, user_inputs: Dict[str, str]) -> EvaluationResult:
        cols = ["Infinitive", "Preterit", "Past Participle", "Translation"]
        missing = [c for c in cols if c != given_col]

        # 1. Contrôle strict anglais
        for col in missing:
            if col != "Translation":
                if self._normalize_en(user_inputs.get(col, "")) != self._normalize_en(verb.get_field(col)):
                    return EvaluationResult(status="WRONG", missing_translations=[], verb=verb)

        # 2. Contrôle souple français (accents tolérés)
        if "Translation" in missing:
            user_raw = user_inputs.get("Translation", "").strip()
            if not user_raw:
                return EvaluationResult(status="WRONG", missing_translations=[], verb=verb)

            expected_parts = [p.strip() for p in re.split(r'[,/;]', verb.translation) if p.strip()]
            user_tokens = [self._normalize_fr(t) for t in re.split(r'[,/;]', user_raw) if t.strip()]

            expected_norm = {self._normalize_fr(p): p for p in expected_parts}
            matched = set()

            for ut in user_tokens:
                found = False
                for en_norm, orig in expected_norm.items():
                    # Enlève parenthèses optionnelles pour la comparaison
                    clean_norm = re.sub(r'\([^)]*\)', '', en_norm).strip()
                    if ut == en_norm or ut == clean_norm:
                        matched.add(orig)
                        found = True
                        break
                if not found:
                    return EvaluationResult(status="WRONG", missing_translations=[], verb=verb)

            missing_trans = [p for p in expected_parts if p not in matched]
            if missing_trans:
                return EvaluationResult(status="INCOMPLETE", missing_translations=missing_trans, verb=verb)

        return EvaluationResult(status="EXACT", missing_translations=[], verb=verb)


class ContextSentenceService:
    """Génère des phrases TOEIC (Part 5) pour tester les verbes en contexte."""
    
    DICTIONARY = {
        "be": [("Since yesterday, the new project leader has ___ very professional.", "been", "Past Participle")],
        "have": [("By next month, the branch manager will ___ finalized the audit.", "have", "Infinitive")],
        "do": [("Yesterday, the administrative team ___ a great job on reports.", "did", "Preterit")],
        "go": [("Last week, two senior directors ___ to New York for a seminar.", "went", "Preterit")],
        "get": [("The logistics division ___ approval for the new warehouse last Friday.", "got", "Preterit")],
        "make": [("The committee has ___ significant progress on safety regulations.", "made", "Past Participle")],
        "write": [("The lead engineer ___ the technical specification report yesterday.", "wrote", "Preterit")],
        "cut": [("To optimize expenses, management ___ the operating budget last quarter.", "cut", "Preterit")],
        "oversee": [("Since January, the supervisor has ___ the nuclear maintenance schedule.", "overseen", "Past Participle")],
        "meet": [("All suppliers must ___ the required quality standards by tomorrow.", "meet", "Infinitive")],
    }

    def generate(self, verb: Verb) -> Tuple[str, str, str]:
        if verb.infinitive in self.DICTIONARY:
            template, answer, tense = random.choice(self.DICTIONARY[verb.infinitive])
            return template, answer, tense
        
        # Gabarit générique professionnel par défaut
        tenses = [
            (f"Yesterday, the department ___ the contract for {verb.infinitive}.", verb.preterit, "Preterit"),
            (f"Since last month, the team has ___ the process.", verb.past_participle, "Past Participle"),
            (f"Management decided to ___ the new protocol.", verb.infinitive, "Infinitive")
        ]
        return random.choice(tenses)


class SRSService:
    LONG_TERM_STEPS = [1, 3, 7, 16, 35, 90]
    MAX_NEW_PER_DAY = 10

    def __init__(self, verb_repo: IVerbRepository, user_repo: IUserDataRepository):
        self.verb_repo = verb_repo
        self.user_repo = user_repo

    def get_daily_queue(self, username: str, force_early: bool = False) -> Tuple[List[SRSCard], int]:
        data = self.user_repo.get_user_data(username)
        raw_srs = data.get("srs", {})
        cards = {int(k): SRSCard(**v) for k, v in raw_srs.items()}
        
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        introduced_today = sum(1 for c in cards.values() if c.introduced_date == today_str)
        quota = max(0, self.MAX_NEW_PER_DAY - introduced_today)

        if quota > 0:
            all_verbs = self.verb_repo.get_all()
            unseen = [v.id for v in all_verbs if v.id not in cards]
            if unseen:
                new_sel = random.sample(unseen, min(quota, len(unseen)))
                for vid in new_sel:
                    cards[vid] = SRSCard(verb_id=vid, state="learning", step=0, due_timestamp=now.isoformat(), introduced_date=today_str)
                data["srs"] = {str(k): asdict(v) for k, v in cards.items()}
                self.user_repo.save_user_data(username, data)

        due, waiting = [], []
        for card in cards.values():
            if card.is_due(now): due.append(card)
            elif card.state == "learning":
                if force_early: due.append(card)
                else: waiting.append(card)
        due.sort(key=lambda c: c.due_timestamp)
        return due, len(waiting)

    def process_rating(self, username: str, verb_id: int, rating: str):
        data = self.user_repo.get_user_data(username)
        cards = {int(k): SRSCard(**v) for k, v in data.get("srs", {}).items()}
        card = cards.get(verb_id, SRSCard(verb_id=verb_id))
        now = datetime.now()

        if card.state in ("new", "learning"):
            if rating == "again":
                card.step = 0
                card.due_timestamp = (now + timedelta(minutes=1)).isoformat()
                self._log_error(data, verb_id)
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
                self._log_error(data, verb_id)
            elif rating == "hard":
                card.interval_days = max(curr + 1, int(round(curr * 1.2)))
                card.due_timestamp = (now + timedelta(days=card.interval_days)).isoformat()
            elif rating == "good":
                card.interval_days = self._next_interval(curr)
                card.due_timestamp = (now + timedelta(days=card.interval_days)).isoformat()
            elif rating == "easy":
                g = self._next_interval(curr)
                card.interval_days = self._next_interval(g)
                card.due_timestamp = (now + timedelta(days=card.interval_days)).isoformat()

        cards[verb_id] = card
        data["srs"] = {str(k): asdict(v) for k, v in cards.items()}
        self.user_repo.save_user_data(username, data)

    def _next_interval(self, current: int) -> int:
        for s in self.LONG_TERM_STEPS:
            if s > current: return s
        return int(round(current * 2.2))

    def _log_error(self, data: Dict, verb_id: int):
        errors = data.get("errors", [])
        if verb_id not in errors: errors.append(verb_id)
        failures = data.get("failure_counts", {})
        failures[str(verb_id)] = failures.get(str(verb_id), 0) + 1
        data["errors"] = errors
        data["failure_counts"] = failures


class AudioService:
    @staticmethod
    @st.cache_data(show_spinner=False)
    def get_audio(text: str) -> bytes:
        tts = gTTS(text=text.replace("/", ", "), lang='en-US')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return fp.getvalue()


# =====================================================================
# 4. CONTROLLER & VIEWS
# =====================================================================

class AppController:
    COLS = ["Infinitive", "Preterit", "Past Participle", "Translation"]

    def __init__(self, verb_repo, user_repo, auth, evaluator, srs, context_service, audio):
        self.verb_repo = verb_repo
        self.user_repo = user_repo
        self.auth = auth
        self.evaluator = evaluator
        self.srs = srs
        self.context_service = context_service
        self.audio = audio
        self._init_state()

    def _init_state(self):
        defaults = {
            "current_user": None,
            "queue": [],
            "current_idx": None,
            "given_col": None,
            "score": 0,
            "total": 0,
            "last_eval": None,
            "fc_revealed": False,
            "srs_card": None,
            "srs_eval": None,
            "srs_force": False,
            "ctx_verb": None,
            "ctx_eval": None
        }
        for k, v in defaults.items():
            if k not in st.session_state: st.session_state[k] = v

    def run(self):
        st.title("TOEIC Irregular Verbs")

        if not st.session_state.current_user:
            self._auth_view()
            return

        user = st.session_state.current_user
        
        # En-tête utilisateur
        c1, c2 = st.columns([3, 1])
        with c1: st.caption(f"👤 Connecté : **{user}**")
        with c2:
            if st.button("Déconnexion"):
                st.session_state.current_user = None
                st.rerun()

        # Navigation par onglets (Design mobile optimisé)
        tab_srs, tab_train, tab_fc, tab_stats = st.tabs(["🧠 SRS", "🎯 S'entraîner", "🗂️ Flashcards", "📊 Statistiques"])

        with tab_srs: self._srs_view(user)
        with tab_train: self._train_view(user)
        with tab_fc: self._flashcards_view(user)
        with tab_stats: self._stats_view(user)

    def _auth_view(self):
        st.subheader("Connexion requise")
        t1, t2 = st.tabs(["Se connecter", "Créer un compte"])
        with t1:
            with st.form("login"):
                u = st.text_input("Pseudo :")
                p = st.text_input("Code PIN (4 chiffres) :", type="password", max_chars=4)
                if st.form_submit_button("Valider", use_container_width=True):
                    ok, msg = self.auth.login(u, p)
                    if ok:
                        st.session_state.current_user = u.strip()
                        st.rerun()
                    else: st.error(msg)
        with t2:
            with st.form("reg"):
                u = st.text_input("Nouveau pseudo :")
                p = st.text_input("Code PIN (4 chiffres) :", type="password", max_chars=4)
                if st.form_submit_button("Créer", use_container_width=True):
                    ok, msg = self.auth.register(u, p)
                    if ok:
                        st.session_state.current_user = u.strip()
                        st.success(msg)
                        st.rerun()
                    else: st.error(msg)

    def _srs_view(self, user):
        st.subheader("Répétition Espacée (Anki)")
        if st.session_state.srs_card is None:
            due, waiting = self.srs.get_daily_queue(user, force_early=st.session_state.srs_force)
            st.session_state.srs_force = False

            if not due:
                if waiting > 0:
                    st.info(f"⏳ **{waiting} verbe(s)** en pause d'apprentissage (revenant dans quelques minutes).")
                    if st.button("⏩ Réviser sans attendre", use_container_width=True):
                        st.session_state.srs_force = True
                        st.rerun()
                else:
                    st.success("🎉 Session SRS du jour terminée !")
                return

            st.session_state.srs_card = due[0]
            st.session_state.srs_given_col = random.choice(self.COLS)
            st.session_state.srs_eval = None

        card = st.session_state.srs_card
        v = self.verb_repo.get_by_id(card.verb_id)
        col = st.session_state.srs_given_col
        missing = [c for c in self.COLS if c != col]

        st.markdown(f"### {col} : **{v.get_field(col)}**")
        if col != "Translation": st.audio(self.audio.get_audio(v.get_field(col)), format="audio/mp3")

        if st.session_state.srs_eval is None:
            with st.form("srs_f"):
                inputs = {c: st.text_input(f"{c} :", autocomplete="off") for c in missing}
                if st.form_submit_button("Vérifier", type="primary", use_container_width=True):
                    st.session_state.srs_eval = self.evaluator.evaluate(v, col, inputs)
                    st.rerun()
        else:
            res = st.session_state.srs_eval
            if res.status == "EXACT": st.success("✅ Exact !")
            elif res.status == "INCOMPLETE": st.warning(f"⚠️ Partiel — Manquant : `{', '.join(res.missing_translations)}`")
            else: st.error("❌ Incorrect")

            st.write(f"**Complet :** {v.infinitive} | {v.preterit} | {v.past_participle} — *{v.translation}*")
            st.audio(self.audio.get_audio(f"{v.infinitive}, {v.preterit}, {v.past_participle}"), format="audio/mp3")

            st.markdown("##### Évalue ta mémorisation :")
            # Grille 2x2 optimisée mobile
            c1, c2 = st.columns(2)
            if c1.button("🔄 À revoir (+1m)", use_container_width=True):
                self.srs.process_rating(user, v.id, "again")
                st.session_state.srs_card = None
                st.rerun()
            if c2.button("⚠️ Difficile (+5m)", use_container_width=True):
                self.srs.process_rating(user, v.id, "hard")
                st.session_state.srs_card = None
                st.rerun()
            c3, c4 = st.columns(2)
            if c3.button("✅ Correct", type="primary", use_container_width=True):
                self.srs.process_rating(user, v.id, "good")
                st.session_state.srs_card = None
                st.rerun()
            if c4.button("⭐ Facile", use_container_width=True):
                self.srs.process_rating(user, v.id, "easy")
                st.session_state.srs_card = None
                st.rerun()

    def _train_view(self, user):
        data = self.user_repo.get_user_data(user)
        errors = data.get("errors", [])

        mode = st.radio("Mode d'entraînement :", ["Tableau classique (3 colonnes)", "Contexte TOEIC (Part 5)"], key="train_mode")

        if mode == "Contexte TOEIC (Part 5)":
            st.subheader("Part 5 : Phrases professionnelles")
            if st.session_state.ctx_verb is None:
                pool = [self.verb_repo.get_by_id(i) for i in errors] if st.checkbox("Cibler mes erreurs uniquement") else self.verb_repo.get_all()
                if not pool: pool = self.verb_repo.get_all()
                st.session_state.ctx_verb = random.choice(pool)
                st.session_state.ctx_eval = None

            v = st.session_state.ctx_verb
            template, expected, tense = self.context_service.generate(v)
            st.info(f"Niveau : **{v.level}** | Temps recherché : **{tense}**")
            st.markdown(f"#### {template.replace('___', '`___`')}")

            if st.session_state.ctx_eval is None:
                with st.form("ctx_form"):
                    ans = st.text_input("Verbe conjugué attendu :", autocomplete="off")
                    if st.form_submit_button("Valider", type="primary", use_container_width=True):
                        correct = ans.strip().lower() == expected.strip().lower()
                        st.session_state.ctx_eval = (correct, expected, v)
                        if not correct and v.id not in errors:
                            errors.append(v.id)
                            data["errors"] = errors
                            self.user_repo.save_user_data(user, data)
                        st.rerun()
            else:
                correct, exp, vb = st.session_state.ctx_eval
                if correct: st.success("✅ Bonne réponse !")
                else: st.error(f"❌ Faux. Réponse attendue : **{exp}**")
                st.write(f"Traduction : *{vb.translation}*")
                if st.button("Verbe suivant ➡️", type="primary", use_container_width=True):
                    st.session_state.ctx_verb = None
                    st.rerun()
            return

        # Mode classique
        source_choice = st.radio("Source :", ["Tous les verbes (127)", f"Mes erreurs ({len(errors)})"], key="tr_src_cls")
        level_filter = st.selectbox("Filtrer par niveau :", ["Tous", "A1", "A2", "B1", "B2"])

        if st.button("Lancer l'entraînement", type="primary", use_container_width=True):
            base_pool = [self.verb_repo.get_by_id(i) for i in errors] if source_choice.startswith("Mes") else self.verb_repo.get_all()
            if level_filter != "Tous": base_pool = [v for v in base_pool if v.level == level_filter]
            
            if not base_pool:
                st.warning("Aucun verbe disponible avec ces critères.")
                return

            ids = [v.id for v in base_pool]
            random.shuffle(ids)
            st.session_state.queue = ids[1:]
            st.session_state.current_idx = ids[0]
            st.session_state.total = len(ids)
            st.session_state.score = 0
            st.session_state.given_col = random.choice(self.COLS)
            st.session_state.last_eval = None
            st.rerun()

        if st.session_state.current_idx is not None:
            if st.session_state.last_eval is not None:
                res = st.session_state.last_eval
                v = res.verb
                if res.status == "INCOMPLETE": st.warning(f"⚠️ Partiel — Manquant : `{', '.join(res.missing_translations)}`")
                else: st.error("❌ Erreur")
                st.write(f"**Correct :** {v.infinitive} | {v.preterit} | {v.past_participle} | *{v.translation}*")
                if st.button("Continuer", type="primary", use_container_width=True):
                    st.session_state.last_eval = None
                    st.rerun()
                return

            done = st.session_state.total - len(st.session_state.queue)
            st.progress(done / st.session_state.total)
            v = self.verb_repo.get_by_id(st.session_state.current_idx)
            col = st.session_state.given_col
            missing = [c for c in self.COLS if c != col]

            st.markdown(f"### {col} : **{v.get_field(col)}**")
            with st.form("tr_f", clear_on_submit=True):
                inputs = {c: st.text_input(f"{c} :", autocomplete="off") for c in missing}
                if st.form_submit_button("Valider", type="primary", use_container_width=True):
                    res = self.evaluator.evaluate(v, col, inputs)
                    if res.status == "EXACT":
                        st.session_state.score += 1
                        if v.id in errors:
                            errors.remove(v.id)
                            data["errors"] = errors
                            self.user_repo.save_user_data(user, data)
                    else:
                        if v.id not in errors:
                            errors.append(v.id)
                            data["errors"] = errors
                            self.user_repo.save_user_data(user, data)
                        st.session_state.last_eval = res

                    if st.session_state.queue:
                        st.session_state.current_idx = st.session_state.queue.pop(0)
                        st.session_state.given_col = random.choice(self.COLS)
                    else: st.session_state.current_idx = None
                    st.rerun()

    def _flashcards_view(self, user):
        st.subheader("Flashcards (Catalogue & Fiches)")
        data = self.user_repo.get_user_data(user)
        errors = data.get("errors", [])

        source = st.radio("Source :", ["Tous les verbes", f"Mes erreurs ({len(errors)})"], key="fc_s")
        verbs = [self.verb_repo.get_by_id(i) for i in errors] if source.startswith("Mes") else self.verb_repo.get_all()

        options = {f"[{v.level}] {v.infinitive} — {v.translation}": v.id for v in verbs}
        selected = st.multiselect("Rechercher des verbes :", list(options.keys()))

        if selected and st.checkbox("Afficher les fiches détaillées"):
            for label in selected:
                v = self.verb_repo.get_by_id(options[label])
                with st.expander(f"**{v.infinitive}** ({v.level})"):
                    st.write(f"**Prétérit :** `{v.preterit}` | **Participe :** `{v.past_participle}`")
                    st.write(f"**Traduction :** {v.translation}")
                    st.audio(self.audio.get_audio(f"{v.infinitive}, {v.preterit}, {v.past_participle}"), format="audio/mp3")

        if st.button("Lancer en mode révision flashcard", type="primary", use_container_width=True):
            if not selected: st.warning("Sélectionne au moins un verbe.")
            else:
                st.session_state.queue = [options[l] for l in selected]
                st.session_state.fc_revealed = False
                st.session_state.app_submode = "running"

        if st.session_state.get("app_submode") == "running" and st.session_state.queue:
            v = self.verb_repo.get_by_id(st.session_state.queue[0])
            st.markdown(f"## 🃏 {v.infinitive}")
            if not st.session_state.fc_revealed:
                if st.button("Révéler", type="primary", use_container_width=True):
                    st.session_state.fc_revealed = True
                    st.rerun()
            else:
                st.info(f"**Prétérit :** {v.preterit}  \n**Participe :** {v.past_participle}  \n**Traduction :** {v.translation}")
                st.audio(self.audio.get_audio(f"{v.infinitive}, {v.preterit}, {v.past_participle}"), format="audio/mp3")
                if st.button("Suivant ➡️", type="primary", use_container_width=True):
                    st.session_state.queue.pop(0)
                    st.session_state.fc_revealed = False
                    st.rerun()

    def _stats_view(self, user):
        st.subheader("Tableau de bord & Statistiques")
        data = self.user_repo.get_user_data(user)
        errors = data.get("errors", [])
        failures = data.get("failure_counts", {})

        st.metric("Verbes à maîtriser (Erreurs actives)", len(errors))

        if failures:
            st.markdown("#### ⚡ Tes bêtes noires (Top erreurs) :")
            sorted_failures = sorted(failures.items(), key=lambda x: x[1], reverse=True)[:5]
            for vid_str, count in sorted_failures:
                v = self.verb_repo.get_by_id(int(vid_str))
                st.write(f"- **{v.infinitive}** (*{v.translation}*) : raté **{count} fois**")
        else:
            st.info("Aucune bête noire enregistrée pour l'instant. Continue d' t'entraîner !")


# =====================================================================
# 5. ENTRY POINT
# =====================================================================

def main():
    verb_repo = StaticVerbRepository()
    user_repo = GoogleSheetsUserRepository()
    auth = AuthService(user_repo)
    evaluator = EvaluationService()
    srs = SRSService(verb_repo, user_repo)
    context_service = ContextSentenceService()
    audio = AudioService()

    controller = AppController(verb_repo, user_repo, auth, evaluator, srs, context_service, audio)
    controller.run()

if __name__ == "__main__":
    main()
