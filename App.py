import streamlit as st
import pandas as pd
import random
import io
from streamlit_cookies_controller import CookieController

st.set_page_config(page_title="TOEIC Verbs", layout="centered")

controller = CookieController()

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

# Get saved errors from browser storage
saved_errors = controller.get('toeic_errors')
if type(saved_errors) is not list:
    saved_errors = []
saved_errors = [int(i) for i in saved_errors if str(i).isdigit()]

if 'error_list' not in st.session_state:
    st.session_state.error_list = saved_errors
if 'current_queue' not in st.session_state:
    st.session_state.current_queue = []
if 'current_verb' not in st.session_state:
    st.session_state.current_verb = None
if 'given_col' not in st.session_state:
    st.session_state.given_col = None
if 'score' not in st.session_state:
    st.session_state.score = 0
if 'total_in_session' not in st.session_state:
    st.session_state.total_in_session = 0
if 'show_correction' not in st.session_state:
    st.session_state.show_correction = False
if 'last_verb' not in st.session_state:
    st.session_state.last_verb = None

st.title("TOEIC Irregular Verbs")

if st.session_state.show_correction:
    st.error("Erreur sur le verbe précédent :")
    v = st.session_state.last_verb
    st.write(f"**Infinitif:** {v['Infinitive']}")
    st.write(f"**Prétérit:** {v['Preterit']}")
    st.write(f"**Participe Passé:** {v['Past Participle']}")
    st.write(f"**Traduction:** {v['Translation']}")
    
    if st.button("Continuer", use_container_width=True):
        st.session_state.show_correction = False
        st.rerun()

elif st.session_state.current_verb is not None:
    progress = st.session_state.total_in_session - len(st.session_state.current_queue)
    st.progress(progress / st.session_state.total_in_session, text=f"Verbe {progress} / {st.session_state.total_in_session}")
    
    v = st.session_state.current_verb
    given_c = st.session_state.given_col
    missing_cols = [c for c in cols if c != given_c]
    
    st.markdown(f"### {given_c} : **{v[given_c]}**")
    
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
                if v.name in st.session_state.error_list:
                    st.session_state.error_list.remove(v.name)
                    controller.set('toeic_errors', st.session_state.error_list)
            else:
                if v.name not in st.session_state.error_list:
                    st.session_state.error_list.append(v.name)
                    controller.set('toeic_errors', st.session_state.error_list)
                st.session_state.last_verb = v
                st.session_state.show_correction = True

            if st.session_state.current_queue:
                idx = st.session_state.current_queue.pop(0)
                st.session_state.current_verb = df.iloc[idx]
                st.session_state.given_col = random.choice(cols)
            else:
                st.session_state.current_verb = None
            
            st.rerun()

elif st.session_state.total_in_session > 0:
    st.success(f"Session terminée ! Score : {st.session_state.score} / {st.session_state.total_in_session}")
    if st.button("Retour au menu", use_container_width=True):
        st.session_state.score = 0
        st.session_state.total_in_session = 0
        st.rerun()

else:
    st.subheader("Nouvelle session")
    
    mode = st.radio("Mode :", ["Tous les verbes", "Révision des erreurs"])
    
    if mode == "Tous les verbes":
        nb_verbs = st.selectbox("Nombre de verbes :", [20, 50, 100, 127])
    
    if st.button("Démarrer", use_container_width=True):
        if mode == "Révision des erreurs" and len(st.session_state.error_list) == 0:
            st.warning("Aucune erreur enregistrée pour le moment.")
        else:
            source_df = df.iloc[st.session_state.error_list] if mode == "Révision des erreurs" else df
            sample_size = len(source_df) if mode == "Révision des erreurs" else min(nb_verbs, len(source_df))
            
            st.session_state.current_queue = source_df.sample(sample_size).index.tolist()
            st.session_state.total_in_session = sample_size
            st.session_state.score = 0
            
            idx = st.session_state.current_queue.pop(0)
            st.session_state.current_verb = df.iloc[idx]
            st.session_state.given_col = random.choice(cols)
            st.rerun()

