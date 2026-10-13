import streamlit as st
import pandas as pd
import random
import io
from streamlit_cookies_controller import CookieController
from gtts import gTTS

st.set_page_config(page_title="TOEIC Verbs", layout="centered")

controller = CookieController()

# --- DONNÉES ---
csv_data = """Infinitive;Preterit;Past Participle;Translation
be;was/were;been;être / avoir
do;did;done;faire
say;said;said;dire
go;went;gone;aller
get;got;gotten;obtenir / recevoir
make;made;made;faire / fabriquer
know;knew;known;connaître / savoir
think;thought;thought;penser
take;took;taken;prendre
see;saw;seen;voir
come;came;come;venir
find;found;found;trouver
give;gave;given;donner
tell;told;told;dire / raconter
feel;felt;felt;toucher / se sentir
become;became;become;devenir
leave;left;left;partir de / sortir de / quitter
put;put;put;mettre
mean;meant;meant;signifier
keep;kept;kept;garder
let;let;let;laisser / permettre
begin;began;begun;commencer
hear;heard;heard;entendre
run;ran;run;courir
hold;held;held;tenir
bring;brought;brought;amener / apporter
write;wrote;written;écrire
sit;sat;sat;s'asseoir
stand;stood;stood;être debout
lose;lost;lost;perdre
pay;payed / paid;payed / paid;payer
meet;met;met;rencontrer / retrouver
set;set;set;mettre / poser / placer
lead;led;led;conduire / mener
understand;understood;understood;comprendre
speak;spoke;spoken;parler
read;read;read;lire
spend;spent;spent;dépenser
grow;grew;grown;grandir / pousser
win;won;won;gagner
buy;bought;bought;acheter
send;sent;sent;envoyer
build;built;built;bâtir / construire
fall;fell;fallen;tomber
cut;cut;cut;couper
sell;sold;sold;vendre
drive;drove;driven;conduire / mener
break;broke;broken;casser
wear;wore;worn;porter (des vêtements)
hit;hit;hit;frapper
eat;ate;eaten;manger
teach;taught;taught;enseigner
catch;caught;caught;attraper
draw;drew;drawn;dessiner
choose;chose;chosen;choisir
seek;sought;sought;chercher / rechercher
deal;dealt;dealt;distribuer
fight;fought;fought;lutter / combattre
throw;threw;thrown;jeter / lancer
rise;rose;risen;se lever
shoot;shot;shot;tirer
lie;lay;lain;s'allonger
lay;laid;laid;mettre / poser
hang;hung;hung;suspendre / accrocher
forget;forgot;forgotten;oublier
shake;shook;shaken;secouer / agiter
fly;flew;flown;voler
sing;sang;sung;chanter
beat;beat;beaten;battre / frapper
be born;was born;been born;naître
cost;cost;cost;coûter
hurt;hurt;hurt;faire du mal à / se blesser
strike;struck;stricken;frapper / faire grève
sleep;slept;slept;dormir
stick;stuck;stuck;piquer / planter / être collé
drink;drank;drunk;boire
hide;hid;hidden;cacher / se cacher
ride;rode;ridden;monter à / faire du
feed;fed;fed;nourrir
fit;fit;fit;aller à / entrer
spread;spread;spread;étendre / étaler
blow;blew;blown;pousser / chasser / souffler
shut;shut;shut;refermer / repousser
bear;bore;born;porter / se diriger
wake;woke;woken;se réveiller / s'éveiller
steal;stole;stolen;voler / dérober
slide;slid;slid;glisser / se glisser
bend;bent;bent;courber / plier / tordre
tear;tore;torn;déchirer
ring;rang;rung;sonner
light;lit;lit;allumer / éclairer
swing;swung;swung;se balancer / osciller
dig;dug;dug;creuser / bêcher
bind;bound;bound;attacher / entourer
quit;quit;quit;quitter / sortir / partir
arise;arose;arisen;surgir / se présenter
sweep;swept;swept;balayer / ramoner
spin;spun;spun;filer / faire tourner
wind;wound;wound;enrouler / remonter
bet;bet;bet;parier
overcome;overcame;overcome;surmonter / triompher
withdraw;withdrew;withdrawn;se retirer / se replier
freeze;froze;frozen;geler / se figer
sink;sank;sunk;couler / baisser
swim;swam;swum;nager
split;split;split;fendre / diviser
flee;fled;fled;s'enfuir
rid;rid;rid;débarrasser / laisser tomber
undergo;underwent;undergone;subir / éprouver
swear;swore;sworn;jurer
shine;shone;shone;briller
upset;upset;upset;renverser / bouleverser
burst;burst;burst;éclater / crever
speed;sped;sped;aller à toute vitesse
forgive;forgave;forgiven;pardonner
rebuild;rebuilt;rebuilt;rebâtir / refaire
undertake;undertook;undertaken;entreprendre / assumer
spring;sprang;sprung;bondir
oversee;oversaw;overseen;surveiller
shed;shed;shed;perdre / verser
shrink;shrank;shrunk;rétrécir / se réduire
sneak;snuck;snuck;entrer furtivement
cling;clung;clung;se cramponner / coller
forbid;forbade;forbidden;interdire
spit;spat;spat;cracher
kneel;knelt;knelt;s'agenouiller"""

