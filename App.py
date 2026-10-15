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

st.set_page_config(page_title="TOEIC Verbs", layout="centered")

# =====================================================================
# 1. DOMAIN MODELS (Modèles de données)
# =====================================================================

@dataclass(frozen=True)
class Verb:
    id: int
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
    """Charge la liste officielle des 127 verbes irréguliers."""
    
    CSV_DATA = """Infinitive;Preterit;Past Participle;Translation
be;was/were;been;être
have;had;had;avoir
do;did;done;faire
say;said;said;dire
go;went;gone;aller
get;got;gotten;obtenir, recevoir
make;made;made;faire, fabriquer
know;knew;known;connaître, savoir
think;thought;thought;penser
take;took;taken;prendre
see;saw;seen;voir
come;came;come;venir
find;found;found;trouver
give;gave;given;donner
tell;told;told;dire, raconter
feel;felt;felt;toucher, se sentir
become;became;become;devenir
leave;left;left;partir de, sortir de, quitter
put;put;put;mettre
mean;meant;meant;signifier
keep;kept;kept;garder
let;let;let;laisser, permettre
begin;began;begun;commencer
hear;heard;heard;entendre
run;ran;run;courir
hold;held;held;tenir
bring;brought;brought;amener, apporter
write;wrote;written;écrire
sit;sat;sat;(s')asseoir
stand;stood;stood;être debout, se tenir debout
lose;lost;lost;perdre
pay;payed / paid;payed / paid;payer
meet;met;met;rencontrer, retrouver
set;set;set;mettre, poser, placer
lead;led;led;conduire, mener
understand;understood;understood;comprendre
speak;spoke;spoken;parler
read;read;read;lire
spend;spent;spent;dépenser
grow;grew;grown;grandir, pousser
win;won;won;gagner
buy;bought;bought;acheter
send;sent;sent;envoyer
build;built;built;bâtir, construire
fall;fell;fallen;tomber
cut;cut;cut;couper
sell;sold;sold;vendre
drive;drove;driven;conduire, mener
break;broke;broken;casser
wear;wore;worn;porter (des vêtements)
hit;hit;hit;frapper
eat;ate;eaten;manger
teach;taught;taught;enseigner
catch;caught;caught;attraper
draw;drew;drawn;dessiner
choose;chose;chosen;choisir
seek;sought;sought;chercher, rechercher
deal;dealt;dealt;distribuer
fight;fought;fought;lutter, combattre
throw;threw;thrown;jeter, lancer
rise;rose;risen;se lever
shoot;shot;shot;tirer
lie;lay;lain;s'allonger
lay;laid;laid;mettre, poser
hang;hung;hung;suspendre, accrocher, monter, poser
forget;forgot;forgotten;oublier
shake;shook;shaken;secouer, agiter
fly;flew;flown;voler
sing;sang;sung;chanter
beat;beat;beaten;battre, frapper
be born;was born;been born;naître
cost;cost;cost;coûter
hurt;hurt;hurt;faire du mal à, se blesser
strike;struck;stricken;frapper, faire grève
sleep;slept;slept;dormir
stick;stuck;stuck;piquer, planter, être collé
drink;drank;drunk;boire
hide;hid;hidden;cacher, se cacher
ride;rode;ridden;monter à, faire du
feed;fed;fed;nourrir
fit;fit;fit;aller à, entrer
spread;spread;spread;étendre, étaler, s'élargir
blow;blew;blown;pousser, chasser, souffler
shut;shut;shut;(re)fermer, repousser
bear;bore;born;porter, se diriger
wake;woke;woken;se réveiller, s'éveiller
steal;stole;stolen;voler, dérober
slide;slid;slid;glisser, se glisser
bend;bent;bent;courber, plier, pencher, faire ployer, tordre
tear;tore;torn;déchirer
ring;rang;rung;sonner
light;lit;lit;allumer, éclairer
swing;swung;swung;se balancer, osciller
dig;dug;dug;creuser, bêcher, arracher
bind;bound;bound;attacher, entourer, bander
quit;quit;quit;quitter, sortir, partir
arise;arose;arisen;surgir, se présenter, résulter
sweep;swept;swept;balayer, ramoner
spin;spun;spun;filer, fabriquer, faire tourner
wind;wound;wound;enrouler, envelopper, remonter
bet;bet;bet;parier
overcome;overcame;overcome;surmonter, triompher de, battre
withdraw;withdrew;withdrawn;(se) retirer, se replier
freeze;froze;frozen;geler, se congeler, se figer
sink;sank;sunk;couler, baisser
swim;swam;swum;nager
split;split;split;fendre, diviser
flee;fled;fled;(s')enfuir
rid;rid;rid;débarrasser, laisser tomber
undergo;underwent;undergone;subir, éprouver
swear;swore;sworn;jurer
shine;shone;shone;briller
upset;upset;upset;renverser, bouleverser, vexer
burst;burst;burst;éclater, crever
speed;speeded/sped;speeded/sped;aller à toute vitesse
forgive;forgave;forgiven;pardonner
rebuild;rebuilt;rebuilt;rebâtir, refaire
undertake;undertook;undertaken;entreprendre, se charger de, assumer
spring;sprang;sprung;bondir
oversee;oversaw;overseen;surveiller
shed;shed;shed;perdre, verser
shrink;shrank;shrunk;rétrécir, (se) réduire
sneak;snuck;snuck;entrer/sortir furtivement, faire qqc discrètement, s'éclipser
cling;clang;clung;se cramponner, adhérer, coller
forbid;forbade;forbidden;interdire
spit;spit/spat;spit/spat;cracher, crépiter
kneel;kneeled/knelt;kneeled/knelt;s'agenouiller, être agenouillé"""

    def __init__(self):
        df = pd.read_csv(io.StringIO(self.CSV_DATA), sep=";")
        self._verbs: List[Verb] = [
            Verb(
                id=int(idx),
                infinitive=row["Infinitive"].strip(),
                preterit=row["Preterit"].strip(),
                past_participle=row["Past Participle"].strip(),
                translation=row["Translation"].strip()
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
    def save_errors(self, username: str, error_ids: List[int]) -> None: pass

    @abstractmethod
    def get_paused_session(self, username: str) -> Dict: pass

    @abstractmethod
    def save_paused_session(self, username: str, session_data: Dict) -> None: pass

    @abstractmethod
    def get_srs_cards(self, username: str) -> Dict[int, SRSCard]: pass

    @abstractmethod
    def save_srs_cards(self, username: str, cards: Dict[int, SRSCard]) -> None: pass


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
    
    # Création automatique de l'onglet unique de stockage JSON par utilisateur
    try:
        ws = sheet.worksheet("app_data")
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title="app_data", rows=100, cols=5)
        ws.append_row(["username", "pin_hash", "errors_json", "session_json", "srs_json"])
    return ws


class GoogleSheetsUserRepository(IUserDataRepository):
    """Persiste toutes les données par utilisateur dans une ligne Google Sheets dédiée."""

    def __init__(self):
        self.ws = get_gspread_sheet()

    def _find_user_row(self, username: str) -> Tuple[Optional[int], Optional[Dict]]:
        records = self.ws.get_all_records()
        for idx, row in enumerate(records, start=2):  # Ligne 1 = en-têtes
            if str(row.get("username", "")).strip().lower() == username.strip().lower():
                return idx, row
        return None, None

    def _ensure_cache(self, username: str):
        if "db_cache" not in st.session_state or st.session_state.db_cache.get("username") != username:
            row_idx, row_data = self._find_user_row(username)
            if row_data:
                st.session_state.db_cache = {
                    "username": username,
                    "row_idx": row_idx,
                    "pin_hash": str(row_data.get("pin_hash", "")),
                    "errors": json.loads(row_data.get("errors_json") or "[]"),
                    "session": json.loads(row_data.get("session_json") or "{}"),
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

    def save_errors(self, username: str, error_ids: List[int]) -> None:
        self._ensure_cache(username)
        st.session_state.db_cache["errors"] = error_ids
        row_idx = st.session_state.db_cache["row_idx"]
        self.ws.update_cell(row_idx, 3, json.dumps(error_ids))

    def get_paused_session(self, username: str) -> Dict:
        self._ensure_cache(username)
        return dict(st.session_state.db_cache.get("session", {}))

    def save_paused_session(self, username: str, session_data: Dict) -> None:
        self._ensure_cache(username)
        st.session_state.db_cache["session"] = session_data
        row_idx = st.session_state.db_cache["row_idx"]
        self.ws.update_cell(row_idx, 4, json.dumps(session_data))

    def get_srs_cards(self, username: str) -> Dict[int, SRSCard]:
        self._ensure_cache(username)
        raw_srs = st.session_state.db_cache.get("srs", {})
        return {int(k): SRSCard(**v) for k, v in raw_srs.items()}

    def save_srs_cards(self, username: str, cards: Dict[int, SRSCard]) -> None:
        self._ensure_cache(username)
        serialized = {str(k): asdict(v) for k, v in cards.items()}
        st.session_state.db_cache["srs"] = serialized
        row_idx = st.session_state.db_cache["row_idx"]
        self.ws.update_cell(row_idx, 5, json.dumps(serialized))


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
    """Évalue les réponses (strict sur l'anglais, partiel autorisé sur la traduction)."""

    @staticmethod
    def _normalize_english(text: str) -> str:
        text = text.strip().lower()
        # Uniformise les espaces autour des slashs (ex: "payed / paid" == "payed/paid")
        text = re.sub(r'\s*/\s*', '/', text)
        text = re.sub(r'\s+', ' ', text)
        return text

    @staticmethod
    def _clean_french_token(token: str) -> str:
        token = token.strip().lower()
        token = token.replace("’", "'")
        token = re.sub(r'\s+', ' ', token)
        return token

    @classmethod
    def _expand_french_variants(cls, raw_translation: str) -> Tuple[List[str], Dict[str, str]]:
        """
        Découpe les traductions par ',' ou '/' et gère les parenthèses optionnelles.
        Retourne (liste_canonique, dict_variante_vers_canonique).
        """
        raw_parts = [p.strip() for p in re.split(r'[,/;]', raw_translation) if p.strip()]
        canonical_list = []
        variant_map = {}

        for part in raw_parts:
            clean_part = cls._clean_french_token(part)
            canonical_list.append(clean_part)
            variant_map[clean_part] = clean_part

            # Ex: "(s')asseoir" -> accepte "s'asseoir" et "asseoir"
            # Ex: "porter (des vêtements)" -> accepte "porter" et "porter des vêtements"
            no_parens = cls._clean_french_token(re.sub(r'\([^)]*\)', '', clean_part))
            with_parens_content = cls._clean_french_token(re.sub(r'[()]', '', clean_part))
            
            if no_parens:
                variant_map[no_parens] = clean_part
            if with_parens_content:
                variant_map[with_parens_content] = clean_part

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

        # 2. Vérification de la traduction française (si elle fait partie des champs à remplir)
        if "Translation" in missing_cols:
            user_raw = user_inputs.get("Translation", "").strip()
            if not user_raw:
                return EvaluationResult(status="WRONG", missing_translations=[], verb=verb)

            canonical_expected, variant_map = self._expand_french_variants(verb.translation)
            user_tokens = [self._clean_french_token(t) for t in re.split(r'[,/;]', user_raw) if t.strip()]

            if not user_tokens:
                return EvaluationResult(status="WRONG", missing_translations=[], verb=verb)

            matched_canonicals = set()
            for u_tok in user_tokens:
                if u_tok in variant_map:
                    matched_canonicals.add(variant_map[u_tok])
                else:
                    # Dès qu'un mot saisi est faux, toute la réponse est fausse
                    return EvaluationResult(status="WRONG", missing_translations=[], verb=verb)

            missing = [c for c in canonical_expected if c not in matched_canonicals]
            if missing:
                return EvaluationResult(status="INCOMPLETE", missing_translations=missing, verb=verb)

        return EvaluationResult(status="EXACT", missing_translations=[], verb=verb)


class SRSService:
    """Implémente l'algorithme de répétition espacée (Anki)."""

    LONG_TERM_STEPS = [1, 3, 7, 16, 35, 90]
    MAX_NEW_PER_DAY = 10

    def __init__(self, verb_repo: IVerbRepository, user_repo: IUserDataRepository):
        self.verb_repo = verb_repo
        self.user_repo = user_repo

    def get_daily_queue(self, username: str, force_early: bool = False) -> Tuple[List[SRSCard], int]:
        """Retourne (cartes_dues_maintenant, nb_cartes_en_attente_dans_quelques_minutes)."""
        cards = self.user_repo.get_srs_cards(username)
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        # Compte combien de nouveaux verbes ont déjà été introduits aujourd'hui
        introduced_today = sum(1 for c in cards.values() if c.introduced_date == today_str)
        remaining_new_quota = max(0, self.MAX_NEW_PER_DAY - introduced_today)

        # Ajoute jusqu'à 10 nouveaux verbes si le quota du jour n'est pas atteint
        if remaining_new_quota > 0:
            all_verb_ids = [v.id for v in self.verb_repo.get_all()]
            unseen_ids = [vid for vid in all_verb_ids if vid not in cards]
            if unseen_ids:
                new_selection = random.sample(unseen_ids, min(remaining_new_quota, len(unseen_ids)))
                for vid in new_selection:
                    cards[vid] = SRSCard(
                        verb_id=vid,
                        state="learning",
                        step=0,
                        interval_days=0,
                        due_timestamp=now.isoformat(),
                        introduced_date=today_str
                    )
                self.user_repo.save_srs_cards(username, cards)

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
        """Calcule les intitulés exacts des 4 boutons selon l'état de la carte."""
        if card.state in ("new", "learning"):
            if card.step == 0:
                return {
                    "again": "À revoir (+1 min)",
                    "hard": "Difficile (+5 min)",
                    "good": "Correct (+10 min)",
                    "easy": "Facile (+4 j)"
                }
            else:
                return {
                    "again": "À revoir (+1 min)",
                    "hard": "Difficile (+5 min)",
                    "good": "Correct (+1 j)",
                    "easy": "Facile (+4 j)"
                }
        else:
            # Phase mémoire à long terme
            curr = max(1, card.interval_days)
            hard_days = max(curr + 1, int(round(curr * 1.2)))
            good_days = self._next_good_interval(curr)
            easy_days = self._next_good_interval(good_days)
            return {
                "again": "À revoir (+1 min)",
                "hard": f"Difficile (+{hard_days} j)",
                "good": f"Correct (+{good_days} j)",
                "easy": f"Facile (+{easy_days} j)"
            }

    def _next_good_interval(self, current_days: int) -> int:
        for step in self.LONG_TERM_STEPS:
            if step > current_days:
                return step
        return int(round(current_days * 2.2))

    def process_rating(self, username: str, verb_id: int, rating: str) -> None:
        """Met à jour l'intervalle de la carte et ajoute aux erreurs en cas d'échec."""
        cards = self.user_repo.get_srs_cards(username)
        card = cards.get(verb_id, SRSCard(verb_id=verb_id, state="learning"))
        now = datetime.now()

        if card.state in ("new", "learning"):
            if rating == "again":
                card.step = 0
                card.due_timestamp = (now + timedelta(minutes=1)).isoformat()
                self._add_to_errors(username, verb_id)
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
                # Rechute : retour à +1 min et ajout aux erreurs
                card.state = "learning"
                card.step = 0
                card.interval_days = 0
                card.due_timestamp = (now + timedelta(minutes=1)).isoformat()
                self._add_to_errors(username, verb_id)
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
        self.user_repo.save_srs_cards(username, cards)

    def _add_to_errors(self, username: str, verb_id: int) -> None:
        errors = self.user_repo.get_errors(username)
        if verb_id not in errors:
            errors.append(verb_id)
            self.user_repo.save_errors(username, errors)


class AudioService:
    """Génère la synthèse vocale en anglais américain."""

    @staticmethod
    @st.cache_data(show_spinner=False)
    def get_audio(text: str) -> bytes:
        clean_text = text.replace("/", ", ")
        tts = gTTS(text=clean_text, lang='en-US')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return fp.getvalue()


# =====================================================================
# 4. CONTROLLER & VIEWS (Gestion de l'interface et de la navigation)
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
            "app_mode": "menu",
            "queue": [],
            "current_idx": None,
            "given_col": None,
            "score": 0,
            "total": 0,
            "last_eval": None,
            "flashcard_revealed": False,
            "srs_current_card": None,
            "srs_given_col": None,
            "srs_eval_result": None,
            "srs_force_early": False
        }
        for k, v in defaults.items():
            if k not in st.session_state:
                st.session_state[k] = v

    def run(self):
        st.title("TOEIC Irregular Verbs")

        if not st.session_state.current_user:
            self._render_auth_view()
            return

        # Barre supérieure utilisateur
        col_u1, col_u2 = st.columns([3, 1])
        with col_u1:
            st.caption(f"👤 Connecté : **{st.session_state.current_user}**")
        with col_u2:
            if st.button("Déconnexion"):
                st.session_state.current_user = None
                st.session_state.app_mode = "menu"
                st.rerun()

        mode = st.session_state.app_mode
        if mode == "menu":
            self._render_menu_view()
        elif mode == "training":
            self._render_training_view()
        elif mode == "flashcards":
            self._render_flashcards_view()
        elif mode == "srs":
            self._render_srs_view()

    # --- VUE : AUTHENTIFICATION ---
    def _render_auth_view(self):
        st.subheader("Identification")
        tab_login, tab_reg = st.tabs(["Connexion", "Créer un compte"])

        with tab_login:
            with st.form("login_form"):
                u_login = st.text_input("Pseudo :")
                p_login = st.text_input("Code PIN (4 chiffres) :", type="password", max_chars=4)
                if st.form_submit_button("Se connecter", use_container_width=True):
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
                if st.form_submit_button("Créer mon compte", use_container_width=True):
                    ok, msg = self.auth_service.register(u_reg, p_reg)
                    if ok:
                        st.session_state.current_user = u_reg.strip()
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    # --- VUE : MENU PRINCIPAL ---
    def _render_menu_view(self):
        user = st.session_state.current_user
        errors = self.user_repo.get_errors(user)
        paused = self.user_repo.get_paused_session(user)

        # 1. Reprise de session en pause
        if paused and paused.get("current_idx") is not None:
            rem = len(paused.get("queue", [])) + 1
            st.info(f"⏸️ Session en pause : **{rem} verbe(s) restant(s)**.")
            if st.button("Reprendre la session", type="primary", use_container_width=True):
                st.session_state.queue = paused["queue"]
                st.session_state.score = paused["score"]
                st.session_state.total = paused["total"]
                st.session_state.current_idx = paused["current_idx"]
                st.session_state.given_col = paused["given_col"]
                st.session_state.last_eval = None
                st.session_state.app_mode = "training"
                self.user_repo.save_paused_session(user, {})
                st.rerun()
            st.write("---")

        # 2. Mode SRS (Anki)
        st.subheader("1. Mode SRS (Mémoire long terme)")
        st.caption("10 nouveaux verbes/jour max + révisions espacées (+1min, +5min, +10min, jours).")
        if st.button("Lancer ma session SRS du jour", type="primary", use_container_width=True):
            st.session_state.srs_current_card = None
            st.session_state.srs_eval_result = None
            st.session_state.srs_force_early = False
            st.session_state.app_mode = "srs"
            st.rerun()

        st.write("---")

        # 3. Mode Flashcards (Catalogue à la carte + Aléatoire)
        st.subheader("2. Flashcards (Catalogue & Révision)")
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
                options_map = {f"{v.infinitive} ({v.translation})": v.id for v in source_verbs}
                chosen_labels = st.multiselect(
                    "Recherche et sélectionne tes verbes :",
                    options=list(options_map.keys())
                )
                selected_fc_ids = [options_map[lbl] for lbl in chosen_labels]

                # Aperçu rapide sous forme de liste déroulante si souhaité
                if selected_fc_ids and st.checkbox("Afficher directement la fiche récapitulative ici"):
                    for vid in selected_fc_ids:
                        vb = self.verb_repo.get_by_id(vid)
                        with st.expander(f"**{vb.infinitive}** — {vb.translation}"):
                            st.write(f"**Prétérit :** `{vb.preterit}` | **Participe Passé :** `{vb.past_participle}`")
                            st.audio(self.audio_service.get_audio(f"{vb.infinitive}, {vb.preterit}, {vb.past_participle}"), format="audio/mp3")

        if st.button("Lancer les Flashcards", use_container_width=True):
            if not source_verbs:
                st.warning("Aucune erreur enregistrée pour le moment.")
            elif fc_style == "Catalogue (Choisir les verbes)" and not selected_fc_ids:
                st.warning("Sélectionne au moins un verbe dans le catalogue.")
            else:
                if fc_style == "Catalogue (Choisir les verbes)":
                    st.session_state.queue = selected_fc_ids
                else:
                    ids = [v.id for v in source_verbs]
                    random.shuffle(ids)
                    st.session_state.queue = ids
                st.session_state.flashcard_revealed = False
                st.session_state.app_mode = "flashcards"
                st.rerun()

        st.write("---")

        # 4. Mode Entraînement classique
        st.subheader("3. S'entraîner (Listes)")
        tr_source = st.radio(
            "Source Entraînement :",
            ["Tous les verbes (127)", f"Mes erreurs ({len(errors)})"],
            key="tr_src"
        )
        nb_verbs = 127
        if tr_source.startswith("Tous"):
            nb_verbs = st.selectbox("Nombre de verbes :", [20, 50, 100, 127])

        if st.button("Lancer l'entraînement", use_container_width=True):
            if tr_source.startswith("Mes erreurs") and not errors:
                st.warning("Aucune erreur enregistrée pour le moment.")
            else:
                pool = errors if tr_source.startswith("Mes erreurs") else [v.id for v in self.verb_repo.get_all()]
                sample_size = len(pool) if tr_source.startswith("Mes erreurs") else min(nb_verbs, len(pool))
                sampled = random.sample(pool, sample_size)

                st.session_state.current_idx = sampled.pop(0)
                st.session_state.queue = sampled
                st.session_state.total = sample_size
                st.session_state.score = 0
                st.session_state.given_col = random.choice(self.COLS)
                st.session_state.last_eval = None
                st.session_state.app_mode = "training"
                st.rerun()

    # --- VUE : FLASHCARDS ---
    def _render_flashcards_view(self):
        if not st.session_state.queue:
            st.success("Toutes les flashcards sélectionnées ont été révisées !")
            if st.button("Retour au menu", use_container_width=True):
                st.session_state.app_mode = "menu"
                st.rerun()
            return

        v = self.verb_repo.get_by_id(st.session_state.queue[0])
        st.caption(f"Cartes restantes : {len(st.session_state.queue)}")
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
                st.session_state.queue.pop(0)
                st.session_state.flashcard_revealed = False
                st.rerun()

        st.write("---")
        if st.button("Quitter les flashcards", use_container_width=True):
            st.session_state.app_mode = "menu"
            st.rerun()

    # --- VUE : ENTRAÎNEMENT ---
    def _render_training_view(self):
        user = st.session_state.current_user

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
            st.success(f"🎉 Session terminée ! Score : **{st.session_state.score} / {st.session_state.total}**")
            if st.button("Retour au menu", type="primary", use_container_width=True):
                st.session_state.app_mode = "menu"
                st.rerun()
            return

        # 3. Saisie active
        done_count = st.session_state.total - len(st.session_state.queue)
        st.progress(done_count / st.session_state.total, text=f"Verbe {done_count} / {st.session_state.total}")

        v = self.verb_repo.get_by_id(st.session_state.current_idx)
        given_c = st.session_state.given_col
        missing_cols = [c for c in self.COLS if c != given_c]

        st.markdown(f"### {given_c} : **{v.get_field(given_c)}**")
        if given_c != "Translation":
            st.audio(self.audio_service.get_audio(v.get_field(given_c)), format="audio/mp3")

        with st.form("training_form", clear_on_submit=True):
            user_inputs = {col: st.text_input(f"{col} :", autocomplete="off") for col in missing_cols}
            submitted = st.form_submit_button("Valider", type="primary", use_container_width=True)

            if submitted:
                eval_res = self.eval_service.evaluate(v, given_c, user_inputs)
                errors = self.user_repo.get_errors(user)

                if eval_res.status == "EXACT":
                    st.session_state.score += 1
                    if v.id in errors:
                        errors.remove(v.id)
                        self.user_repo.save_errors(user, errors)
                elif eval_res.status == "INCOMPLETE":
                    st.session_state.score += 1
                    if v.id not in errors:
                        errors.append(v.id)
                        self.user_repo.save_errors(user, errors)
                    st.session_state.last_eval = eval_res
                else:
                    if v.id not in errors:
                        errors.append(v.id)
                        self.user_repo.save_errors(user, errors)
                    st.session_state.last_eval = eval_res

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
                })
                st.session_state.app_mode = "menu"
                st.rerun()
        with c2:
            if st.button("⏹️ Arrêter définitivement", use_container_width=True):
                self.user_repo.save_paused_session(user, {})
                st.session_state.current_idx = None
                st.session_state.queue = []
                st.session_state.app_mode = "menu"
                st.rerun()

    # --- VUE : MODE SRS (ANKI) ---
    def _render_srs_view(self):
        user = st.session_state.current_user

        # Charge une carte due si aucune n'est active à l'écran
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
                        if st.button("⏩ Réviser sans attendre", use_container_width=True):
                            st.session_state.srs_force_early = True
                            st.rerun()
                else:
                    st.success("🎉 Bravo ! Tu as terminé toutes tes révisions SRS et tes 10 nouveaux verbes du jour.")
                
                if st.button("Retour au menu", use_container_width=True):
                    st.session_state.app_mode = "menu"
                    st.rerun()
                return

            st.session_state.srs_current_card = due_cards[0]
            st.session_state.srs_given_col = random.choice(self.COLS)
            st.session_state.srs_eval_result = None

        card: SRSCard = st.session_state.srs_current_card
        v = self.verb_repo.get_by_id(card.verb_id)
        given_c = st.session_state.srs_given_col
        missing_cols = [c for c in self.COLS if c != given_c]

        st.markdown(f"### {given_c} : **{v.get_field(given_c)}**")
        if given_c != "Translation":
            st.audio(self.audio_service.get_audio(v.get_field(given_c)), format="audio/mp3")

        # Étape 1 : Test de mémoire active
        if st.session_state.srs_eval_result is None:
            with st.form("srs_form", clear_on_submit=True):
                user_inputs = {col: st.text_input(f"{col} :", autocomplete="off") for col in missing_cols}
                if st.form_submit_button("Vérifier ma réponse", type="primary", use_container_width=True):
                    st.session_state.srs_eval_result = self.eval_service.evaluate(v, given_c, user_inputs)
                    st.rerun()

        # Étape 2 : Affichage de la correction complète + 4 boutons d'intervalles Anki
        else:
            res: EvaluationResult = st.session_state.srs_eval_result
            if res.status == "EXACT":
                st.success("✅ **Réponse exacte !**")
            elif res.status == "INCOMPLETE":
                st.warning(f"⚠️ **Réponse incomplète** — Manquant : `{', '.join(res.missing_translations)}`")
            else:
                st.error("❌ **Réponse fausse**")

            st.markdown("#### Forme complète :")
            st.write(f"**Infinitif :** {v.infinitive} | **Prétérit :** {v.preterit} | **Participe Passé :** {v.past_participle}")
            st.write(f"**Traductions :** **{v.translation}**")
            st.audio(self.audio_service.get_audio(f"{v.infinitive}, {v.preterit}, {v.past_participle}"), format="audio/mp3")

            st.markdown("##### Choisis l'intervalle de répétition :")
            labels = self.srs_service.get_button_labels(card)
            b1, b2, b3, b4 = st.columns(4)

            if b1.button(labels["again"], use_container_width=True):
                self.srs_service.process_rating(user, v.id, "again")
                st.session_state.srs_current_card = None
                st.rerun()
            if b2.button(labels["hard"], use_container_width=True):
                self.srs_service.process_rating(user, v.id, "hard")
                st.session_state.srs_current_card = None
                st.rerun()
            if b3.button(labels["good"], type="primary", use_container_width=True):
                self.srs_service.process_rating(user, v.id, "good")
                st.session_state.srs_current_card = None
                st.rerun()
            if b4.button(labels["easy"], use_container_width=True):
                self.srs_service.process_rating(user, v.id, "easy")
                st.session_state.srs_current_card = None
                st.rerun()

        st.write("---")
        if st.button("Quitter la session SRS", use_container_width=True):
            st.session_state.srs_current_card = None
            st.session_state.app_mode = "menu"
            st.rerun()


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
