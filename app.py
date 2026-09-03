import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client

st.set_page_config(
    page_title="Basketball Academy",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------
# Helpers
# ----------------------------
def get_config():
    try:
        return (
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_PUBLISHABLE_KEY"],
            st.secrets["SUPABASE_SECRET_KEY"],
        )
    except Exception:
        st.error(
            "Λείπουν τα Supabase secrets. Δες το README.md και βάλε "
            "SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY και SUPABASE_SECRET_KEY."
        )
        st.stop()

SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, SUPABASE_SECRET_KEY = get_config()

def public_client():
    return create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)

def admin_client():
    # Χρησιμοποιείται μόνο server-side και μόνο σε Admin ενέργειες.
    return create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

def get_user_client():
    if "sb" not in st.session_state:
        st.session_state.sb = public_client()
    return st.session_state.sb

def logout():
    try:
        get_user_client().auth.sign_out()
    except Exception:
        pass
    for key in ["sb", "user", "profile"]:
        st.session_state.pop(key, None)
    st.rerun()

def load_profile(user_id):
    sb = get_user_client()
    result = (
        sb.table("profiles")
        .select("id,email,full_name,role,active")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    return result.data

def require_login():
    if "user" not in st.session_state:
        st.title("🏀 Basketball Academy")
        st.subheader("Είσοδος προπονητή")

        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Κωδικός", type="password")
            submitted = st.form_submit_button("Σύνδεση", use_container_width=True)

        if submitted:
            try:
                sb = public_client()
                response = sb.auth.sign_in_with_password(
                    {"email": email.strip(), "password": password}
                )
                if not response.user:
                    st.error("Δεν ήταν δυνατή η σύνδεση.")
                    st.stop()

                st.session_state.sb = sb
                st.session_state.user = response.user
                profile = load_profile(response.user.id)

                if not profile or not profile.get("active", False):
                    try:
                        sb.auth.sign_out()
                    except Exception:
                        pass
                    st.session_state.pop("user", None)
                    st.session_state.pop("sb", None)
                    st.error("Ο λογαριασμός δεν έχει ενεργή πρόσβαση στην ακαδημία.")
                    st.stop()

                st.session_state.profile = profile
                st.rerun()
            except Exception:
                st.error("Λάθος email/κωδικός ή μη εγκεκριμένος λογαριασμός.")
        st.stop()

    if "profile" not in st.session_state:
        profile = load_profile(st.session_state.user.id)
        if not profile or not profile.get("active", False):
            logout()
        st.session_state.profile = profile

def pct(made, attempted):
    if attempted in (None, 0):
        return 0.0
    return round((made / attempted) * 100, 1)

def get_players(active_only=True):
    sb = get_user_client()
    query = sb.table("players").select("*").order("full_name")
    if active_only:
        query = query.eq("active", True)
    return query.execute().data or []

def player_map(players):
    return {f'{p["full_name"]} — {p.get("team") or "Χωρίς τμήμα"}': p["id"] for p in players}

def role_is_admin():
    return st.session_state.profile.get("role") == "admin"

def safe_int(v):
    try:
        return int(v)
    except Exception:
        return 0

# ----------------------------
# Authentication
# ----------------------------
require_login()
sb = get_user_client()
profile = st.session_state.profile

# ----------------------------
# Sidebar
# ----------------------------
st.sidebar.title("🏀 Academy")
st.sidebar.caption(profile.get("full_name") or profile.get("email"))
st.sidebar.caption("Admin" if role_is_admin() else "Coach")

pages = [
    "🏠 Dashboard",
    "👥 Παίκτες",
    "✅ Παρουσίες",
    "🎯 Αξιολογήσεις",
    "📈 Εξέλιξη",
]
if role_is_admin():
    pages.append("⚙️ Χρήστες")

page = st.sidebar.radio("Μενού", pages)
st.sidebar.divider()
if st.sidebar.button("Αποσύνδεση", use_container_width=True):
    logout()

# ----------------------------
# Dashboard
# ----------------------------
if page == "🏠 Dashboard":
    st.title("Dashboard")

    players = get_players()
    attendance = sb.table("attendance").select("id,present").execute().data or []
    tests = sb.table("skill_tests").select("id").execute().data or []

    c1, c2, c3 = st.columns(3)
    c1.metric("Ενεργοί παίκτες", len(players))
    c2.metric("Καταχωρήσεις παρουσιών", len(attendance))
    c3.metric("Αξιολογήσεις", len(tests))

    st.subheader("Πρόσφατοι παίκτες")
    if players:
        df = pd.DataFrame(players)
        cols = [c for c in ["full_name", "birth_year", "team", "position"] if c in df.columns]
        st.dataframe(df[cols], use_container_width=True, hide_index=True)
    else:
        st.info("Δεν έχουν προστεθεί παίκτες ακόμη.")

# ----------------------------
# Players
# ----------------------------
elif page == "👥 Παίκτες":
    st.title("Παίκτες")

    tab1, tab2 = st.tabs(["Λίστα", "➕ Νέος παίκτης"])

    with tab1:
        players = get_players(active_only=False)
        if players:
            df = pd.DataFrame(players)
            display_cols = [
                c for c in ["full_name", "birth_year", "team", "position", "active"]
                if c in df.columns
            ]
            st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
        else:
            st.info("Δεν υπάρχουν παίκτες.")

    with tab2:
        with st.form("new_player"):
            full_name = st.text_input("Ονοματεπώνυμο *")
            birth_year = st.number_input(
                "Έτος γέννησης", min_value=2000, max_value=date.today().year, value=2012
            )
            team = st.text_input("Τμήμα", placeholder="π.χ. U14")
            position = st.selectbox(
                "Θέση", ["", "Guard", "Forward", "Center", "Guard/Forward", "Forward/Center"]
            )
            notes = st.text_area("Σημειώσεις")
            save = st.form_submit_button("Αποθήκευση παίκτη", use_container_width=True)

        if save:
            if not full_name.strip():
                st.error("Το ονοματεπώνυμο είναι υποχρεωτικό.")
            else:
                sb.table("players").insert({
                    "full_name": full_name.strip(),
                    "birth_year": int(birth_year),
                    "team": team.strip() or None,
                    "position": position or None,
                    "notes": notes.strip() or None,
                    "active": True,
                    "created_by": st.session_state.user.id,
                }).execute()
                st.success("Ο παίκτης προστέθηκε.")
                st.rerun()

# ----------------------------
# Attendance
# ----------------------------
elif page == "✅ Παρουσίες":
    st.title("Παρουσίες")
    players = get_players()

    if not players:
        st.info("Πρόσθεσε πρώτα παίκτες.")
    else:
        teams = sorted({p.get("team") or "Χωρίς τμήμα" for p in players})
        selected_team = st.selectbox("Τμήμα", teams)
        training_date = st.date_input("Ημερομηνία προπόνησης", value=date.today())

        team_players = [
            p for p in players
            if (p.get("team") or "Χωρίς τμήμα") == selected_team
        ]

        with st.form("attendance_form"):
            st.write("Τσέκαρε όσους ήταν **παρόντες**.")
            presence = {}
            for p in team_players:
                presence[p["id"]] = st.checkbox(p["full_name"], value=True)
            submit_att = st.form_submit_button(
                "Αποθήκευση παρουσιών", use_container_width=True
           , key=f"attendance_{training_date}_{p['id']}")

        if submit_att:
            for p in team_players:
                # Αν υπάρχει ήδη εγγραφή για ίδια μέρα/παίκτη, ενημέρωσέ την.
                existing = (
                    sb.table("attendance")
                    .select("id")
                    .eq("player_id", p["id"])
                    .eq("training_date", str(training_date))
                    .execute()
                    .data
                )
                payload = {
                    "player_id": p["id"],
                    "training_date": str(training_date),
                    "present": bool(presence[p["id"]]),
                    "recorded_by": st.session_state.user.id,
                }
                if existing:
                    sb.table("attendance").update(payload).eq("id", existing[0]["id"]).execute()
                else:
                    sb.table("attendance").insert(payload).execute()

            st.success("Οι παρουσίες αποθηκεύτηκαν.")

        st.subheader("Ιστορικό")
        att = (
            sb.table("attendance")
            .select("training_date,present,players(full_name,team),profiles(full_name)")
            .order("training_date", desc=True)
            .limit(200)
            .execute()
            .data
            or []
        )
        if att:
            rows = []
            for r in att:
                rows.append({
                    "Ημερομηνία": r.get("training_date"),
                    "Παίκτης": (r.get("players") or {}).get("full_name"),
                    "Τμήμα": (r.get("players") or {}).get("team"),
                    "Παρουσία": "✅" if r.get("present") else "❌",
                    "Καταχώρηση": (r.get("profiles") or {}).get("full_name"),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ----------------------------
# Skill tests
# ----------------------------
elif page == "🎯 Αξιολογήσεις":
    st.title("Αξιολόγηση παίκτη")
    players = get_players()

    if not players:
        st.info("Πρόσθεσε πρώτα παίκτες.")
    else:
        mapping = player_map(players)
        selected_label = st.selectbox("Παίκτης", list(mapping.keys()))
        selected_id = mapping[selected_label]

        with st.form("skill_test"):
            test_date = st.date_input("Ημερομηνία τεστ", value=date.today())

            st.markdown("#### Σουτ")
            c1, c2 = st.columns(2)
            ft_made = c1.number_input("Βολές εύστοχες", 0, 100, 0)
            ft_att = c2.number_input("Βολές προσπάθειες", 0, 100, 20)

            c3, c4 = st.columns(2)
            mid_made = c3.number_input("Mid-range εύστοχα", 0, 100, 0)
            mid_att = c4.number_input("Mid-range προσπάθειες", 0, 100, 20)

            c5, c6 = st.columns(2)
            three_made = c5.number_input("Τρίποντα εύστοχα", 0, 100, 0)
            three_att = c6.number_input("Τρίποντα προσπάθειες", 0, 100, 20)

            st.markdown("#### Layups")
            c7, c8 = st.columns(2)
            right_made = c7.number_input("Δεξί εύστοχα", 0, 100, 0)
            right_att = c8.number_input("Δεξί προσπάθειες", 0, 100, 20)

            c9, c10 = st.columns(2)
            left_made = c9.number_input("Αριστερό εύστοχα", 0, 100, 0)
            left_att = c10.number_input("Αριστερό προσπάθειες", 0, 100, 20)

            sprint = st.number_input(
                "Sprint 20m (δευτερόλεπτα)", min_value=0.0, max_value=20.0, value=0.0, step=0.01
            )
            coach_notes = st.text_area("Παρατηρήσεις προπονητή")

            save_test = st.form_submit_button(
                "Αποθήκευση αξιολόγησης", use_container_width=True
            )

        if save_test:
            validations = [
                (ft_made, ft_att, "βολές"),
                (mid_made, mid_att, "mid-range"),
                (three_made, three_att, "τρίποντα"),
                (right_made, right_att, "δεξιά layups"),
                (left_made, left_att, "αριστερά layups"),
            ]
            invalid = [name for made, att, name in validations if made > att]
            if invalid:
                st.error("Τα εύστοχα δεν γίνεται να είναι περισσότερα από τις προσπάθειες: " + ", ".join(invalid))
            else:
                sb.table("skill_tests").insert({
                    "player_id": selected_id,
                    "test_date": str(test_date),
                    "free_throws_made": int(ft_made),
                    "free_throws_attempted": int(ft_att),
                    "midrange_made": int(mid_made),
                    "midrange_attempted": int(mid_att),
                    "threes_made": int(three_made),
                    "threes_attempted": int(three_att),
                    "layups_right_made": int(right_made),
                    "layups_right_attempted": int(right_att),
                    "layups_left_made": int(left_made),
                    "layups_left_attempted": int(left_att),
                    "sprint_20m": float(sprint) if sprint else None,
                    "coach_notes": coach_notes.strip() or None,
                    "recorded_by": st.session_state.user.id,
                }).execute()
                st.success("Η αξιολόγηση αποθηκεύτηκε.")

# ----------------------------
# Progress
# ----------------------------
elif page == "📈 Εξέλιξη":
    st.title("Εξέλιξη παίκτη")
    players = get_players()

    if not players:
        st.info("Δεν υπάρχουν παίκτες.")
    else:
        mapping = player_map(players)
        label = st.selectbox("Επίλεξε παίκτη", list(mapping.keys()))
        pid = mapping[label]

        tests = (
            sb.table("skill_tests")
            .select("*")
            .eq("player_id", pid)
            .order("test_date")
            .execute()
            .data
            or []
        )

        if not tests:
            st.info("Δεν υπάρχουν αξιολογήσεις για αυτόν τον παίκτη.")
        else:
            df = pd.DataFrame(tests)
            df["Βολές %"] = df.apply(
                lambda r: pct(safe_int(r["free_throws_made"]), safe_int(r["free_throws_attempted"])), axis=1
            )
            df["Mid-range %"] = df.apply(
                lambda r: pct(safe_int(r["midrange_made"]), safe_int(r["midrange_attempted"])), axis=1
            )
            df["Τρίποντα %"] = df.apply(
                lambda r: pct(safe_int(r["threes_made"]), safe_int(r["threes_attempted"])), axis=1
            )
            df["test_date"] = pd.to_datetime(df["test_date"])

            st.subheader("Ευστοχία")
            chart_df = df.set_index("test_date")[["Βολές %", "Mid-range %", "Τρίποντα %"]]
            st.line_chart(chart_df)

            if "sprint_20m" in df.columns and df["sprint_20m"].notna().any():
                st.subheader("Sprint 20m")
                st.line_chart(df.set_index("test_date")[["sprint_20m"]])

            show = df[["test_date", "Βολές %", "Mid-range %", "Τρίποντα %", "sprint_20m", "coach_notes"]].copy()
            show.columns = ["Ημερομηνία", "Βολές %", "Mid-range %", "Τρίποντα %", "Sprint 20m", "Σημειώσεις"]
            st.dataframe(show, use_container_width=True, hide_index=True)

# ----------------------------
# Admin users
# ----------------------------
elif page == "⚙️ Χρήστες":
    if not role_is_admin():
        st.error("Δεν έχεις πρόσβαση.")
        st.stop()

    st.title("Διαχείριση χρηστών")
    admin = admin_client()

    profiles = (
        admin.table("profiles")
        .select("id,email,full_name,role,active,created_at")
        .order("created_at")
        .execute()
        .data
        or []
    )

    st.caption(f"Εγκεκριμένοι λογαριασμοί: {len(profiles)} / 10")
    if profiles:
        st.dataframe(pd.DataFrame(profiles), use_container_width=True, hide_index=True)

    st.subheader("➕ Δημιουργία προπονητή")
    with st.form("create_coach"):
        coach_name = st.text_input("Ονοματεπώνυμο")
        coach_email = st.text_input("Email")
        coach_password = st.text_input("Προσωρινός κωδικός", type="password")
        coach_role = st.selectbox("Ρόλος", ["coach", "admin"])
        create = st.form_submit_button("Δημιουργία χρήστη", use_container_width=True)

    if create:
        if len(profiles) >= 10:
            st.error("Έχει συμπληρωθεί το όριο των 10 λογαριασμών.")
        elif not coach_name.strip() or not coach_email.strip() or len(coach_password) < 8:
            st.error("Συμπλήρωσε όνομα, email και κωδικό τουλάχιστον 8 χαρακτήρων.")
        else:
            try:
                response = admin.auth.admin.create_user({
                    "email": coach_email.strip().lower(),
                    "password": coach_password,
                    "email_confirm": True,
                    "user_metadata": {"full_name": coach_name.strip()},
                })

                admin.table("profiles").insert({
                    "id": response.user.id,
                    "email": coach_email.strip().lower(),
                    "full_name": coach_name.strip(),
                    "role": coach_role,
                    "active": True,
                }).execute()

                st.success("Ο χρήστης δημιουργήθηκε.")
                st.rerun()
            except Exception as e:
                st.error(f"Δεν δημιουργήθηκε ο χρήστης: {e}")

    st.subheader("Ενεργοποίηση / απενεργοποίηση")
    if profiles:
        selectable = {
            f'{p["full_name"]} — {p["email"]}': p
            for p in profiles
            if p["id"] != st.session_state.user.id
        }
        if selectable:
            selected_user_label = st.selectbox("Χρήστης", list(selectable.keys()))
            selected_user = selectable[selected_user_label]
            new_active = st.toggle(
                "Ενεργός",
                value=bool(selected_user.get("active", True)),
                key=f"active_{selected_user['id']}",
            )
            if st.button("Αποθήκευση κατάστασης"):
                admin.table("profiles").update(
                    {"active": new_active}
                ).eq("id", selected_user["id"]).execute()
                st.success("Η κατάσταση ενημερώθηκε.")
                st.rerun()

st.caption("Basketball Academy Management System")