@st.cache_data
def load_data():
    return pd.read_csv(io.StringIO(csv_data), sep=";")

df = load_data()
cols = ["Infinitive", "Preterit", "Past Participle", "Translation"]

@st.cache_data(show_spinner=False)
def get_audio(text):
    tts = gTTS(text=text, lang='en-US')
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    return fp.getvalue()

# --- LECTURE DES COOKIES ---
saved_errors = controller.get('toeic_errors')
if type(saved_errors) is not list:
    saved_errors = []
saved_errors = [int(i) for i in saved_errors if str(i).isdigit()]

saved_session = controller.get('toeic_session')

# --- INITIALISATION ETAT ---
if 'error_list' not in st.session_state: st.session_state.error_list = saved_errors
if 'app_mode' not in st.session_state: st.session_state.app_mode = "menu"
if 'queue' not in st.session_state: st.session_state.queue = []
if 'current_idx' not in st.session_state: st.session_state.current_idx = None
if 'given_col' not in st.session_state: st.session_state.given_col = None
if 'score' not in st.session_state: st.session_state.score = 0
if 'total' not in st.session_state: st.session_state.total = 0
if 'show_correction' not in st.session_state: st.session_state.show_correction = False
if 'last_idx' not in st.session_state: st.session_state.last_idx = None
if 'flashcard_revealed' not in st.session_state: st.session_state.flashcard_revealed = False

st.title("TOEIC Irregular Verbs")

# ====================================================
# MODE : MENU PRINCIPAL
# ====================================================
if st.session_state.app_mode == "menu":
    
    # 1. Zone de reprise de session
    if saved_session and type(saved_session) is dict and len(saved_session.get('queue', [])) > 0:
        st.info(f"Session en pause : {len(saved_session['queue'])} verbes restants.")
        if st.button("Reprendre la session", type="primary", use_container_width=True):
            st.session_state.queue = saved_session['queue']
            st.session_state.score = saved_session['score']
            st.session_state.total = saved_session['total']
            st.session_state.current_idx = saved_session['current_idx']
            st.session_state.given_col = saved_session['given_col']
            st.session_state.app_mode = "training"
            controller.set('toeic_session', {}) # On vide la sauvegarde
            st.rerun()
        st.write("---")

    # 2. Zone Flashcards
    st.subheader("1. Flashcards (Révision)")
    fc_mode = st.radio("Source Flashcards :", ["Tous les verbes", "Mes erreurs"], key="fc_radio")
    if st.button("Lancer Flashcards", use_container_width=True):
        if fc_mode == "Mes erreurs" and len(st.session_state.error_list) == 0:
            st.warning("Aucune erreur enregistrée pour le moment.")
        else:
            source_df = df.iloc[st.session_state.error_list] if fc_mode == "Mes erreurs" else df
            st.session_state.queue = source_df.sample(frac=1).index.tolist() # Mélange total
            st.session_state.app_mode = "flashcards"
            st.session_state.flashcard_revealed = False
            st.rerun()
            
    st.write("---")
    
    # 3. Zone Entraînement
    st.subheader("2. S'entraîner")
    tr_mode = st.radio("Source Entraînement :", ["Tous les verbes", "Mes erreurs"], key="tr_radio")
    
    if tr_mode == "Tous les verbes":
        nb_verbs = st.selectbox("Nombre de verbes :", [20, 50, 100, 127])
    
    if st.button("Lancer Entraînement", use_container_width=True):
        if tr_mode == "Mes erreurs" and len(st.session_state.error_list) == 0:
            st.warning("Aucune erreur enregistrée pour le moment.")
        else:
            source_df = df.iloc[st.session_state.error_list] if tr_mode == "Mes erreurs" else df
            sample_size = len(source_df) if tr_mode == "Mes erreurs" else min(nb_verbs, len(source_df))
            
            st.session_state.queue = source_df.sample(sample_size).index.tolist()
            st.session_state.total = sample_size
            st.session_state.score = 0
            
            st.session_state.current_idx = st.session_state.queue.pop(0)
            st.session_state.given_col = random.choice(cols)
            st.session_state.app_mode = "training"
            st.rerun()

