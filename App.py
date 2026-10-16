import streamlit as st
import streamlit.components.v1 as components
import random
from services import (
    Verb, SRSCard, EvaluationResult,
    VerbRepository, UserRepository,
    AuthService, EvaluationService, SRSService, AudioService
)

st.set_page_config(page_title="TOEIC Verbs", layout="centered")


class AppController:
    COLS = ["Infinitive", "Preterit", "Past Participle", "Translation"]

    def __init__(self):
        self.verb_repo = VerbRepository()
        self.user_repo = UserRepository()
        self.auth = AuthService(self.user_repo)
        self.evaluator = EvaluationService()
        self.srs = SRSService(self.verb_repo, self.user_repo)
        self.audio = AudioService()
        self._init_state()

    def _init_state(self):
        defaults = {
            "current_user": None,
            "training_active": False, "queue": [], "current_idx": None, "given_col": None,
            "score": 0, "total": 0, "last_eval": None, "unsaved_count": 0,
            "fc_mode_running": None, "fc_queue": [], "flashcard_revealed": False, "cat_audio_id": None,
            "srs_active": False, "srs_current_card": None, "srs_given_col": None,
            "srs_eval_result": None, "srs_force_early": False,
            "correction_unlocked": False
        }
        for k, v in defaults.items():
            if k not in st.session_state:
                st.session_state[k] = v

    @staticmethod
    def _disable_mobile_autocorrect():
        components.html(
            """<script>
            const inputs = window.parent.document.querySelectorAll('input[type="text"]');
            inputs.forEach(i => { i.setAttribute('autocapitalize','none'); i.setAttribute('autocorrect','off'); i.setAttribute('spellcheck','false'); });
            </script>""", height=0
        )

    # --- COMPOSANT PARTAGÉ : AFFICHAGE COMPARATIF DES ERREURS & RECOPIE ACTIVE ---
    def _render_feedback_and_active_correction(self, res: EvaluationResult, form_prefix: str) -> bool:
        """Affiche le comparatif ligne par ligne et bloque la suite tant que l'erreur n'est pas recopiée."""
        v = res.verb
        if res.status == "EXACT":
            st.success("✅ **Réponse exacte !**")
            st.session_state.correction_unlocked = True
        elif res.status == "INCOMPLETE":
            st.warning(f"⚠️ **Réponse incomplète** — Manquant : `{', '.join(res.missing_translations)}`")
        else:
            st.error("❌ **Erreur détectée**")

        with st.container(border=True):
            st.markdown("#### Comparatif détaillé :")
            for col in self.COLS:
                if col == res.given_col:
                    st.markdown(f"- **{col} :** `{v.get_field(col)}` *(Donné)*")
                else:
                    fb = next((f for f in res.feedbacks if f.col == col), None)
                    if fb and fb.is_correct:
                        st.markdown(f"- **{col} :** `{fb.user_val}` ✅")
                    elif fb:
                        u_disp = fb.user_val if fb.user_val else "(vide)"
                        st.markdown(f"- **{col} :** ~~`{u_disp}`~~ ❌ $\\rightarrow$ **`{fb.expected_val}`** ✅")
                        if fb.hint:
                            st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;💡 *{fb.hint}*")

            st.audio(self.audio.get_audio(f"{v.infinitive}, {v.preterit}, {v.past_participle}"), format="audio/mp3")

        # Recopie active obligatoire si la réponse n'est pas exacte
        if not st.session_state.correction_unlocked:
            failed_fbs = [f for f in res.feedbacks if not f.is_correct]
            with st.form(f"{form_prefix}_retype_form", clear_on_submit=False):
                st.markdown("✍️ **Recopie la correction sans faute pour débloquer la suite :**")
                retyped = {fb.col: st.text_input(f"{fb.col} ({fb.expected_val}) :", autocomplete="off") for fb in failed_fbs}
                if st.form_submit_button("Vérifier ma correction", type="primary", use_container_width=True):
                    # Vérifie que chaque champ erroné a été correctement recopié
                    merged_inputs = {f.col: (retyped.get(f.col, "") if not f.is_correct else f.user_val) for f in res.feedbacks}
                    check_res = self.evaluator.evaluate(v, res.given_col, merged_inputs)
                    if check_res.status == "EXACT":
                        st.session_state.correction_unlocked = True
                        st.rerun()
                    else:
                        st.error("Recopie exactement la correction affichée en gras ci-dessus (avec toutes les traductions).")
            return False

        return True

    def run(self):
        st.title("TOEIC Irregular Verbs")
        if not st.session_state.current_user:
            self._render_auth_view()
            return

        user = st.session_state.current_user
        is_admin = self.auth.is_admin(user)
        streak = self.user_repo.update_login_streak(user)

        c1, c2 = st.columns([3, 1])
        c1.caption(f"{'👑 Admin' if is_admin else '👤 Connecté'} : **{user}** &nbsp;|&nbsp; 🔥 **{streak} jour(s)**")
        if c2.button("Déconnexion"):
            self.user_repo.flush_all(user)
            st.session_state.current_user = None
            st.rerun()

        titles = ["🧠 SRS (Anki)", "🎯 S'entraîner", "🗂️ Flashcards", "📊 Statistiques"] + (["🛠️ Admin"] if is_admin else [])
        tabs = st.tabs(titles)
        with tabs[0]: self._render_srs_tab(user)
        with tabs[1]: self._render_training_tab(user)
        with tabs[2]: self._render_flashcards_tab(user)
        with tabs[3]: self._render_stats_tab(user)
        if is_admin:
            with tabs[4]: self._render_admin_tab(user)

        self._disable_mobile_autocorrect()

    def _render_auth_view(self):
        st.subheader("Connexion")
        st.caption("Accès privé. Demande tes identifiants à Alexis si tu n'as pas de compte.")
        with st.form("login_form"):
            u = st.text_input("Pseudo :")
            p = st.text_input("Code PIN (4 chiffres) :", type="password", max_chars=4)
            if st.form_submit_button("Se connecter", type="primary", use_container_width=True):
                ok, msg = self.auth.login(u, p)
                if ok:
                    st.session_state.current_user = u.strip()
                    st.rerun()
                else:
                    st.error(msg)

    def _render_srs_tab(self, user: str):
        st.subheader("Mémoire à long terme (SRS)")
        if not st.session_state.srs_active:
            st.caption("10 nouveaux verbes/jour max (par ordre de fréquence TOEIC) + révisions espacées.")
            if st.button("Lancer ma session SRS du jour", type="primary", use_container_width=True):
                st.session_state.update(srs_active=True, srs_current_card=None, srs_eval_result=None, srs_force_early=False)
                st.rerun()
            return

        if st.session_state.srs_current_card is None:
            due, waiting = self.srs.get_daily_queue(user, force_early=st.session_state.srs_force_early)
            st.session_state.srs_force_early = False
            if not due:
                if waiting > 0:
                    st.info(f"⏳ **{waiting} verbe(s)** en apprentissage reviennent dans quelques minutes.")
                    c1, c2 = st.columns(2)
                    if c1.button("🔄 Actualiser", use_container_width=True): st.rerun()
                    if c2.button("⏩ Réviser sans attendre", type="primary", use_container_width=True):
                        st.session_state.srs_force_early = True
                        st.rerun()
                else:
                    st.success("🎉 Bravo ! Tu as terminé toutes tes révisions SRS du jour.")
                if st.button("Fermer la session SRS", use_container_width=True):
                    st.session_state.srs_active = False
                    st.rerun()
                return

            st.session_state.srs_current_card = due[0]
            st.session_state.srs_given_col = random.choice(self.COLS)
            st.session_state.srs_eval_result = None
            st.session_state.correction_unlocked = False

        card: SRSCard = st.session_state.srs_current_card
        v = self.verb_repo.get_by_id(card.verb_id)
        given_c = st.session_state.srs_given_col

        st.caption(f"Niveau TOEIC : **{v.level}**")
        st.markdown(f"### {given_c} : **{v.get_field(given_c)}**")
        if given_c != "Translation":
            st.audio(self.audio.get_audio(v.get_field(given_c)), format="audio/mp3")

        if st.session_state.srs_eval_result is None:
            with st.form("srs_form", clear_on_submit=True):
                inputs = {c: st.text_input(f"{c} :", autocomplete="off") for c in self.COLS if c != given_c}
                if st.form_submit_button("Vérifier ma réponse", type="primary", use_container_width=True):
                    res = self.evaluator.evaluate(v, given_c, inputs)
                    st.session_state.srs_eval_result = res
                    st.session_state.correction_unlocked = (res.status == "EXACT")
                    st.rerun()
        else:
            unlocked = self._render_feedback_and_active_correction(st.session_state.srs_eval_result, "srs")
            if unlocked:
                st.markdown("##### Choisis l'intervalle de répétition :")
                labels = self.srs.get_button_labels(card)
                r1c1, r1c2 = st.columns(2)
                r2c1, r2c2 = st.columns(2)
                for btn_col, key, is_prim in [(r1c1, "again", False), (r1c2, "hard", False), (r2c1, "good", True), (r2c2, "easy", False)]:
                    if btn_col.button(labels[key], type="primary" if is_prim else "secondary", use_container_width=True):
                        self.srs.process_rating(user, v.id, key)
                        st.session_state.srs_current_card = None
                        st.rerun()

        st.write("---")
        if st.button("Quitter la session SRS", use_container_width=True):
            st.session_state.update(srs_current_card=None, srs_active=False)
            st.rerun()

    def _render_training_tab(self, user: str):
        errors = self.user_repo.get_errors(user)
        paused = self.user_repo.get_paused_session(user)

        if not st.session_state.training_active:
            st.subheader("S'entraîner par listes")
            if paused and paused.get("current_idx") is not None:
                rem = len(paused.get("queue", [])) + 1
                st.info(f"⏸️ Session en pause : **{rem} verbe(s) restant(s)** (Score : {paused.get('score', 0)}/{paused.get('total', 0)}).")
                if st.button("▶️ Reprendre la session en pause", type="primary", use_container_width=True):
                    st.session_state.update(
                        queue=paused["queue"], score=paused["score"], total=paused["total"],
                        current_idx=paused["current_idx"], given_col=paused["given_col"],
                        last_eval=None, unsaved_count=0, training_active=True
                    )
                    self.user_repo.save_paused_session(user, {}, flush=True)
                    st.rerun()
                st.write("---")

            tr_source = st.radio("Source Entraînement :", ["Tous les verbes (127)", f"Mes erreurs ({len(errors)})"], key="tr_src")
            lvl, nb = "Tous", 127
            if tr_source.startswith("Tous"):
                c1, c2 = st.columns(2)
                lvl = c1.selectbox("Niveau :", ["Tous", "A1", "A2", "B1", "B2"])
                nb = c2.selectbox("Nombre de verbes :", [20, 50, 100, 127])

            if st.button("Lancer l'entraînement", type="primary", use_container_width=True):
                if tr_source.startswith("Mes erreurs") and not errors:
                    st.warning("Aucune erreur enregistrée.")
                else:
                    v_pool = [self.verb_repo.get_by_id(i) for i in errors] if tr_source.startswith("Mes erreurs") else self.verb_repo.get_all()
                    if lvl != "Tous" and tr_source.startswith("Tous"):
                        v_pool = [v for v in v_pool if v.level == lvl]
                    pool = [v.id for v in v_pool]
                    sampled = random.sample(pool, len(pool) if tr_source.startswith("Mes erreurs") else min(nb, len(pool)))
                    st.session_state.update(
                        current_idx=sampled.pop(0), queue=sampled, total=len(sampled) + 1,
                        score=0, given_col=random.choice(self.COLS), last_eval=None, unsaved_count=0, training_active=True
                    )
                    st.rerun()
            return

        if st.session_state.last_eval is not None:
            unlocked = self._render_feedback_and_active_correction(st.session_state.last_eval, "train")
            if unlocked:
                if st.button("Continuer ➡️", type="primary", use_container_width=True):
                    st.session_state.last_eval = None
                    st.rerun()
            return

        if st.session_state.current_idx is None:
            self.user_repo.flush_all(user)
            st.success(f"🎉 Session terminée ! Score : **{st.session_state.score} / {st.session_state.total}**")
            if st.button("Retour à la configuration", type="primary", use_container_width=True):
                st.session_state.training_active = False
                st.rerun()
            return

        done = st.session_state.total - len(st.session_state.queue)
        st.progress(done / st.session_state.total, text=f"Verbe {done} / {st.session_state.total}")

        v = self.verb_repo.get_by_id(st.session_state.current_idx)
        given_c = st.session_state.given_col
        st.caption(f"Niveau TOEIC : **{v.level}**")
        st.markdown(f"### {given_c} : **{v.get_field(given_c)}**")
        if given_c != "Translation":
            st.audio(self.audio.get_audio(v.get_field(given_c)), format="audio/mp3")

        with st.form("training_form", clear_on_submit=True):
            inputs = {c: st.text_input(f"{c} :", autocomplete="off") for c in self.COLS if c != given_c}
            if st.form_submit_button("Valider", type="primary", use_container_width=True):
                res = self.evaluator.evaluate(v, given_c, inputs)
                st.session_state.unsaved_count += 1
                if res.status == "EXACT":
                    st.session_state.score += 1
                    if v.id in errors:
                        errors.remove(v.id)
                        self.user_repo.save_errors(user, errors, flush=False)
                else:
                    if res.status == "INCOMPLETE":
                        st.session_state.score += 1
                    else:
                        self.user_repo.increment_failure(user, v.id, flush=False)
                    if v.id not in errors:
                        errors.append(v.id)
                        self.user_repo.save_errors(user, errors, flush=False)
                    st.session_state.last_eval = res
                    st.session_state.correction_unlocked = False

                if st.session_state.unsaved_count >= 5 or not st.session_state.queue:
                    self.user_repo.flush_all(user)
                    st.session_state.unsaved_count = 0

                st.session_state.current_idx = st.session_state.queue.pop(0) if st.session_state.queue else None
                st.session_state.given_col = random.choice(self.COLS)
                st.rerun()

        st.write("---")
        c1, c2 = st.columns(2)
        if c1.button("⏸️ Mettre en pause", use_container_width=True):
            self.user_repo.save_paused_session(user, {
                "queue": st.session_state.queue, "total": st.session_state.total,
                "score": st.session_state.score, "current_idx": st.session_state.current_idx, "given_col": st.session_state.given_col
            }, flush=True)
            st.session_state.training_active = False
            st.rerun()
        if c2.button("⏹️ Arrêter définitivement", use_container_width=True):
            self.user_repo.save_paused_session(user, {}, flush=True)
            st.session_state.update(current_idx=None, queue=[], training_active=False)
            st.rerun()

    def _render_flashcards_tab(self, user: str):
        errors = self.user_repo.get_errors(user)
        if st.session_state.fc_mode_running is None:
            st.subheader("Flashcards (Catalogue & Révision)")
            fc_src = st.radio("Source :", ["Tous les verbes (127)", f"Mes erreurs ({len(errors)})"], key="fc_src")
            fc_style = st.radio("Méthode :", ["Catalogue (Liste complète à faire défiler)", "Défilement aléatoire (Carte par carte)"], key="fc_style")
            lvl = st.selectbox("Filtrer par niveau :", ["Tous", "A1", "A2", "B1", "B2"]) if fc_src.startswith("Tous") else "Tous"

            if st.button("📖 Ouvrir le catalogue" if fc_style.startswith("Catalogue") else "🎲 Lancer les Flashcards", type="primary", use_container_width=True):
                verbs = [self.verb_repo.get_by_id(i) for i in errors] if fc_src.startswith("Mes erreurs") else self.verb_repo.get_all()
                if lvl != "Tous" and fc_src.startswith("Tous"):
                    verbs = [v for v in verbs if v.level == lvl]
                if not verbs:
                    st.warning("Aucun verbe disponible.")
                else:
                    ids = [v.id for v in verbs]
                    if not fc_style.startswith("Catalogue"):
                        random.shuffle(ids)
                    st.session_state.update(fc_queue=ids, cat_audio_id=None, flashcard_revealed=False, fc_mode_running="catalogue" if fc_style.startswith("Catalogue") else "random")
                    st.rerun()
            return

        if st.session_state.fc_mode_running == "catalogue":
            c1, c2 = st.columns([3, 1])
            c1.subheader(f"Catalogue ({len(st.session_state.fc_queue)} verbes)")
            if c2.button("⬅️ Retour", use_container_width=True):
                st.session_state.fc_mode_running = None
                st.rerun()

            q = EvaluationService.normalize_fr(st.text_input("🔍 Filtrer par mot (français ou anglais) :"))
            verbs_show = [self.verb_repo.get_by_id(vid) for vid in st.session_state.fc_queue]
            if q:
                verbs_show = [v for v in verbs_show if q in EvaluationService.normalize_fr(v.translation) or q in v.infinitive.lower() or q in v.preterit.lower() or q in v.past_participle.lower()]

            for v in verbs_show:
                with st.container(border=True):
                    ct, ca = st.columns([5, 1])
                    ct.markdown(f"**🇫🇷 {v.translation}** &nbsp; `[{v.level}]`  \n🇬🇧 **Inf :** `{v.infinitive}` &nbsp;|&nbsp; **Prét :** `{v.preterit}` &nbsp;|&nbsp; **Part :** `{v.past_participle}`")
                    if ca.button("🔊", key=f"aud_{v.id}"):
                        st.session_state.cat_audio_id = v.id
                    if st.session_state.cat_audio_id == v.id:
                        st.audio(self.audio.get_audio(f"{v.infinitive}, {v.preterit}, {v.past_participle}"), format="audio/mp3")
            return

        if not st.session_state.fc_queue:
            st.success("🎉 Toutes les flashcards ont été révisées !")
            if st.button("Retour", type="primary", use_container_width=True):
                st.session_state.fc_mode_running = None
                st.rerun()
            return

        v = self.verb_repo.get_by_id(st.session_state.fc_queue[0])
        st.caption(f"Cartes restantes : {len(st.session_state.fc_queue)} | Niveau : **{v.level}**")
        st.markdown(f"## {v.infinitive}")
        st.audio(self.audio.get_audio(v.infinitive), format="audio/mp3")

        if not st.session_state.flashcard_revealed:
            if st.button("Révéler", type="primary", use_container_width=True):
                st.session_state.flashcard_revealed = True
                st.rerun()
        else:
            st.info(f"**Prétérit :** {v.preterit}  \n**Participe Passé :** {v.past_participle}  \n**Traduction :** {v.translation}")
            st.audio(self.audio.get_audio(f"{v.infinitive}, {v.preterit}, {v.past_participle}"), format="audio/mp3")
            if st.button("Carte suivante ➡️", type="primary", use_container_width=True):
                st.session_state.fc_queue.pop(0)
                st.session_state.flashcard_revealed = False
                st.rerun()

        if st.button("Quitter les flashcards", use_container_width=True):
            st.session_state.fc_mode_running = None
            st.rerun()

    def _render_stats_tab(self, user: str):
        st.subheader("Tableau de bord & Statistiques")
        errors = self.user_repo.get_errors(user)
        failures = self.user_repo.get_failures(user)
        srs_cards = self.user_repo.get_srs_cards(user)

        c1, c2, c3 = st.columns(3)
        c1.metric("Acquis (SRS)", f"{sum(1 for c in srs_cards.values() if c.state == 'review')} / 127")
        c2.metric("En cours (SRS)", sum(1 for c in srs_cards.values() if c.state == "learning"))
        c3.metric("Erreurs actives", len(errors))

        st.write("---")
        st.markdown("#### 🔥 Tes 10 Bêtes noires (Verbes les plus ratés)")
        if not failures:
            st.caption("Aucun échec enregistré pour le moment.")
        for vid, count in sorted(failures.items(), key=lambda x: x[1], reverse=True)[:10]:
            vb = self.verb_repo.get_by_id(vid)
            st.write(f"- **[{vb.level}] {vb.infinitive}** (`{vb.preterit}`, `{vb.past_participle}`) — *{vb.translation}* : **{count} erreur(s)**")

    def _render_admin_tab(self, admin_user: str):
        st.subheader("🛠️ Gestion des comptes (Modérateur)")
        with st.form("admin_create_form", clear_on_submit=True):
            new_u = st.text_input("Pseudo du camarade :")
            new_p = st.text_input("Code PIN attribué (4 chiffres) :", max_chars=4)
            if st.form_submit_button("Créer ce compte", type="primary", use_container_width=True):
                ok, msg = self.auth.admin_create_user(admin_user, new_u, new_p)
                st.success(msg) if ok else st.error(msg)
                if ok: st.rerun()

        all_users = self.user_repo.list_all_users()
        other_users = [u for u in all_users if not self.auth.is_admin(u)]
        if other_users:
            st.write("---")
            sel_u = st.selectbox("Modifier ou supprimer un camarade :", other_users)
            c1, c2 = st.columns(2)
            with c1.form("reset_pin_form", clear_on_submit=True):
                rp = st.text_input("Nouveau PIN (4 chiffres) :", max_chars=4)
                if st.form_submit_button("Changer le PIN", use_container_width=True):
                    ok, msg = self.auth.admin_reset_pin(admin_user, sel_u, rp)
                    st.success(msg) if ok else st.error(msg)
            if c2.button(f"🗑️ Supprimer '{sel_u}'", use_container_width=True):
                ok, msg = self.auth.admin_delete_user(admin_user, sel_u)
                if ok: st.rerun()


if __name__ == "__main__":
    AppController().run()