# ====================================================
# MODE : FLASHCARDS
# ====================================================
elif st.session_state.app_mode == "flashcards":
    if not st.session_state.queue:
        st.success("Toutes les flashcards ont été vues !")
        if st.button("Retour au menu", use_container_width=True):
            st.session_state.app_mode = "menu"
            st.rerun()
    else:
        idx = st.session_state.queue[0]
        v = df.iloc[idx]
        
        st.markdown(f"## {v['Infinitive']}")
        st.audio(get_audio(v['Infinitive']), format="audio/mp3")
        
        if not st.session_state.flashcard_revealed:
            if st.button("Révéler", use_container_width=True):
                st.session_state.flashcard_revealed = True
                st.rerun()
        else:
            st.info(f"**Prétérit:** {v['Preterit']}  \n**Participe Passé:** {v['Past Participle']}  \n**Traduction:** {v['Translation']}")
            st.audio(get_audio(f"{v['Infinitive']}, {v['Preterit']}, {v['Past Participle']}"), format="audio/mp3")
            
            if st.button("Suivant", type="primary", use_container_width=True):
                st.session_state.queue.pop(0)
                st.session_state.flashcard_revealed = False
                st.rerun()
        
        st.write("---")
        if st.button("Quitter les flashcards"):
            st.session_state.app_mode = "menu"
            st.rerun()

# ====================================================
# MODE : ENTRAÎNEMENT
# ====================================================
elif st.session_state.app_mode == "training":
    
    # 1. Affichage de la correction si erreur au verbe précédent
    if st.session_state.show_correction:
        st.error("Erreur sur le verbe précédent :")
        v_last = df.iloc[st.session_state.last_idx]
        st.write(f"**Infinitif:** {v_last['Infinitive']}")
        st.write(f"**Prétérit:** {v_last['Preterit']}")
        st.write(f"**Participe Passé:** {v_last['Past Participle']}")
        st.write(f"**Traduction:** {v_last['Translation']}")
        
        if st.button("Continuer", use_container_width=True):
            st.session_state.show_correction = False
            st.rerun()
            
    # 2. Fin de session
    elif st.session_state.current_idx is None:
        st.success(f"Session terminée ! Score : {st.session_state.score} / {st.session_state.total}")
        if st.button("Retour au menu", use_container_width=True):
            st.session_state.app_mode = "menu"
            st.rerun()
            
    # 3. Interface de saisie
    else:
        progress = st.session_state.total - len(st.session_state.queue)
        st.progress(progress / st.session_state.total, text=f"Verbe {progress} / {st.session_state.total}")
        
        v = df.iloc[st.session_state.current_idx]
        given_c = st.session_state.given_col
        missing_cols = [c for c in cols if c != given_c]
        
        st.markdown(f"### {given_c} : **{v[given_c]}**")
        
        # Audio si la colonne donnée est en anglais
        if given_c != "Translation":
            st.audio(get_audio(v[given_c]), format="audio/mp3")
        
        with st.form("verb_form", clear_on_submit=True):
            user_inputs = {}
            for col_name in missing_cols:
                user_inputs[col_name] = st.text_input(f"{col_name} :", autocomplete="off")
            
            submitted = st.form_submit_button("Valider", use_container_width=True)
            
            if submitted:
                success = True
                for col_name in missing_cols:
                    expected = str(v[col_name]).strip().lower()
                    user_ans = str(user_inputs[col_name]).strip().lower()
                    if user_ans != expected:
                        success = False
                
                if success:
                    st.session_state.score += 1
                    if st.session_state.current_idx in st.session_state.error_list:
                        st.session_state.error_list.remove(st.session_state.current_idx)
                        controller.set('toeic_errors', st.session_state.error_list)
                else:
                    if st.session_state.current_idx not in st.session_state.error_list:
                        st.session_state.error_list.append(st.session_state.current_idx)
                        controller.set('toeic_errors', st.session_state.error_list)
                    st.session_state.last_idx = st.session_state.current_idx
                    st.session_state.show_correction = True

                # Passage au verbe suivant
                if st.session_state.queue:
                    st.session_state.current_idx = st.session_state.queue.pop(0)
                    st.session_state.given_col = random.choice(cols)
                else:
                    st.session_state.current_idx = None
                
                st.rerun()
                
        # Options de contrôle (Pause / Quitter)
        st.write("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Mettre en pause"):
                session_data = {
                    'queue': st.session_state.queue,
                    'total': st.session_state.total,
                    'score': st.session_state.score,
                    'current_idx': st.session_state.current_idx,
                    'given_col': st.session_state.given_col
                }
                controller.set('toeic_session', session_data)
                st.session_state.app_mode = "menu"
                st.rerun()
        with col2:
            if st.button("Quitter la session"):
                controller.set('toeic_session', {})
                st.session_state.app_mode = "menu"
                st.rerun()
